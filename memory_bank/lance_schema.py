"""
LanceDB Schema 定义

使用 pyarrow 定义三个核心表的 Schema：
- memories: 记忆/事实表（兼容 SQLite 的 facts 表）
- entities: 实体表
- relations: 关系表（新增）

向量维度: 1536 (OpenAI text-embedding-3-small)
"""

import pyarrow as pa
from typing import Dict, Any


# ============================================================================
# 向量维度配置
# ============================================================================

EMBEDDING_DIM: int = 2560  # 向量维度（GLM-4 embedding）


# ============================================================================
# Memories 表 Schema（兼容 SQLite facts 表）
# ============================================================================

MEMORIES_SCHEMA: pa.Schema = pa.schema([
    # === 原有字段（兼容 SQLite） ===
    
    # 主键 ID
    pa.field("id", pa.string(), nullable=False, metadata={"description": "唯一标识符"}),
    
    # 内容
    pa.field("content", pa.string(), nullable=False, metadata={"description": "记忆内容"}),
    
    # 类型 (W=世界事实, B=经验/传记, O=意见/偏好, S=总结)
    pa.field("kind", pa.string(), nullable=False, metadata={"description": "事实类型: W/B/O/S"}),
    
    # 时间戳
    pa.field("timestamp", pa.timestamp("us"), nullable=False, metadata={"description": "记录时间戳"}),
    
    # 来源信息
    pa.field("source_path", pa.string(), nullable=True, metadata={"description": "来源文件路径"}),
    pa.field("source_line", pa.int32(), nullable=True, metadata={"description": "来源行号"}),
    
    # 置信度
    pa.field("confidence", pa.float32(), nullable=False, metadata={"description": "置信度 0.0-1.0"}),
    
    # 创建和更新时间
    pa.field("created_at", pa.timestamp("us"), nullable=False, metadata={"description": "创建时间"}),
    pa.field("updated_at", pa.timestamp("us"), nullable=False, metadata={"description": "更新时间"}),
    
    # === 新增字段 ===
    
    # 向量嵌入
    pa.field("embedding", pa.list_(pa.float32(), EMBEDDING_DIM), nullable=True, 
             metadata={"description": "向量嵌入 (1536维)"}),
    
    # 关联实体列表（存储 entity slug）
    pa.field("entities", pa.list_(pa.string()), nullable=True, 
             metadata={"description": "关联实体 slug 列表"}),
    
    # 重要性评分
    pa.field("importance", pa.float32(), nullable=True,
             metadata={"description": "重要性评分 0.0-1.0"}),

    # 版本号
    pa.field("version", pa.int32(), nullable=False,
             metadata={"description": "版本号，用于乐观锁"}),

    # 标签列表
    pa.field("tags", pa.list_(pa.string()), nullable=True,
             metadata={"description": "标签列表"}),

    # === Lifecycle Fields (新增) ===

    # 衰减率 (0.0001=恒定, 0.001=长期, 0.01=中期, 0.05=短期, 0.2=即时)
    pa.field("decay_rate", pa.float32(), nullable=True,
             metadata={"description": "衰减率 0.0001-0.2"}),

    # 生命周期状态
    pa.field("lifecycle_state", pa.string(), nullable=True,
             metadata={"description": "状态: ACTIVE/ARCHIVED/SUPERSEDED/FORGOTTEN"}),

    # 被哪条记忆取代
    pa.field("superseded_by", pa.string(), nullable=True,
             metadata={"description": "取代此记忆的新记忆ID"}),

    # 访问统计
    pa.field("access_count", pa.int32(), nullable=False,
             metadata={"description": "访问次数"}),
    pa.field("last_accessed_at", pa.timestamp("us"), nullable=True,
             metadata={"description": "最后访问时间"}),
])

# Memories 表名
MEMORIES_TABLE_NAME: str = "memories"


# ============================================================================
# Entities 表 Schema
# ============================================================================

