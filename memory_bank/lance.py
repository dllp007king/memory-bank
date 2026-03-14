"""
LanceDB 向量数据库连接模块

提供 LanceDB 的连接管理、表操作和向量存储功能。
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from contextlib import contextmanager
import lancedb
import pyarrow as pa

FactVector = dict
EntityVector = dict
from .lance_schema import (
    MEMORIES_SCHEMA,
    ENTITIES_SCHEMA,
    RELATIONS_SCHEMA,
    MEMORIES_TABLE_NAME,
    ENTITIES_TABLE_NAME,
    RELATIONS_TABLE_NAME,
    EMBEDDING_DIM
)

# 配置日志
logger = logging.getLogger(__name__)


class LanceConnection:
    """
    LanceDB 数据库连接管理器
    
    管理与 LanceDB 的连接，提供表的创建、打开、关闭操作。
    支持上下文管理器模式。
    
    使用示例：
        with LanceConnection("./data/lancedb") as conn:
            table = conn.open_table(MEMORIES_TABLE_NAME)
            # 执行操作...
    """
    
    def __init__(self, db_path: str = "./data/lancedb"):
        """
        初始化 LanceDB 连接管理器
        
        Args:
            db_path: 数据库存储路径
        """
        self.db_path = Path(db_path)
        self._db = None
        self._tables: Dict[str, Any] = {}
        
    def connect(self):
        """
        连接到 LanceDB 数据库
        
        如果数据库不存在会自动创建。
        """
        try:
            # 确保目录存在
            self.db_path.mkdir(parents=True, exist_ok=True)
            
            # 连接数据库
            self._db = lancedb.connect(self.db_path)
            logger.info(f"[LanceDB] 已连接到数据库: {self.db_path}")
            return self._db
            
        except Exception as e:
            logger.error(f"[LanceDB] 连接失败: {e}")
            raise
    
    def close(self):
        """
        关闭数据库连接
        
        LanceDB 不需要显式关闭连接，此方法主要用于清理资源。
        """
        self._tables.clear()
        self._db = None
        logger.info("[LanceDB] 已关闭连接")
    
    def create_table(self, table_name: str, schema: pa.Schema, mode: str = "create") -> Any:
        """
        创建表
        
        Args:
            table_name: 表名称
            schema: PyArrow Schema
            mode: 创建模式 ("create" 或 "overwrite")
            
        Returns:
            LanceDB 表对象
        """
        try:
            if self._db is None:
                self.connect()
            
            # 检查表是否已存在
            existing_tables = self._db.table_names()
            
            if table_name in existing_tables and mode == "create":
                logger.info(f"[LanceDB] 表 {table_name} 已存在")
                return self._db.open_table(table_name)
            
            # 创建空表
            table = self._db.create_table(
                table_name,
                schema=schema,
                mode=mode
            )
            
            logger.info(f"[LanceDB] 已创建表: {table_name}")
            self._tables[table_name] = table
            return table
            
        except Exception as e:
            logger.error(f"[LanceDB] 创建表失败 {table_name}: {e}")
            raise
    
    def open_table(self, table_name: str) -> Any:
        """
        打开表
        
        Args:
            table_name: 表名称
            
        Returns:
            LanceDB 表对象
        """
        try:
            if self._db is None:
                self.connect()
            
            # 检查缓存
            if table_name in self._tables:
                return self._tables[table_name]
            
            # 打开表
            table = self._db.open_table(table_name)
            self._tables[table_name] = table
            
            logger.info(f"[LanceDB] 已打开表: {table_name}")
            return table
            
        except Exception as e:
            logger.error(f"[LanceDB] 打开表失败 {table_name}: {e}")
            raise
    
    def drop_table(self, table_name: str):
        """
        删除表
        
        Args:
            table_name: 表名称
        """
        try:
            if self._db is None:
                self.connect()
            
            self._db.drop_table(table_name)
            
            if table_name in self._tables:
                del self._tables[table_name]
            
            logger.info(f"[LanceDB] 已删除表: {table_name}")
            
        except Exception as e:
            logger.error(f"[LanceDB] 删除表失败 {table_name}: {e}")
            raise
    
    def list_tables(self) -> List[str]:
        """
        列出所有表
        
        Returns:
            表名称列表
        """
        if self._db is None:
            self.connect()
        
        return self._db.table_names()
    
    def init_schema(self):
        """
        初始化默认 Schema
        
        创建 facts_vectors 和 entities_vectors 表
        """
        try:
            # 事实向量表 Schema
            facts_schema = pa.schema([
                pa.field("fact_id", pa.string()),
                pa.field("content", pa.string()),
                pa.field("kind", pa.string()),
                pa.field("timestamp", pa.timestamp('us')),
                pa.field("source_path", pa.string()),
                pa.field("source_line", pa.int64()),
                pa.field("confidence", pa.float64()),
                pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM)),
            ])
            
            # 实体向量表 Schema
            entities_schema = pa.schema([
                pa.field("slug", pa.string()),
                pa.field("name", pa.string()),
                pa.field("summary", pa.string()),
                pa.field("entity_type", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), EMBEDDING_DIM)),
                pa.field("first_seen", pa.timestamp('us')),
                pa.field("last_updated", pa.timestamp('us')),
            ])
            
            # 创建表
            self.create_table(MEMORIES_TABLE_NAME, facts_schema)
            self.create_table(ENTITIES_TABLE_NAME, entities_schema)
            
            # 创建 FTS 全文搜索索引
            try:
                memories_table = self.db.open_table(MEMORIES_TABLE_NAME)
                memories_table.create_fts_index("content")
                logger.info("[LanceDB] FTS 索引创建成功")
            except Exception as e:
                logger.warning(f"[LanceDB] FTS 索引创建失败: {e}")
            
            logger.info("[LanceDB] Schema 初始化完成")
            
        except Exception as e:
            logger.error(f"[LanceDB] Schema 初始化失败: {e}")
            raise
    
    # ==================== 上下文管理器 ====================
    
    def __enter__(self):
        """进入上下文"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        self.close()
        return False
    
    # ==================== 便捷方法 ====================
    
    def insert_facts(self, facts: List[FactVector]):
        """
        批量插入事实向量
        
        Args:
            facts: 事实向量列表
        """
        try:
            table = self.open_table(MEMORIES_TABLE_NAME)
            
            # 转换为字典列表
            data = [fact.dict() for fact in facts]
            
            # 插入数据
            table.add(data)
            logger.info(f"[LanceDB] 已插入 {len(facts)} 条事实记录")
            
        except Exception as e:
            logger.error(f"[LanceDB] 插入事实失败: {e}")
            raise
    
    def insert_entities(self, entities: List[EntityVector]):
        """
        批量插入实体向量
        
        Args:
            entities: 实体向量列表
        """
        try:
            table = self.open_table(ENTITIES_TABLE_NAME)
            
            # 转换为字典列表
            data = [entity.dict() for entity in entities]
            
            # 插入数据
            table.add(data)
            logger.info(f"[LanceDB] 已插入 {len(entities)} 条实体记录")
            
        except Exception as e:
            logger.error(f"[LanceDB] 插入实体失败: {e}")
            raise
    
    def search_similar_facts(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filter: Optional[str] = None
    ) -> List[Dict]:
        """
        搜索相似事实
        
        Args:
            query_vector: 查询向量
            top_k: 返回前 K 个结果
            filter: 过滤条件 (SQL WHERE 子句)
            
        Returns:
            相似事实列表
        """
        try:
            table = self.open_table(MEMORIES_TABLE_NAME)
            
            # 执行向量搜索
            results = table.search(query_vector) \
                .limit(top_k)
            
            if filter:
                results = results.where(filter)
            
            # 转换为字典列表
            return results.to_list()
            
        except Exception as e:
            logger.error(f"[LanceDB] 搜索事实失败: {e}")
            raise
    
    def search_similar_entities(
        self,
        query_vector: List[float],
        top_k: int = 10,
        entity_type: Optional[str] = None
    ) -> List[Dict]:
        """
        搜索相似实体
        
        Args:
            query_vector: 查询向量
            top_k: 返回前 K 个结果
            entity_type: 实体类型过滤
            
        Returns:
            相似实体列表
        """
        try:
            table = self.open_table(ENTITIES_TABLE_NAME)
            
            # 执行向量搜索
            results = table.search(query_vector).limit(top_k)
            
            if entity_type:
                results = results.where(f"entity_type = '{entity_type}'")
            
            # 转换为字典列表
            return results.to_list()
            
        except Exception as e:
            logger.error(f"[LanceDB] 搜索实体失败: {e}")
            raise


def init_lancedb(db_path: str = "./data/lancedb") -> LanceConnection:
    """
    初始化 LanceDB 数据库并返回连接实例
    
    Args:
        db_path: 数据库路径
        
    Returns:
        LanceConnection 实例
    """
    conn = LanceConnection(db_path)
    conn.init_schema()
    return conn
