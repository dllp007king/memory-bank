"""
Memory Bank - OpenClaw 长期记忆系统

提供基于 LanceDB 的向量存储、实体管理和混合搜索功能。
v2.1: 移除 SQLite 遗留代码，完全使用 LanceDB
"""

# LanceDB 模块
from .lance import LanceConnection
from .lance_crud import MemoryCRUD, get_crud, set_crud, Relation, Entity
from .lance_search import MemorySearch, get_searcher
from .slug_generator import generate_slug, parse_slug, get_entity_type_from_slug
from .models import Fact, FactKind

# 向量嵌入
from .embedding import (
    EmbeddingConfig,
    get_config as get_embedding_config,
    set_config as set_embedding_config,
    embed_single,
    cosine_similarity,
    check_server_health,
)

# Lifecycle management
from .lifecycle import (
    effective_confidence,
    infer_decay_rate,
    cleanup_priority,
    distill_priority,
    should_keep,
    LifecycleState,
)
from .lance_schema import RelationType, EntityType
from .similarity import (
    calculate_similarity,
    get_update_strategy,
    UpdateStrategy,
    find_similar_memories,
)
from .contradiction import (
    handle_contradiction,
    detect_contradiction,
    ContradictionResolution,
)
from .entity_types import EntityRef, RelationRef, EntityType, RelationType, ENTITY_TYPE_NAMES, RELATION_TYPE_NAMES

__version__ = "2.1.0"
__all__ = [
    # LanceDB
    "LanceConnection",
    "MemoryCRUD",
    "get_crud",
    "set_crud",
    "MemorySearch",
    "get_searcher",
    "Relation",
    "Entity",
    # 模型
    "Fact",
    "FactKind",
    # 实体和关系类型
    "EntityRef",
    "RelationRef",
    "EntityType",
    "RelationType",
    "ENTITY_TYPE_NAMES",
    "RELATION_TYPE_NAMES",
    # Lifecycle
    "effective_confidence",
    "infer_decay_rate",
    "cleanup_priority",
    "distill_priority",
    "should_keep",
    "LifecycleState",
    # 相似度
    "calculate_similarity",
    "get_update_strategy",
    "UpdateStrategy",
    "find_similar_memories",
    # 矛盾处理
    "handle_contradiction",
    "detect_contradiction",
    "ContradictionResolution",
    # 向量化
    "EmbeddingConfig",
    "get_embedding_config",
    "set_embedding_config",
    "embed_single",
    "cosine_similarity",
    "check_server_health",
]