ENTITIES_SCHEMA: pa.Schema = pa.schema([
    # === 原有字段（兼容 SQLite） ===
    
    # 主键（唯一标识符）
    pa.field("slug", pa.string(), nullable=False, metadata={"description": "实体唯一标识符"}),
    
    # 名称
    pa.field("name", pa.string(), nullable=False, metadata={"description": "实体名称"}),
    
    # 摘要
    pa.field("summary", pa.string(), nullable=True, metadata={"description": "实体摘要"}),
    
    # 实体类型 (PERSON, PLACE, ORG, etc.)
    pa.field("entity_type", pa.string(), nullable=False, metadata={"description": "实体类型"}),
    
    # 首次和最后更新时间
    pa.field("first_seen", pa.timestamp("us"), nullable=False, metadata={"description": "首次出现时间"}),
    pa.field("last_updated", pa.timestamp("us"), nullable=False, metadata={"description": "最后更新时间"}),
    
    # === 新增字段 ===
    
    # 向量嵌入
    pa.field("embedding", pa.list_(pa.float32(), EMBEDDING_DIM), nullable=True, 
             metadata={"description": "实体名称的向量嵌入 (1536维)"}),
    
    # 别名列表
    pa.field("aliases", pa.list_(pa.string()), nullable=True, 
             metadata={"description": "实体别名列表"}),
    
    # 标签列表
    pa.field("tags", pa.list_(pa.string()), nullable=True, 
             metadata={"description": "标签列表"}),
    
    # 版本号
    pa.field("version", pa.int32(), nullable=False, 
             metadata={"description": "版本号，用于乐观锁"}),
    
    # 关联记忆数量
    pa.field("memory_count", pa.int32(), nullable=True, 
             metadata={"description": "关联的记忆数量"}),
    
    # 重要性评分
    pa.field("importance", pa.float32(), nullable=True, 
             metadata={"description": "重要性评分 0.0-1.0"}),
])

# Entities 表名
ENTITIES_TABLE_NAME: str = "entities"


# ============================================================================
# Relations 表 Schema（新增）
# ============================================================================

RELATIONS_SCHEMA: pa.Schema = pa.schema([
    # 主键 ID
    pa.field("id", pa.string(), nullable=False, metadata={"description": "关系唯一标识符"}),
    
    # 源实体
    pa.field("source_slug", pa.string(), nullable=False, 
             metadata={"description": "源实体 slug"}),
    
    # 目标实体
    pa.field("target_slug", pa.string(), nullable=False, 
             metadata={"description": "目标实体 slug"}),
    
    # 关系类型
    pa.field("relation_type", pa.string(), nullable=False, 
             metadata={"description": "关系类型: KNOWS/WORKS_WITH/RELATED_TO/etc."}),
    
    # 关系描述
    pa.field("description", pa.string(), nullable=True, 
             metadata={"description": "关系描述"}),
    
    # 置信度
    pa.field("confidence", pa.float32(), nullable=False, 
             metadata={"description": "置信度 0.0-1.0"}),
    
    # 来源记忆 ID
    pa.field("source_memory_id", pa.string(), nullable=True, 
             metadata={"description": "提取此关系的来源记忆 ID"}),
    
    # === 时间字段 ===
    
    pa.field("created_at", pa.timestamp("us"), nullable=False, metadata={"description": "创建时间"}),
    pa.field("updated_at", pa.timestamp("us"), nullable=False, metadata={"description": "更新时间"}),
    
    # === 新增字段 ===
    
    # 版本号
    pa.field("version", pa.int32(), nullable=False,
             metadata={"description": "版本号，用于乐观锁"}),

    # 标签列表
    pa.field("tags", pa.list_(pa.string()), nullable=True,
             metadata={"description": "标签列表"}),

    # === Relation History Tracking Fields (新增) ===

    # 生命周期状态
    pa.field("status", pa.string(), nullable=False,
             metadata={"description": "状态: ACTIVE/SUPERSEDED/ARCHIVED/FORGOTTEN"}),

    # 是否当前关系
    pa.field("is_current", pa.bool_(), nullable=False,
             metadata={"description": "是否为当前有效关系"}),

    # 被哪个关系取代
    pa.field("superseded_by", pa.string(), nullable=True,
             metadata={"description": "取代此关系的新关系ID"}),

    # 替代的目标实体
    pa.field("supersedes_target", pa.string(), nullable=True,
             metadata={"description": "此关系替代的目标实体slug"}),

    # 替代前的置信度
    pa.field("old_confidence", pa.float32(), nullable=True,
             metadata={"description": "被替代前的置信度"}),

    # 替代原因
    pa.field("replacement_reason", pa.string(), nullable=True,
             metadata={"description": "替代原因"}),
])

