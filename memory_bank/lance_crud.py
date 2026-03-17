"""
LanceDB CRUD 操作模块

提供基于 LanceDB 的记忆、实体、关系的创建、读取、更新、删除操作。
支持自动向量嵌入和语义搜索。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
import json
import lancedb
import pyarrow as pa
from pathlib import Path

from .embedding import embed_single, get_config
from .lifecycle import infer_decay_rate, DEFAULT_DECAY_RATE, effective_confidence
from .lance_schema import RELATIONS_SCHEMA, MEMORIES_SCHEMA, ENTITIES_SCHEMA
from .logger import get_logger
from .similarity import calculate_similarity, get_update_strategy, UpdateStrategy, find_similar_memories
from .contradiction import detect_contradiction, handle_contradiction, ContradictionResolution
from .entity_types import EntityRef, RelationRef, EntityType, RelationType
from .slug_generator import generate_slug, parse_slug, get_entity_type_from_slug, encode_base62, decode_base62, get_type_prefix

logger = get_logger()

# jieba 中文分词（使用共享词典管理器）
from .jieba_dict import add_word, add_words


# ==================== 数据模型 ====================

@dataclass
class Memory:
    """记忆记录"""
    id: str = ""
    content: str = ""
    memory_type: str = "fact"  # fact, experience, preference, summary
    entities: List[dict] = field(default_factory=list)  # 支持对象格式
    relations: List[dict] = field(default_factory=list)  # 支持对象格式
    confidence: float = 1.0
    source: str = ""
    importance: float = 0.5
    vector: Optional[List[float]] = None
    created_at: str = ""
    updated_at: str = ""
    # === Lifecycle fields ===
    decay_rate: float = 0.01
    lifecycle_state: str = "ACTIVE"
    superseded_by: str = ""
    access_count: int = 0
    last_accessed_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            # 实体列表：字符串（兼容）或对象（转换为 JSON 字符串）
            "entities": self._entities_to_storage(),
            # 关系列表：字符串（简化格式）或对象（转换为简化字符串）
            "relations": self._relations_to_storage(),
            "confidence": self.confidence,
            "source": self.source,
            "importance": self.importance,
            "vector": self.vector,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # Lifecycle fields
            "decay_rate": self.decay_rate,
            "lifecycle_state": self.lifecycle_state,
            "superseded_by": self.superseded_by,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at,
        }
    
    def _entities_to_storage(self) -> list:
        """将实体列表转换为存储格式（list[string]）"""
        result = []
        for e in self.entities:
            if isinstance(e, str):
                result.append(e)
            elif isinstance(e, dict):
                # 对象格式：转换为 JSON 字符串存储
                import json
                result.append(json.dumps(e, ensure_ascii=False))
        return result
    
    def _relations_to_storage(self) -> list:
        """将关系列表转换为存储格式（list[string]）"""
        result = []
        for r in self.relations:
            if isinstance(r, str):
                # 简化格式：保持原样
                result.append(r)
            elif isinstance(r, dict):
                # 对象格式：转换为简化字符串格式 "A|喜欢|B"
                source = r.get("source", r.get("from", ""))
                rel_type = r.get("relation_type", r.get("rel", "RELATED_TO"))
                target = r.get("target", r.get("to", ""))
                result.append(f"{source}|{rel_type}|{target}")
        return result
    
    def get_entity_objects(self) -> List[EntityRef]:
        """获取实体对象列表"""
        result = []
        for e in self.entities:
            if isinstance(e, str):
                result.append(EntityRef(slug=e, name=e, entity_type="PERSON"))
            elif isinstance(e, dict):
                result.append(EntityRef.from_dict(e))
        return result
    
    def get_relation_objects(self) -> List[RelationRef]:
        """获取关系对象列表"""
        result = []
        for r in self.relations:
            if isinstance(r, str):
                result.append(RelationRef.from_string(r))
            elif isinstance(r, dict):
                result.append(RelationRef.from_dict(r))
        return result
    
    def get_entity_objects(self) -> List[EntityRef]:
        """获取实体对象列表"""
        import json
        result = []
        for e in self.entities:
            if isinstance(e, str):
                result.append(EntityRef(slug=e, name=e, entity_type="PERSON"))
            elif isinstance(e, dict):
                result.append(EntityRef.from_dict(e))
        return result
    
    def get_relation_objects(self) -> List[RelationRef]:
        """获取关系对象列表"""
        result = []
        for r in self.relations:
            if isinstance(r, str):
                result.append(RelationRef.from_string(r))
            elif isinstance(r, dict):
                result.append(RelationRef.from_dict(r))
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            memory_type=data.get("memory_type", "fact"),
            entities=data.get("entities", []),
            relations=data.get("relations", []),
            confidence=data.get("confidence", 1.0),
            source=data.get("source", ""),
            importance=data.get("importance", 0.5),
            vector=data.get("vector"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            # Lifecycle fields with defaults
            decay_rate=data.get("decay_rate", 0.01),
            lifecycle_state=data.get("lifecycle_state", "ACTIVE"),
            superseded_by=data.get("superseded_by", ""),
            access_count=data.get("access_count", 0),
            last_accessed_at=data.get("last_accessed_at", ""),
        )


@dataclass
class Entity:
    """实体"""
    slug: str = ""
    name: str = ""
    entity_type: str = "PERSON"  # PERSON, ORG, LOCATION, CONCEPT
    summary: str = ""
    aliases: List[str] = field(default_factory=list)
    vector: Optional[List[float]] = None
    first_seen: str = ""
    last_updated: str = ""

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "entity_type": self.entity_type,
            "summary": self.summary,
            "aliases": self.aliases,
            "vector": self.vector,
            "first_seen": self.first_seen,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        return cls(
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            entity_type=data.get("entity_type", "PERSON"),
            summary=data.get("summary", ""),
            aliases=data.get("aliases", []),
            vector=data.get("vector"),
            first_seen=data.get("first_seen", ""),
            last_updated=data.get("last_updated", ""),
        )


@dataclass
class Relation:
    """关系 - 匹配 LanceDB RELATIONS_SCHEMA"""
    id: str = ""
    source_slug: str = ""  # 源实体 slug
    target_slug: str = ""  # 目标实体 slug
    relation_type: str = ""  # e.g., "KNOWS", "WORKS_AT", "RELATED_TO"
    description: str = ""  # 关系描述
    confidence: float = 1.0
    source_memory_id: str = ""  # 关联的记忆 ID
    created_at: str = ""
    updated_at: str = ""
    version: int = 1
    tags: List[str] = field(default_factory=list)
    # === History tracking fields ===
    status: str = "ACTIVE"
    is_current: bool = True
    superseded_by: str = ""
    supersedes_target: str = ""
    old_confidence: float = 0.0
    replacement_reason: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_slug": self.source_slug,
            "target_slug": self.target_slug,
            "relation_type": self.relation_type,
            "description": self.description,
            "confidence": self.confidence,
            "source_memory_id": self.source_memory_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "tags": self.tags,
            "status": self.status,
            "is_current": self.is_current,
            "superseded_by": self.superseded_by,
            "supersedes_target": self.supersedes_target,
            "old_confidence": self.old_confidence,
            "replacement_reason": self.replacement_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Relation":
        return cls(
            id=data.get("id", ""),
            source_slug=data.get("source_slug", data.get("source", "")),
            target_slug=data.get("target_slug", data.get("target", "")),
            relation_type=data.get("relation_type", ""),
            description=data.get("description", ""),
            confidence=data.get("confidence", 1.0),
            source_memory_id=data.get("source_memory_id", data.get("source_memory", "")),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            version=data.get("version", 1),
            tags=data.get("tags", []),
            status=data.get("status", "ACTIVE"),
            is_current=data.get("is_current", True),
            superseded_by=data.get("superseded_by", ""),
            supersedes_target=data.get("supersedes_target", ""),
            old_confidence=data.get("old_confidence", 0.0),
            replacement_reason=data.get("replacement_reason", ""),
        )


# ==================== LanceDB Schema ====================
# 使用从 lance_schema.py 导入的统一 schema 定义
# RELATIONS_SCHEMA, MEMORIES_SCHEMA, ENTITIES_SCHEMA 已在顶部导入


# ==================== MemoryCRUD 类 ====================

class MemoryCRUD:
    """
    LanceDB 记忆 CRUD 操作类
    
    提供三个表的操作：
    - memories: 记忆存储（带向量索引）
    - entities: 实体存储（带向量索引）
    - relations: 关系存储
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """
        初始化 LanceDB 连接
        
        Args:
            db_path: 数据库路径，默认 ~/.openclaw/workspace/.memory/lancedb
        """
        if db_path is None:
            db_path = str(Path.home() / ".openclaw" / "workspace" / ".memory" / "lancedb")
        
        self.db_path = db_path
        self._db = None
        self._memories_table = None
        self._entities_table = None
        self._relations_table = None
        
    def _get_db(self):
        """获取数据库连接（懒加载）"""
        if self._db is None:
            # 确保目录存在
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self._db = lancedb.connect(self.db_path)
        return self._db
    
    def _get_memories_table(self):
        """获取或创建 memories 表"""
        if self._memories_table is None:
            db = self._get_db()
            try:
                self._memories_table = db.open_table("memories")
            except Exception:
                # 表不存在，创建新表
                self._memories_table = db.create_table(
                    "memories",
                    schema=MEMORIES_SCHEMA,
                    mode="create"
                )
        return self._memories_table
    
    def _get_entities_table(self):
        """获取或创建 entities 表"""
        if self._entities_table is None:
            db = self._get_db()
            try:
                self._entities_table = db.open_table("entities")
            except Exception:
                self._entities_table = db.create_table(
                    "entities",
                    schema=ENTITIES_SCHEMA,
                    mode="create"
                )
        return self._entities_table
    
    def _get_relations_table(self):
        """获取或创建 relations 表"""
        if self._relations_table is None:
            db = self._get_db()
            try:
                self._relations_table = db.open_table("relations")
            except Exception:
                self._relations_table = db.create_table(
                    "relations",
                    schema=RELATIONS_SCHEMA,
                    mode="create"
                )
        return self._relations_table
    
    def _update_jieba_dict(self, entities: Optional[List[str]]):
        """自动更新 jieba 词典（从实体列表）
        
        Args:
            entities: 实体列表
        """
        if not entities:
            return
        
        add_words(entities, freq=10)
    
    # ==================== 记忆 CRUD ====================
    
    def create_memory(
        self,
        content: str,
        memory_type: str = "fact",
        entities: Optional[List[str]] = None,
        relations: Optional[List[dict]] = None,
        importance: float = 0.5,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        source: str = "",
        auto_embed: bool = True,
        skip_lifecycle: bool = False,
        skip_relations: bool = False,  # 跳过自动创建关系（由调用方处理）
    ) -> Memory:
        """
        创建记忆

        Args:
            content: 记忆内容
            memory_type: 记忆类型 (fact, experience, preference, summary)
            entities: 关联实体列表
            relations: 关系列表 [{"from": "A", "rel": "使用", "to": "B"}]
            importance: 重要性 0-1
            tags: 标签列表
            confidence: 置信度
            source: 来源
            auto_embed: 是否自动生成向量嵌入
            skip_lifecycle: 是否跳过生命周期检测（用于批量导入）
            skip_relations: 是否跳过自动创建关系（由调用方处理）

        Returns:
            创建的记忆对象
        """
        import uuid

        now = datetime.now().isoformat()
        memory_id = str(uuid.uuid4())[:8]

        # 推断衰减率
        inferred_decay_rate = infer_decay_rate(content)

        # 处理关系：支持简化的 "A|喜欢|B" 格式
        relations_dict = []  # 存储为对象
        relations_str = []  # 存储为简化字符串
        
        if relations:
            for r in relations:
                # 支持简化的 "A|喜欢|B" 格式
                if isinstance(r, str):
                    relation_obj = RelationRef.from_string(r)
                    relations_dict.append(relation_obj.to_dict())
                    relations_str.append(relation_obj.to_string())
                # 支持完整的对象格式
                elif isinstance(r, dict):
                    relation_obj = RelationRef.from_dict(r)
                    relations_dict.append(relation_obj.to_dict())
                    relations_str.append(relation_obj.to_string())

        # 创建新记忆对象
        memory = Memory(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            entities=entities or [],
            relations=relations_str,
            confidence=confidence,
            source=source,
            created_at=now,
            updated_at=now,
            decay_rate=inferred_decay_rate,
            lifecycle_state="ACTIVE",
            access_count=0,
            last_accessed_at="",
            importance=importance,
        )

        # 生成向量嵌入（在生命周期检测后）
        if auto_embed and content:
            memory.vector = embed_single(content)

        # 生命周期检测（如果启用）
        superseded_memories = []
        if not skip_lifecycle:
            # 1. 查找相似记忆
            existing_memories = self.list_memories(limit=200)
            similar_memories = find_similar_memories(content, existing_memories, threshold=0.70)

            for old_mem, sim_score in similar_memories:
                # 只处理 ACTIVE 状态的记忆
                if old_mem.lifecycle_state != "ACTIVE":
                    continue

                # 2. 检测矛盾
                is_contradiction = detect_contradiction(old_mem.content, content)

                if is_contradiction:
                    # 处理矛盾
                    resolution = handle_contradiction(old_mem, memory)

                    if resolution == ContradictionResolution.UPDATE:
                        # 标记旧记忆为 SUPERSEDED
                        old_mem.lifecycle_state = "SUPERSEDED"
                        old_mem.superseded_by = memory_id
                        # 删除旧记忆并重新插入
                        table = self._get_memories_table()
                        table.delete(f"id = '{old_mem.id}'")
                        table.add([old_mem.to_dict()])
                        superseded_memories.append(old_mem.id)
                        logger.info("lance_crud", f"[Lifecycle] 记忆 {old_mem.id} 被 {memory_id} 取代（矛盾处理）")

                    elif resolution == ContradictionResolution.KEEP:
                        # 新记忆置信度低，不创建
                        logger.info("lance_crud", f"[Lifecycle] 跳过新记忆 {memory_id}（旧记忆置信度更高）")
                        return old_mem
                    # CONFIRM: 暂时保留两个，后续需要用户确认

                # 3. 根据相似度决定策略
                strategy = get_update_strategy(sim_score)

                if strategy == UpdateStrategy.OVERWRITE and not is_contradiction:
                    # 覆盖更新：删除旧记忆，插入新记忆
                    table = self._get_memories_table()
                    table.delete(f"id = '{old_mem.id}'")
                    logger.info("lance_crud", f"[Lifecycle] 记忆 {old_mem.id} 被覆盖（相似度: {sim_score:.4f}）")

                elif strategy == UpdateStrategy.MERGE and not is_contradiction:
                    # 合并更新：标记旧记忆为 SUPERSEDED
                    old_mem.lifecycle_state = "SUPERSEDED"
                    old_mem.superseded_by = memory_id
                    table = self._get_memories_table()
                    table.delete(f"id = '{old_mem.id}'")
                    table.add([old_mem.to_dict()])
                    superseded_memories.append(old_mem.id)
                    logger.info("lance_crud", f"[Lifecycle] 记忆 {old_mem.id} 被 {memory_id} 合并（相似度: {sim_score:.4f}）")

        # 插入新记忆到 LanceDB
        table = self._get_memories_table()
        table.add([memory.to_dict()])

        # 处理实体：提取 slug 列表用于 jieba
        entity_slugs = []
        if entities:
            for e in entities:
                # 支持字符串（兼容）或对象格式
                if isinstance(e, str):
                    entity_slugs.append(e)
                elif isinstance(e, dict):
                    entity_slugs.append(e.get("slug", e.get("name", "")))
        
        # 自动更新 jieba 词典
        self._update_jieba_dict(entity_slugs)

        # 如果有关系，同时写入关系表（除非跳过）
        if relations_dict and not skip_relations:
            for rel_dict in relations_dict:
                try:
                    self.create_relation(
                        source=rel_dict["source"],
                        target=rel_dict["target"],
                        relation_type=rel_dict["relation_type"],
                        description=rel_dict.get("description", ""),
                        confidence=rel_dict.get("confidence", 1.0),
                        source_memory_id=memory_id
                    )
                except Exception as e:
                    logger.error("lance_crud", f"创建关系失败: {e}")

        return memory
    
    def get_memory(self, memory_id: str, update_access: bool = True) -> Optional[Memory]:
        """
        获取单个记忆

        Args:
            memory_id: 记忆 ID
            update_access: 是否更新访问计数

        Returns:
            记忆对象，不存在返回 None
        """
        table = self._get_memories_table()
        result = table.search().where(f"id = '{memory_id}'").limit(1).to_list()

        if not result:  # to_list() 返回列表，不是 DataFrame
            return None

        memory = Memory.from_dict(result[0])

        # 更新访问计数（仅对 ACTIVE 状态）
        if update_access and memory.lifecycle_state == "ACTIVE":
            self._increment_access_count(memory_id)

        return memory
    
    def list_memories(
        self,
        memory_type: Optional[str] = None,
        entity: Optional[str] = None,
        limit: int = 100,
        lifecycle_state: Optional[str] = None,
        include_inactive: bool = False,
    ) -> List[Memory]:
        """
        列出记忆

        Args:
            memory_type: 按类型过滤
            entity: 按关联实体过滤
            limit: 返回数量限制
            lifecycle_state: 生命周期状态过滤（ACTIVE, ARCHIVED, SUPERSEDED, FORGOTTEN）
            include_inactive: 是否包含非 ACTIVE 状态的记忆

        Returns:
            记忆列表
        """
        table = self._get_memories_table()

        # 构建查询
        query = table.search()

        conditions = []
        if memory_type:
            conditions.append(f"memory_type = '{memory_type}'")
        if lifecycle_state:
            conditions.append(f"lifecycle_state = '{lifecycle_state}'")
        elif not include_inactive:
            # 默认只返回 ACTIVE 状态
            conditions.append("lifecycle_state = 'ACTIVE'")

        if entity:
            # LanceDB 不直接支持 list 包含查询，需要在 Python 层过滤
            pass

        if conditions:
            query = query.where(" AND ".join(conditions))

        # 获取结果（to_list() 返回字典列表）
        rows = query.limit(limit * 2).to_list()

        memories = []
        for row in rows:  # row 已经是字典
            memory = Memory.from_dict(row)

            # 如果指定了实体，进行过滤
            if entity and entity not in memory.entities:
                continue

            memories.append(memory)
            if len(memories) >= limit:
                break

        return memories
    
    def update_memory(
        self,
        memory_id: str,
        **kwargs
    ) -> Optional[Memory]:
        """
        更新记忆
        
        Args:
            memory_id: 记忆 ID
            **kwargs: 要更新的字段
            
        Returns:
            更新后的记忆对象
        """
        # 获取现有记忆
        memory = self.get_memory(memory_id)
        if memory is None:
            return None
        
        # 更新字段
        allowed_fields = {"content", "memory_type", "entities", "confidence", "source"}
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(memory, key, value)
        
        # 如果内容改变，重新生成向量
        if "content" in kwargs and kwargs["content"]:
            memory.vector = embed_single(kwargs["content"])
        
        memory.updated_at = datetime.now().isoformat()
        
        # LanceDB 不支持直接更新，需要删除后重新插入
        table = self._get_memories_table()
        table.delete(f"id = '{memory_id}'")
        table.add([memory.to_dict()])
        
        return memory
    
    def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆 ID
            
        Returns:
            是否删除成功
        """
        table = self._get_memories_table()
        
        # 检查是否存在
        memory = self.get_memory(memory_id)
        if memory is None:
            return False
        
        # 先删除与该记忆相关的所有关系
        relations_table = self._get_relations_table()
        relations_table.delete(f"source_memory_id = '{memory_id}'")
        
        table.delete(f"id = '{memory_id}'")
        return True

    def _increment_access_count(self, memory_id: str) -> bool:
        """增加访问计数"""
        table = self._get_memories_table()
        result = table.search().where(f"id = '{memory_id}'").limit(1).to_list()

        if not result:
            return False

        memory = Memory.from_dict(result[0])

        # 只更新 ACTIVE 状态的记忆
        if memory.lifecycle_state != "ACTIVE":
            return False

        new_count = memory.access_count + 1
        now = datetime.now().isoformat()

        # LanceDB doesn't support direct update, delete and re-insert
        table.delete(f"id = '{memory_id}'")

        # Update memory object
        memory.access_count = new_count
        memory.last_accessed_at = now
        table.add([memory.to_dict()])

        return True

    def search_memories(
        self,
        query: str,
        limit: int = 10,
        use_effective_confidence: bool = True,
        update_access: bool = True,
    ) -> List[Memory]:
        """
        语义搜索记忆

        Args:
            query: 查询文本
            limit: 返回数量
            use_effective_confidence: 是否使用有效置信度排序
            update_access: 是否更新访问计数

        Returns:
            相似记忆列表
        """
        # 生成查询向量
        query_vector = embed_single(query)
        if query_vector is None:
            return []

        table = self._get_memories_table()

        # 获取更多结果用于重排序（仅 ACTIVE 状态）
        results = table.search(query_vector, vector_column_name="vector") \
            .where("lifecycle_state = 'ACTIVE'") \
            .limit(limit * 3) \
            .to_list()

        memories = []
        for row in results:  # row 已经是字典
            memory = Memory.from_dict(row)
            memories.append(memory)

        if use_effective_confidence:
            # 使用有效置信度重新排序
            # 搜索得分 = 相关性 × 有效置信度
            # 相关性通过 1 - _distance 估算
            for mem in memories:
                # 计算有效置信度
                mem.effective_confidence = effective_confidence(mem)

            # 重新排序
            memories.sort(key=lambda m: m.effective_confidence, reverse=True)
            memories = memories[:limit]

        # 更新访问计数（仅 ACTIVE 状态的记忆）
        if update_access:
            for mem in memories:
                if mem.lifecycle_state == "ACTIVE":
                    self._increment_access_count(mem.id)

        return memories

    # ==================== 实体 CRUD ====================

    def get_next_slug_for_type(self, entity_type: str) -> str:
        """
        获取指定实体类型的下一个 slug

        使用类型前缀 + Base62 编码格式: {类型前缀}_{Base62}

        Args:
            entity_type: 实体类型 (PERSON, ORG, etc.)

        Returns:
            生成的 slug 字符串
        """
        table = self._get_entities_table()

        # 获取该类型的所有实体
        all_entities = table.search().limit(1000000).to_list()

        # 获取类型前缀
        type_prefix = get_type_prefix(entity_type)

        # 找到该类型的最大计数器值
        max_counter = -1
        for entity in all_entities:
            entity_slug = entity.get("slug", "")
            if entity_slug.startswith(f"{type_prefix}_"):
                try:
                    prefix, counter = parse_slug(entity_slug)
                    if prefix == type_prefix and counter > max_counter:
                        max_counter = counter
                except:
                    pass

        # 下一个计数器值
        next_counter = max_counter + 1

        # 生成 slug
        return generate_slug(entity_type, next_counter)

    def search_entities_by_name(
        self,
        name_query: str,
        entity_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Entity]:
        """
        按名称搜索实体

        Args:
            name_query: 名称查询字符串（支持模糊匹配）
            entity_type: 可选，按实体类型过滤
            limit: 返回数量限制

        Returns:
            匹配的实体列表
        """
        table = self._get_entities_table()

        # 获取所有实体
        all_entities = table.search().limit(1000000).to_list()

        # 按名称过滤（支持模糊匹配）
        query_lower = name_query.lower()
        results = []
        for entity_dict in all_entities:
            name = entity_dict.get("name", "")
            if query_lower in name.lower():
                # 如果指定了类型，还要过滤类型
                if entity_type:
                    et = entity_dict.get("entity_type", "")
                    import re
                    type_match = re.match(r'^([A-Z]+)', et)
                    type_key = type_match.group(1) if type_match else et
                    if type_key != entity_type and et != entity_type:
                        continue

                results.append(Entity.from_dict(entity_dict))
                if len(results) >= limit:
                    break

        return results

    def get_entity_by_name(
        self,
        name: str,
        entity_type: Optional[str] = None
    ) -> Optional[Entity]:
        """
        按名称精确获取实体

        Args:
            name: 实体名称
            entity_type: 可选，按实体类型过滤

        Returns:
            匹配的实体，不存在返回 None
        """
        table = self._get_entities_table()

        # 获取所有实体
        all_entities = table.search().limit(1000000).to_list()

        # 按名称精确匹配
        for entity_dict in all_entities:
            if entity_dict.get("name") == name:
                # 如果指定了类型，还要过滤类型
                if entity_type:
                    et = entity_dict.get("entity_type", "")
                    import re
                    type_match = re.match(r'^([A-Z]+)', et)
                    type_key = type_match.group(1) if type_match else et
                    if type_key != entity_type and et != entity_type:
                        continue

                return Entity.from_dict(entity_dict)

        return None

    def create_entity(
        self,
        name: str,
        entity_type: str = "PERSON",
        summary: str = "",
        aliases: Optional[List[str]] = None,
        auto_embed: bool = True,
        slug: Optional[str] = None,  # 可选，不传则自动生成
    ) -> Entity:
        """
        创建实体

        Args:
            name: 实体名称
            entity_type: 实体类型 (PERSON, ORG, LOCATION, CONCEPT)
            summary: 实体摘要
            aliases: 别名列表
            auto_embed: 是否自动生成向量嵌入
            slug: 实体唯一标识（可选，不传则自动生成 Base62 格式）

        Returns:
            创建的实体对象
        """
        from .slug_generator import generate_slug, get_type_prefix

        now = datetime.now().isoformat()

        # 自动生成 Base62 slug
        if slug is None:
            # 获取该类型的下一个计数器值
            type_prefix = get_type_prefix(entity_type)
            table = self._get_entities_table()
            existing = table.search().to_list()
            max_counter = -1
            for row in existing:
                row_slug = row.get('slug', '')
                if row_slug.startswith(type_prefix + '_'):
                    try:
                        from .slug_generator import decode_base62
                        counter_part = row_slug.split('_', 1)[1]
                        counter = decode_base62(counter_part)
                        max_counter = max(max_counter, counter)
                    except (IndexError, ValueError):
                        pass
            slug = generate_slug(entity_type, max_counter + 1)

        # 生成向量嵌入（基于名称和摘要）
        vector = None
        if auto_embed:
            text = f"{name} {summary}".strip()
            if text:
                vector = embed_single(text)

        entity = Entity(
            slug=slug,
            name=name,
            entity_type=entity_type,
            summary=summary,
            aliases=aliases or [],
            vector=vector,
            first_seen=now,
            last_updated=now,
        )

        # 插入到 LanceDB
        table = self._get_entities_table()
        table.add([entity.to_dict()])

        # 自动更新 jieba 词典
        self._update_jieba_dict([name])
        if aliases:
            self._update_jieba_dict(aliases)

        return entity
    
    def get_entity(self, slug: str) -> Optional[Entity]:
        """
        获取单个实体
        
        Args:
            slug: 实体标识
            
        Returns:
            实体对象，不存在返回 None
        """
        table = self._get_entities_table()
        result = table.search().where(f"slug = '{slug}'").limit(1).to_list()
        
        if not result:  # to_list() 返回列表
            return None
        
        return Entity.from_dict(result[0])
    
    def list_entities(
        self,
        entity_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Entity]:
        """
        列出实体
        
        Args:
            entity_type: 按类型过滤
            limit: 返回数量限制
            
        Returns:
            实体列表
        """
        table = self._get_entities_table()
        
        query = table.search()
        if entity_type:
            query = query.where(f"entity_type = '{entity_type}'")
        
        rows = query.limit(limit).to_list()  # to_list() 返回字典列表
        
        entities = []
        for row in rows:  # row 已经是字典
            entities.append(Entity.from_dict(row))
        
        return entities
    
    def delete_entity(self, slug: str) -> bool:
        """
        删除实体
        
        Args:
            slug: 实体标识
            
        Returns:
            是否删除成功
        """
        table = self._get_entities_table()
        
        # 检查是否存在
        entity = self.get_entity(slug)
        if entity is None:
            return False
        
        # 先删除与该实体相关的所有关系
        relations_table = self._get_relations_table()
        relations_table.delete(f"source_slug = '{slug}'")
        relations_table.delete(f"target_slug = '{slug}'")
        
        table.delete(f"slug = '{slug}'")
        return True
    
    # ==================== 关系 CRUD ====================
    
    def create_relation(
        self,
        source: str,
        target: str,
        relation_type: str,
        description: str = "",
        confidence: float = 1.0,
        source_memory_id: str = "",
    ) -> Relation:
        """
        创建关系（如果已存在则比较置信度，保留更高的）

        Args:
            source: 源实体 slug (Base62 格式，如 P_0)
            target: 目标实体 slug (Base62 格式，如 P_1)
            relation_type: 关系类型
            description: 关系描述
            confidence: 置信度
            source_memory_id: 关联的记忆 ID

        Returns:
            创建或更新的关系对象
        """
        import uuid

        now = datetime.now().isoformat()

        # 检查关系是否已存在（source_slug + target_slug + relation_type 唯一）
        existing = self.get_relation_by_triple(source, target, relation_type)
        if existing:
            # 关系已存在，比较置信度
            if confidence > existing.confidence:
                # 新关系置信度更高，更新
                table = self._get_relations_table()
                data = {
                    "confidence": confidence,
                    "source_memory_id": source_memory_id,
                    "updated_at": now,
                }
                if description:
                    data["description"] = description

                # 更新记录（LanceDB 不支持 update，需要删除后重新插入）
                table.delete(f"id = '{existing.id}'")
                old_confidence = existing.confidence  # 保存旧值用于日志
                existing.confidence = confidence
                existing.source_memory_id = source_memory_id
                if description:
                    existing.description = description
                existing.updated_at = now
                table.add([existing.to_dict()])

                logger.info("lance_crud", f"更新关系置信度: {source} -> {relation_type} -> {target} ({old_confidence:.2f} -> {confidence:.2f})")

                # 返回更新后的关系
                return self.get_relation(existing.id)
            else:
                logger.debug("lance_crud", f"关系已存在，置信度更低，跳过: {source} -> {relation_type} -> {target}")
                return existing

        # 创建新关系
        relation_id = str(uuid.uuid4())[:8]

        relation = Relation(
            id=relation_id,
            source_slug=source,
            target_slug=target,
            relation_type=relation_type,
            description=description,
            confidence=confidence,
            source_memory_id=source_memory_id,
            created_at=now,
            updated_at=now,
            version=1,
            status="ACTIVE",
            is_current=True,
        )

        # 插入到 LanceDB
        table = self._get_relations_table()
        table.add([relation.to_dict()])

        logger.info("lance_crud", f"创建新关系: {source} -> {relation_type} -> {target}")
        return relation
    
    def get_relation_by_triple(
        self,
        source: str,
        target: str,
        relation_type: str
    ) -> Optional[Relation]:
        """
        根据源、目标、关系类型查询关系

        Args:
            source: 源实体 slug
            target: 目标实体 slug
            relation_type: 关系类型

        Returns:
            关系对象，不存在返回 None
        """
        table = self._get_relations_table()

        # 查询条件（使用正确的字段名 source_slug, target_slug）
        conditions = [
            f"source_slug = '{source}'",
            f"target_slug = '{target}'",
            f"relation_type = '{relation_type}'"
        ]

        result = table.search().where(" AND ".join(conditions)).limit(1).to_list()

        if not result:
            return None

        data = result[0]
        return Relation.from_dict(data)
    
    def get_relation(self, relation_id: str) -> Optional[Relation]:
        """
        获取单个关系

        Args:
            relation_id: 关系 ID

        Returns:
            关系对象，不存在返回 None
        """
        table = self._get_relations_table()
        result = table.search().where(f"id = '{relation_id}'").limit(1).to_list()

        if not result:  # to_list() 返回列表
            return None

        data = result[0]  # 直接访问第一个元素
        return Relation.from_dict(data)
    
    def list_relations(
        self,
        source: Optional[str] = None,
        target: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Relation]:
        """
        列出关系

        Args:
            source: 按源实体过滤
            target: 按目标实体过滤
            relation_type: 按关系类型过滤
            limit: 返回数量限制

        Returns:
            关系列表
        """
        table = self._get_relations_table()

        conditions = []
        if source:
            conditions.append(f"source_slug = '{source}'")
        if target:
            conditions.append(f"target_slug = '{target}'")
        if relation_type:
            conditions.append(f"relation_type = '{relation_type}'")

        query = table.search()
        if conditions:
            query = query.where(" AND ".join(conditions))

        rows = query.limit(limit).to_list()  # to_list() 返回字典列表

        relations = []
        for row in rows:  # row 已经是字典
            data = row
            relations.append(Relation.from_dict(data))

        return relations
    
    def delete_relation(self, relation_id: str) -> bool:
        """
        删除关系
        
        Args:
            relation_id: 关系 ID
            
        Returns:
            是否删除成功
        """
        table = self._get_relations_table()
        
        # 检查是否存在
        relation = self.get_relation(relation_id)
        if relation is None:
            return False
        
        table.delete(f"id = '{relation_id}'")
        return True

    def create_or_replace_relation(
        self,
        source: str,
        target: str,
        relation_type: str,
        confidence: float = 1.0,
        source_memory_id: str = "",
        replacement_reason: str = "update",
    ) -> Relation:
        """
        创建或替代关系（支持不同目标替代）

        处理逻辑：
        1. 相同目标 → 比较置信度，高的替代低的
        2. 不同目标 → 新关系替代旧关系（记录历史）

        Args:
            source: 源实体 slug
            target: 目标实体 slug
            relation_type: 关系类型
            confidence: 置信度
            source_memory_id: 来源记忆 ID
            replacement_reason: 替代原因

        Returns:
            新关系对象
        """
        import uuid

        now = datetime.now().isoformat()
        table = self._get_relations_table()

        # 检查是否已存在相同类型的关系
        existing_relations = table.search().where(
            f"source_slug = '{source}' AND relation_type = '{relation_type}'"
        ).limit(10).to_list()

        existing = existing_relations[0] if existing_relations else None

        if existing:
            # 关系已存在
            # 检查是否是相同目标
            if existing.get("target_slug") == target:
                # 相同目标，比较置信度
                if confidence > existing.get("confidence", 0):
                    # 新关系置信度更高，更新（删除后重新插入）
                    old_id = existing.get("id", "")
                    table.delete(f"id = '{old_id}'")

                    updated_relation = Relation.from_dict(existing)
                    updated_relation.confidence = confidence
                    updated_relation.source_memory_id = source_memory_id
                    updated_relation.updated_at = now
                    updated_relation.version = existing.get("version", 1) + 1
                    updated_relation.old_confidence = existing.get("confidence", 0)
                    updated_relation.replacement_reason = replacement_reason

                    table.add([updated_relation.to_dict()])
                    return updated_relation
                else:
                    # 新关系置信度低，不更新
                    return Relation.from_dict(existing)
            else:
                # 不同目标，需要替代旧关系
                old_confidence = existing.get("confidence", 0)
                old_id = existing.get("id", "")

                # 删除旧关系
                table.delete(f"id = '{old_id}'")

                # 更新旧关系状态（作为 SUPERSEDED 记录保留）
                superseded_relation = Relation.from_dict(existing)
                superseded_relation.status = "SUPERSEDED"
                superseded_relation.is_current = False
                superseded_relation.superseded_by = f"NEW:{now}"
                superseded_relation.supersedes_target = target
                superseded_relation.old_confidence = old_confidence
                superseded_relation.replacement_reason = replacement_reason
                superseded_relation.updated_at = now
                superseded_relation.version = existing.get("version", 1) + 1

                # 重新插入 SUPERSEDED 关系
                table.add([superseded_relation.to_dict()])

                # 创建新关系
                new_id = str(uuid.uuid4())[:8]
                relation = Relation(
                    id=new_id,
                    source_slug=source,
                    target_slug=target,
                    relation_type=relation_type,
                    confidence=confidence,
                    source_memory_id=source_memory_id,
                    created_at=now,
                    updated_at=now,
                    version=existing.get("version", 1) + 1,
                    status="ACTIVE",
                    is_current=True,
                    superseded_by="",
                    supersedes_target="",
                    old_confidence=old_confidence,
                    replacement_reason=replacement_reason,
                )
                table.add([relation.to_dict()])
                return relation
        else:
            # 新关系，直接创建
            relation_id = str(uuid.uuid4())[:8]
            relation = Relation(
                id=relation_id,
                source_slug=source,
                target_slug=target,
                relation_type=relation_type,
                confidence=confidence,
                source_memory_id=source_memory_id,
                created_at=now,
                updated_at=now,
                version=1,
                status="ACTIVE",
                is_current=True,
                superseded_by="",
                supersedes_target="",
                old_confidence=0.0,
                replacement_reason="",
            )
            table.add([relation.to_dict()])
            return relation

    def get_entity_current_relations(self, entity_slug: str) -> List[Dict]:
        """
        获取实体的所有当前关系（is_current=True）

        Args:
            entity_slug: 实体 slug

        Returns:
            当前关系列表
        """
        table = self._get_relations_table()

        # 查询作为源且为当前的关系
        rows = table.search().where(
            f"source_slug = '{entity_slug}' AND is_current = true"
        ).limit(100).to_list()
        return rows

    def get_relation_history(self, source: str, relation_type: str) -> List[Dict]:
        """
        获取指定源实体和关系类型的历史记录

        Args:
            source: 源实体 slug
            relation_type: 关系类型

        Returns:
            历史关系列表
        """
        table = self._get_relations_table()

        # 查询所有匹配的关系
        rows = table.search().where(
            f"source_slug = '{source}' AND relation_type = '{relation_type}'"
        ).limit(50).to_list()

        # 按更新时间倒序排列
        rows.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return rows

    def batch_update_relations(
        self,
        updates: List[Dict],
    ) -> List[Dict]:
        """
        批量更新关系

        Args:
            updates: 更新列表，每个元素包含 source, target, relation_type, confidence

        Returns:
            更新结果列表
        """
        results = []

        for update in updates:
            try:
                result = {
                    "relation": self.create_or_replace_relation(
                        source=update.get("source"),
                        target=update.get("target"),
                        relation_type=update.get("relation_type"),
                        confidence=update.get("confidence", 1.0),
                        source_memory_id=update.get("source_memory_id", ""),
                        replacement_reason=update.get("replacement_reason", "batch_update"),
                    ),
                    "success": True
                }
            except Exception as e:
                result = {
                    "relation": None,
                    "success": False,
                    "error": str(e)
                }
            results.append(result)

        return results

    def delete_entity_relations(
        self,
        entity_slug: str,
        relation_type: str = None,
    ) -> bool:
        """
        删除实体的关系

        Args:
            entity_slug: 实体 slug
            relation_type: 关系类型（可选，如果为空则删除所有关系）

        Returns:
            是否删除成功
        """
        table = self._get_relations_table()

        if relation_type:
            # 删除特定类型的关系
            table.delete(f"source_slug = '{entity_slug}' AND relation_type = '{relation_type}'")
        else:
            # 删除所有关系
            table.delete(f"source_slug = '{entity_slug}'")

        return True

    # ==================== 辅助方法 ====================
    
    def get_entity_memories(self, entity_slug: str, limit: int = 50) -> List[Memory]:
        """
        获取与实体相关的所有记忆
        
        Args:
            entity_slug: 实体标识
            limit: 返回数量限制
            
        Returns:
            记忆列表
        """
        return self.list_memories(entity=entity_slug, limit=limit)
    
    def get_entity_relations(self, entity_slug: str, limit: int = 50) -> List[Relation]:
        """
        获取与实体相关的所有关系（作为源或目标）

        Args:
            entity_slug: 实体标识
            limit: 返回数量限制

        Returns:
            关系列表
        """
        table = self._get_relations_table()

        # 查询作为源或目标的关系
        rows = table.search().where(f"source_slug = '{entity_slug}' OR target_slug = '{entity_slug}'").limit(limit).to_list()

        relations = []
        for row in rows:  # row 已经是字典
            data = row
            relations.append(Relation.from_dict(data))
        
        return relations


# ==================== 便捷函数 ====================

# 默认 CRUD 实例
_crud: Optional[MemoryCRUD] = None


def get_crud() -> MemoryCRUD:
    """获取默认 CRUD 实例"""
    global _crud
    if _crud is None:
        _crud = MemoryCRUD()
    return _crud


def set_crud(crud: MemoryCRUD):
    """设置默认 CRUD 实例"""
    global _crud
    _crud = crud
