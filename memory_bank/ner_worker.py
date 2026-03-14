"""
NER 后台处理器

负责从队列中取出待处理任务，调用 NER 子代理，更新数据库。
"""

import json
import time
import logging
import threading
import requests
from typing import Optional, Dict, Any, List

from .ner_llm import (
    NER_CONFIG, 
    parse_entities, 
    get_next_model,
    generate_ner_prompt
)
from .ner_queue import (
    get_pending_items,
    mark_processing,
    mark_done,
    mark_failed,
    increment_retry
)

logger = logging.getLogger(__name__)

# Gateway API 配置（需要根据实际情况修改）
GATEWAY_URL = "http://localhost:18789"
GATEWAY_TIMEOUT = 60

# 直接调用 cli-proxy-api (OpenAI 兼容)
CLI_PROXY_URL = "http://localhost:8317/v1/chat/completions"
CLI_PROXY_KEY = "sk-3YfYAUDeac50p87gZ"


class NERWorker:
    """NER 后台处理器"""
    
    def __init__(self, db, gateway_url: str = None, max_concurrent: int = None):
        """
        初始化 NER Worker
        
        Args:
            db: 数据库实例
            gateway_url: OpenClaw Gateway URL
            max_concurrent: 最大并发数
        """
        self.db = db
        self.gateway_url = gateway_url or GATEWAY_URL
        self.max_concurrent = max_concurrent or NER_CONFIG['max_concurrent']
        self.running = False
        self.worker_thread = None
        self.active_tasks = 0
        self.lock = threading.Lock()
    
    def start(self):
        """启动后台处理线程"""
        if self.running:
            logger.warning("NER worker already running")
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.worker_thread.start()
        logger.info("NER worker started")
    
    def stop(self):
        """停止后台处理线程"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("NER worker stopped")
    
    def _run_loop(self):
        """主循环"""
        while self.running:
            try:
                # 检查是否有空闲槽位
                with self.lock:
                    if self.active_tasks >= self.max_concurrent:
                        time.sleep(1)
                        continue
                
                # 获取待处理项
                items = get_pending_items(self.db, limit=1)
                
                if not items:
                    # 没有待处理项，等待一会
                    time.sleep(2)
                    continue
                
                # 处理单个项
                item = items[0]
                
                # 标记为处理中
                if not mark_processing(self.db, item['id']):
                    logger.warning(f"Failed to mark processing: id={item['id']}")
                    continue
                
                # 增加活跃任务计数
                with self.lock:
                    self.active_tasks += 1
                
                # 在新线程中处理（异步）
                thread = threading.Thread(
                    target=self._process_item,
                    args=(item,),
                    daemon=True
                )
                thread.start()
                
                # 批次间隔
                time.sleep(NER_CONFIG['batch_interval'])
                
            except Exception as e:
                logger.error(f"Error in NER worker loop: {e}")
                time.sleep(5)
    
    def _process_item(self, item: Dict[str, Any]):
        """
        处理单个 NER 任务
        
        Args:
            item: 队列项
        """
        item_id = item['id']
        fact_id = item['fact_id']
        content = item['content']
        
        try:
            # 尝试调用 NER（带降级）
            entities = self._ner_with_fallback(content)
            
            if entities is not None:
                # 成功提取实体
                self._save_entities(fact_id, entities)
                
                # 标记完成
                result_json = json.dumps({'entities': entities}, ensure_ascii=False)
                mark_done(self.db, item_id, result_json, 'multiple')
                
                logger.info(f"NER completed: fact_id={fact_id}, entities={len(entities)}")
            else:
                # 所有模型都失败
                error_msg = "All models failed"
                mark_failed(self.db, item_id, error_msg)
                
                # 通知 liu
                self._notify_liu_via_feishu(
                    f"⚠️ NER 提取失败\n\n"
                    f"所有模型均报错，请检查。\n\n"
                    f"内容摘要：{content[:50]}...\n"
                    f"时间：{time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
        
        except Exception as e:
            logger.error(f"Error processing item {item_id}: {e}")
            mark_failed(self.db, item_id, str(e))
        
        finally:
            # 减少活跃任务计数
            with self.lock:
                self.active_tasks -= 1
    
    def _ner_with_fallback(self, content: str) -> Optional[List[Dict[str, str]]]:
        """
        带降级的 NER 调用
        
        Args:
            content: 待处理的内容
            
        Returns:
            实体列表，如果所有模型都失败则返回 None
        """
        models = NER_CONFIG['models']
        
        for model_id in models:
            try:
                result = self._spawn_ner_agent(model_id, content)
                entities = parse_entities(result)
                
                if entities:
                    logger.info(f"NER success with model: {model_id}")
                    return entities
                else:
                    logger.warning(f"NER returned empty entities with model: {model_id}")
                    continue
                    
            except Exception as e:
                logger.warning(f"NER failed with model {model_id}: {e}")
                continue
        
        # 所有模型都失败
        logger.error("All models failed for NER")
        return None
    
    def _spawn_ner_agent(self, model_id: str, content: str) -> str:
        """
        调用 NER 子代理（直接调用 cli-proxy-api）
        
        Args:
            model_id: 模型 ID
            content: 待处理的内容
            
        Returns:
            模型返回的结果
        """
        prompt = generate_ner_prompt(content)
        
        try:
            # 直接调用 cli-proxy-api (OpenAI 兼容)
            response = requests.post(
                CLI_PROXY_URL,
                headers={
                    "Authorization": f"Bearer {CLI_PROXY_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model_id.replace("omega/", ""),  # 移除前缀
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 1000
                },
                timeout=GATEWAY_TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('choices', [{}])[0].get('message', {}).get('content', '')
            else:
                raise Exception(f"API error: {response.status_code} - {response.text[:200]}")
                
        except requests.Timeout:
            raise Exception("API timeout")
        except Exception as e:
            raise Exception(f"API error: {e}")
    
    def _save_entities(self, fact_id: str, entities: List[Dict[str, str]]):
        """
        保存实体到数据库
        
        Args:
            fact_id: 事实 ID
            entities: 实体列表
        """
        try:
            from .ner_extractor import slugify
            
            for entity in entities:
                name = entity['name']
                entity_type = entity['type']
                slug = slugify(name)
                
                # 插入或更新实体
                self.db.execute(
                    """
                    INSERT INTO entities (slug, name, entity_type, first_seen, last_updated)
                    VALUES (?, ?, ?, datetime('now'), datetime('now'))
                    ON CONFLICT(slug) DO UPDATE SET
                        last_updated = datetime('now')
                    """,
                    (slug, name, entity_type)
                )
                
                # 创建关联
                self.db.execute(
                    """
                    INSERT OR IGNORE INTO fact_entities (fact_id, entity_slug)
                    VALUES (?, ?)
                    """,
                    (fact_id, slug)
                )
            
            logger.info(f"Saved {len(entities)} entities for fact {fact_id}")
            
        except Exception as e:
            logger.error(f"Failed to save entities: {e}")
            raise
    
    def _notify_liu_via_feishu(self, message: str):
        """
        通过飞书通知 liu
        
        Args:
            message: 通知消息
        """
        try:
            # 调用 Gateway API 发送飞书消息
            response = requests.post(
                f"{self.gateway_url}/api/message",
                json={
                    "channel": "feishu",
                    "target": "liu",
                    "message": message
                },
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Sent notification to liu via Feishu")
            else:
                logger.warning(f"Failed to send notification: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def process_once(self):
        """
        单次处理（用于批处理或手动触发）
        """
        items = get_pending_items(self.db, limit=self.max_concurrent)
        
        for item in items:
            if not mark_processing(self.db, item['id']):
                continue
            
            self._process_item(item)
        
        return len(items)


def start_ner_worker(db, gateway_url: str = None) -> NERWorker:
    """
    启动 NER 后台处理器
    
    Args:
        db: 数据库实例
        gateway_url: Gateway URL
        
    Returns:
        Worker 实例
    """
    worker = NERWorker(db, gateway_url)
    worker.start()
    return worker
