"""
NER 队列管理

提供 NER 队列的增删改查操作。
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def enqueue_ner(db, fact_id: str, content: str) -> int:
    """
    添加 NER 任务到队列
    
    Args:
        db: 数据库实例
        fact_id: 事实 ID
        content: 待处理的内容
        
    Returns:
        队列项 ID
    """
    try:
        cursor = db.execute(
            """
            INSERT INTO ner_queue (fact_id, content, status, created_at)
            VALUES (?, ?, 'pending', ?)
            """,
            (fact_id, content, datetime.now().isoformat())
        )
        queue_id = cursor.lastrowid
        logger.info(f"Enqueued NER task: fact_id={fact_id}, queue_id={queue_id}")
        return queue_id
    except Exception as e:
        logger.error(f"Failed to enqueue NER task: {e}")
        raise


def get_pending_items(db, limit: int = 10) -> List[Dict[str, Any]]:
    """
    获取待处理的 NER 任务
    
    Args:
        db: 数据库实例
        limit: 最大返回数量
        
    Returns:
        待处理任务列表
    """
    try:
        cursor = db.execute(
            """
            SELECT id, fact_id, content, retry_count, created_at
            FROM ner_queue
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (limit,)
        )
        
        items = []
        for row in cursor.fetchall():
            items.append({
                'id': row['id'],
                'fact_id': row['fact_id'],
                'content': row['content'],
                'retry_count': row['retry_count'],
                'created_at': row['created_at']
            })
        
        return items
    except Exception as e:
        logger.error(f"Failed to get pending items: {e}")
        return []


def mark_processing(db, item_id: int) -> bool:
    """
    标记任务为处理中
    
    Args:
        db: 数据库实例
        item_id: 队列项 ID
        
    Returns:
        是否成功
    """
    try:
        db.execute(
            """
            UPDATE ner_queue
            SET status = 'processing'
            WHERE id = ? AND status = 'pending'
            """,
            (item_id,)
        )
        logger.info(f"Marked NER task as processing: id={item_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to mark processing: {e}")
        return False


def mark_done(db, item_id: int, result_json: str, model_used: str) -> bool:
    """
    标记任务为完成
    
    Args:
        db: 数据库实例
        item_id: 队列项 ID
        result_json: NER 结果（JSON 字符串）
        model_used: 使用的模型
        
    Returns:
        是否成功
    """
    try:
        db.execute(
            """
            UPDATE ner_queue
            SET status = 'done',
                result_json = ?,
                model_used = ?,
                processed_at = ?
            WHERE id = ?
            """,
            (result_json, model_used, datetime.now().isoformat(), item_id)
        )
        logger.info(f"Marked NER task as done: id={item_id}, model={model_used}")
        return True
    except Exception as e:
        logger.error(f"Failed to mark done: {e}")
        return False


def mark_failed(db, item_id: int, error_message: str) -> bool:
    """
    标记任务为失败
    
    Args:
        db: 数据库实例
        item_id: 队列项 ID
        error_message: 错误信息
        
    Returns:
        是否成功
    """
    try:
        db.execute(
            """
            UPDATE ner_queue
            SET status = 'failed',
                error_message = ?,
                processed_at = ?
            WHERE id = ?
            """,
            (error_message, datetime.now().isoformat(), item_id)
        )
        logger.info(f"Marked NER task as failed: id={item_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to mark failed: {e}")
        return False


def increment_retry(db, item_id: int) -> int:
    """
    增加重试计数并重置为 pending
    
    Args:
        db: 数据库实例
        item_id: 队列项 ID
        
    Returns:
        新的重试次数
    """
    try:
        cursor = db.execute(
            """
            UPDATE ner_queue
            SET retry_count = retry_count + 1,
                status = 'pending'
            WHERE id = ?
            """,
            (item_id,)
        )
        
        # 获取新的重试次数
        cursor = db.execute(
            "SELECT retry_count FROM ner_queue WHERE id = ?",
            (item_id,)
        )
        row = cursor.fetchone()
        retry_count = row['retry_count'] if row else 0
        
        logger.info(f"Incremented retry count: id={item_id}, retry_count={retry_count}")
        return retry_count
    except Exception as e:
        logger.error(f"Failed to increment retry: {e}")
        return 0


def get_queue_stats(db) -> Dict[str, int]:
    """
    获取队列统计信息
    
    Args:
        db: 数据库实例
        
    Returns:
        统计信息字典
    """
    try:
        cursor = db.execute(
            """
            SELECT status, COUNT(*) as count
            FROM ner_queue
            GROUP BY status
            """
        )
        
        stats = {
            'pending': 0,
            'processing': 0,
            'done': 0,
            'failed': 0,
            'total': 0
        }
        
        for row in cursor.fetchall():
            status = row['status']
            count = row['count']
            stats[status] = count
            stats['total'] += count
        
        return stats
    except Exception as e:
        logger.error(f"Failed to get queue stats: {e}")
        return {'pending': 0, 'processing': 0, 'done': 0, 'failed': 0, 'total': 0}


def get_item_by_fact_id(db, fact_id: str) -> Optional[Dict[str, Any]]:
    """
    根据 fact_id 获取队列项
    
    Args:
        db: 数据库实例
        fact_id: 事实 ID
        
    Returns:
        队列项信息，如果不存在则返回 None
    """
    try:
        cursor = db.execute(
            """
            SELECT id, fact_id, content, status, retry_count, 
                   model_used, result_json, error_message, 
                   created_at, processed_at
            FROM ner_queue
            WHERE fact_id = ?
            """,
            (fact_id,)
        )
        
        row = cursor.fetchone()
        if row:
            return {
                'id': row['id'],
                'fact_id': row['fact_id'],
                'content': row['content'],
                'status': row['status'],
                'retry_count': row['retry_count'],
                'model_used': row['model_used'],
                'result_json': row['result_json'],
                'error_message': row['error_message'],
                'created_at': row['created_at'],
                'processed_at': row['processed_at']
            }
        
        return None
    except Exception as e:
        logger.error(f"Failed to get item by fact_id: {e}")
        return None


def clear_old_done_items(db, days: int = 30) -> int:
    """
    清理旧的已完成项
    
    Args:
        db: 数据库实例
        days: 保留天数
        
    Returns:
        删除的项数
    """
    try:
        cursor = db.execute(
            """
            DELETE FROM ner_queue
            WHERE status = 'done'
              AND processed_at < datetime('now', ?)
            """,
            (f'-{days} days',)
        )
        
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info(f"Cleared {deleted} old done items")
        
        return deleted
    except Exception as e:
        logger.error(f"Failed to clear old items: {e}")
        return 0


def enqueue_batch(db, items: List[Dict[str, str]]) -> int:
    """
    批量添加 NER 任务
    
    Args:
        db: 数据库实例
        items: 任务列表，每项包含 fact_id 和 content
        
    Returns:
        成功添加的数量
    """
    count = 0
    for item in items:
        try:
            enqueue_ner(db, item['fact_id'], item['content'])
            count += 1
        except Exception as e:
            logger.error(f"Failed to enqueue item {item.get('fact_id')}: {e}")
    
    return count
