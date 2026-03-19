"""
jieba 词典共享管理器

提供统一的 jieba 分词词典管理，所有模块共享同一个词典实例。
支持从 LanceDB 同步实体，自动更新。
"""

import jieba
import logging
from typing import List, Optional, Set
from pathlib import Path

logger = logging.getLogger(__name__)

# 已加载的词语（用于去重）
_loaded_words: Set[str] = set()

# 初始化标记
_initialized = False


def init_jieba(force: bool = False):
    """初始化 jieba 词典
    
    Args:
        force: 是否强制重新初始化
    """
    global _initialized, _loaded_words
    
    if _initialized and not force:
        return
    
    # 基础领域词汇
    base_words = [
        # 系统/项目名
        "memory-bank", "记忆银行", "OpenClaw", "LanceDB", "FTS5",
        # 实体类型
        "PERSON", "TOOL", "SYSTEM", "PROJECT", "CONCEPT", "PLACE", "EVENT", "GAME",
        # 技术术语
        "向量搜索", "嵌入", "embedding", "NER", "实体识别", "知识图谱",
        "混合搜索", "BM25", "RRF", "分词", "索引",
        # 常用词组
        "置信度", "衰减", "实体", "关系", "记忆", "搜索",
    ]
    
    for word in base_words:
        add_word(word, freq=100)
    
    # 从 LanceDB 同步
    sync_from_lancedb()
    
    _initialized = True
    logger.info(f"[jieba-dict] 初始化完成，已加载 {len(_loaded_words)} 个词语")


def add_word(word: str, freq: int = 10):
    """添加词语到词典
    
    Args:
        word: 词语
        freq: 词频（越大越不会被拆分）
    """
    if not word or len(word) < 2:
        return
    
    # 去重
    if word in _loaded_words:
        return
    
    jieba.add_word(word, freq=freq)
    _loaded_words.add(word)
    logger.debug(f"[jieba-dict] 添加词语: {word}")


def add_words(words: List[str], freq: int = 10):
    """批量添加词语
    
    Args:
        words: 词语列表
        freq: 词频
    """
    for word in words:
        add_word(word, freq)


def sync_from_lancedb():
    """从 LanceDB 同步实体到词典"""
    try:
        import lancedb
        
        db_path = Path.home() / ".openclaw" / "workspace" / ".memory" / "lancedb"
        if not db_path.exists():
            return 0
        
        db = lancedb.connect(str(db_path))
        
        count = 0
        try:
            # 读取 entities 表
            table = db.open_table("entities")
            results = table.to_list()
            
            for row in results:
                name = row.get("name", "")
                if name:
                    add_word(name, freq=5)
                    count += 1
                
                # 处理别名
                aliases = row.get("aliases", [])
                if aliases:
                    for alias in aliases:
                        if alias:
                            add_word(alias, freq=5)
                            count += 1
            
            if count > 0:
                logger.info(f"[jieba-dict] 从 LanceDB 同步了 {count} 个实体")
                
        except Exception as e:
            logger.debug(f"[jieba-dict] LanceDB 同步跳过: {e}")
            
    except Exception as e:
        logger.debug(f"[jieba-dict] LanceDB 连接失败: {e}")
    
    return count


def get_loaded_count() -> int:
    """获取已加载的词语数量"""
    return len(_loaded_words)


def tokenize(text: str, mode: str = "search") -> List[str]:
    """分词
    
    Args:
        text: 待分词文本
        mode: 模式
            - "search": 搜索引擎模式（lcut_for_search），用于查询，召回率高
            - "index":  全模式（cut_all=True），用于建索引，覆盖所有可能词组
            - "cut_all": 同 index
            - "cut":    精确模式（默认）
    
    Returns:
        分词结果列表
    """
    if mode == "search":
        return jieba.lcut_for_search(text)
    elif mode in ("index", "cut_all"):
        return jieba.lcut(text, cut_all=True)
    else:
        return jieba.lcut(text)


def tokenize_to_string(text: str, mode: str = "search") -> str:
    """分词并转为字符串
    
    Args:
        text: 待分词文本
        mode: 模式
    
    Returns:
        分词后的字符串（用空格分隔）
    """
    return " ".join(tokenize(text, mode))


# 初始化
init_jieba()