# Relations 表名
RELATIONS_TABLE_NAME: str = "relations"


# ============================================================================
# 辅助函数
# ============================================================================

def get_all_schemas() -> Dict[str, pa.Schema]:
    """
    获取所有表的 Schema 映射
    
    Returns:
        表名到 Schema 的映射字典
    """
    return {
        MEMORIES_TABLE_NAME: MEMORIES_SCHEMA,
        ENTITIES_TABLE_NAME: ENTITIES_SCHEMA,
        RELATIONS_TABLE_NAME: RELATIONS_SCHEMA,
    }


def get_schema_fields_info(schema: pa.Schema) -> str:
    """
    获取 Schema 的字段信息描述
    
    Args:
        schema: pyarrow Schema 对象
        
    Returns:
        格式化的字段信息字符串
    """
    lines = []
    for field in schema:
        nullable = "可空" if field.nullable else "非空"
        desc = field.metadata.get(b"description", b"").decode("utf-8") if field.metadata else ""
        lines.append(f"  - {field.name}: {field.type} ({nullable}) - {desc}")
    return "\n".join(lines)


def print_schema_summary() -> None:
    """打印所有 Schema 的摘要信息"""
    print("=" * 60)
    print("LanceDB Schema 摘要")
    print("=" * 60)
    print(f"向量维度: {EMBEDDING_DIM}")
    print()
    
    for table_name, schema in get_all_schemas().items():
        print(f"表: {table_name}")
        print(f"字段数: {len(schema)}")
        print("字段列表:")
        print(get_schema_fields_info(schema))
        print()


# ============================================================================
# 关系类型常量
# ============================================================================

class RelationType:
    """关系类型常量"""
    KNOWS = "KNOWS"              # 认识
    WORKS_WITH = "WORKS_WITH"    # 共事
    RELATED_TO = "RELATED_TO"    # 相关
    LOCATED_AT = "LOCATED_AT"    # 位于
    PART_OF = "PART_OF"          # 属于
    MANAGES = "MANAGES"          # 管理
    CREATED = "CREATED"          # 创建
    MENTIONS = "MENTIONS"        # 提及
    WORKS_AT = "WORKS_AT"        # 工作于
    REPORTS_TO = "REPORTS_TO"    # 汇报给
    WORKS_ON = "WORKS_ON"        # 参与项目
    INVESTED_BY = "INVESTED_BY"  # 被投资
    FRIENDS_WITH = "FRIENDS_WITH"  # 友好关系
    ENEMIES_WITH = "ENEMIES_WITH"  # 敌对关系
    MANAGED_BY = "MANAGED_BY"    # 被管理


# ============================================================================
# 实体类型常量
# ============================================================================

class EntityType:
    """实体类型常量"""
    PERSON = "PERSON"      # 人物
    PLACE = "PLACE"        # 地点
    ORG = "ORG"            # 组织
    EVENT = "EVENT"        # 事件
    TOPIC = "TOPIC"        # 主题
    PRODUCT = "PRODUCT"    # 产品
    CONCEPT = "CONCEPT"    # 概念


if __name__ == "__main__":
    print_schema_summary()
