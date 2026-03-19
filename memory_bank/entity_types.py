"""
实体类型定义

支持丰富的实体属性，而不仅仅是字符串列表。
"""

from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class EntityRef:
    """
    实体引用（在记忆中使用）

    替代简单的 ["A", "B"] 格式
    """
    slug: str  # 唯一标识
    name: str  # 显示名称
    entity_type: str  # 实体类型
    confidence: float = 1.0  # 提及置信度
    role: Optional[str] = None  # 在记忆中的角色（主语/宾语等）
    mention_count: int = 1  # 提及次数

    def to_string(self) -> str:
        """转换为字符串（用于兼容）"""
        return self.slug

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "slug": self.slug,
            "name": self.name,
            "entity_type": self.entity_type,
            "confidence": self.confidence,
            "role": self.role,
            "mention_count": self.mention_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "EntityRef":
        """从字典创建"""
        return cls(
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            entity_type=data.get("entity_type", "PERSON"),
            confidence=data.get("confidence", 1.0),
            role=data.get("role"),
            mention_count=data.get("mention_count", 1),
        )

    @classmethod
    def from_string(cls, entity_string: str) -> "EntityRef":
        """从字符串创建（兼容旧格式）"""
        # 尝试解析为 JSON 格式
        if "{" in entity_string:
            import json
            try:
                data = json.loads(entity_string)
                return cls.from_dict(data)
            except:
                pass
        # 简单字符串格式
        return cls(
            slug=entity_string,
            name=entity_string,
            entity_type="PERSON",
        )


@dataclass
class RelationRef:
    """
    关系引用

    格式: "A|喜欢|B" 或对象格式
    """
    source: str  # 源实体 slug
    target: str  # 目标实体 slug
    relation_type: str  # 关系类型
    description: Optional[str] = None  # 关系描述
    confidence: float = 1.0  # 置信度

    def to_string(self) -> str:
        """转换为简化字符串格式"""
        return f"{self.source}|{self.relation_type}|{self.target}"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "source": self.source,
            "target": self.target,
            "relation_type": self.relation_type,
            "description": self.description,
            "confidence": self.confidence,
        }

    @classmethod
    def from_string(cls, relation_string: str) -> "RelationRef":
        """从简化字符串格式创建"""
        parts = relation_string.split("|")
        if len(parts) >= 3:
            return cls(
                source=parts[0].strip(),
                relation_type=parts[1].strip(),
                target=parts[2].strip(),
            )
        # 回退：尝试其他格式
        return cls(
            source=relation_string,
            relation_type="RELATED_TO",
            target="",
        )

    @classmethod
    def from_dict(cls, data: dict) -> "RelationRef":
        """从字典创建"""
        return cls(
            source=data.get("from", data.get("source", "")),
            target=data.get("to", data.get("target", "")),
            relation_type=data.get("rel", data.get("relation_type", "RELATED_TO")),
            description=data.get("description"),
            confidence=data.get("confidence", 1.0),
        )


# 实体角色常量
class EntityRole:
    """实体在记忆中的角色"""
    # 基础角色
    SUBJECT = "subject"      # 主语（主动者）
    OBJECT = "object"        # 宾语（被动者）

    # 论元角色
    POSSESSOR = "possessor"  # 领有者（的）
    PART_OF = "part_of"      # 整体的一部分

    # 关系角色
    ACTOR = "actor"          # 行动者
    PATIENT = "patient"        # 接受者
    BENEFICIARY = "beneficiary"  # 受益者
    EXPERIENCER = "experiencer"  # 体验者

    # 交际角色
    SPEAKER = "speaker"      # 说话者
    ADDRESSEE = "addressee"  # 听话对象
    OBSERVER = "observer"    # 观察者

    # 信息角色
    TOPIC = "topic"          # 话题对象
    MENTIONED = "mentioned"  # 被提及
    REFERENCED = "referenced"  # 被引用


# 角色的中文名称映射
ENTITY_ROLE_NAMES = {
    "subject": "主语",
    "object": "宾语",
    "possessor": "领有者",
    "part_of": "整体的一部分",
    "actor": "行动者",
    "patient": "接受者",
    "beneficiary": "受益者",
    "experiencer": "体验者",
    "speaker": "说话者",
    "addressee": "对话对象",
    "observer": "观察者",
    "topic": "话题对象",
    "mentioned": "被提及",
    "referenced": "被引用",
}


# 实体类型常量（统一来源）
class EntityType:
    """
    实体类型常量
    
    所有实体类型定义的单一来源，确保前后端一致性。
    """
    # 核心类型
    PERSON = "PERSON"      # 人物
    ORG = "ORG"            # 组织（别名：ORGANIZATION）
    PLACE = "PLACE"        # 地点
    EVENT = "EVENT"        # 事件
    CONCEPT = "CONCEPT"    # 概念
    
    # 扩展类型（实际使用中）
    TOOL = "TOOL"          # 工具（vscode, git, docker 等）
    SYSTEM = "SYSTEM"      # 系统（linux, server, gateway 等）
    PROJECT = "PROJECT"    # 项目（memory-bank, web-ui 等）
    GAME = "GAME"          # 游戏（魔兽世界 等）
    
    # 其他类型（兼容旧数据）
    TOPIC = "TOPIC"        # 主题
    PRODUCT = "PRODUCT"    # 产品
    DOCUMENT = "DOCUMENT"  # 文档
    CREDENTIAL = "CREDENTIAL"  # 凭证/密钥
    SCRIPT = "SCRIPT"      # 脚本
    DATABASE = "DATABASE"  # 数据库


# 实体类型的中文名称映射
ENTITY_TYPE_NAMES = {
    "PERSON": "人物",
    "ORG": "组织",
    "ORGANIZATION": "组织",
    "PLACE": "地点",
    "EVENT": "事件",
    "CONCEPT": "概念",
    "TOOL": "工具",
    "SYSTEM": "系统",
    "PROJECT": "项目",
    "GAME": "游戏",
    "TOPIC": "主题",
    "PRODUCT": "产品",
    "DOCUMENT": "文档",
    "CREDENTIAL": "凭证",
    "SCRIPT": "脚本",
    "DATABASE": "数据库",
}


# 实体类型颜色配置（供前端使用）
ENTITY_TYPE_COLORS = {
    "PERSON": "#3b82f6",   # 蓝色
    "ORG": "#22c55e",      # 绿色
    "PLACE": "#f59e0b",    # 橙色
    "TOOL": "#8b5cf6",     # 紫色
    "SYSTEM": "#ec4899",   # 粉色
    "PROJECT": "#06b6d4",  # 青色
    "CONCEPT": "#6366f1",  # 靛蓝色
    "EVENT": "#ef4444",    # 红色
    "GAME": "#84cc16",     # 黄绿色
    "DOCUMENT": "#14b8a6", # 青绿色
    "DATABASE": "#f97316", # 橙红色
    "SCRIPT": "#a855f7",   # 紫罗兰色
    "CREDENTIAL": "#dc2626", # 深红色
}


# 实体类型图标（供前端使用）
ENTITY_TYPE_ICONS = {
    "PERSON": "👤",
    "ORG": "🏢",
    "PLACE": "📍",
    "TOOL": "🔧",
    "SYSTEM": "⚙️",
    "PROJECT": "📁",
    "CONCEPT": "💡",
    "EVENT": "🎯",
    "GAME": "🎮",
    "DOCUMENT": "📄",
    "DATABASE": "🗄️",
    "SCRIPT": "📜",
    "CREDENTIAL": "🔑",
}


# 关系类型常量
class RelationType:
    KNOWS = "KNOWS"              # 认识
    LIKES = "LIKES"              # 喜欢
    LOVES = "LOVES"              # 爱
    HATES = "HATES"              # 憎恨
    WORKS_WITH = "WORKS_WITH"    # 共事
    WORKS_AT = "WORKS_AT"        # 工作于
    RELATED_TO = "RELATED_TO"    # 相关
    LOCATED_AT = "LOCATED_AT"    # 位于
    PART_OF = "PART_OF"          # 属于
    MANAGES = "MANAGES"          # 管理
    CREATED = "CREATED"          # 创建
    MENTIONS = "MENTIONS"        # 提及
    REPORTS_TO = "REPORTS_TO"    # 汇报给
    WORKS_ON = "WORKS_ON"        # 参与项目
    INVESTED_BY = "INVESTED_BY"  # 被投资
    FRIENDS_WITH = "FRIENDS_WITH"  # 友好
    ENEMIES_WITH = "ENEMIES_WITH"  # 敌对
    MANAGED_BY = "MANAGED_BY"      # 被管理
    MARRIED_TO = "MARRIED_TO"    # 结婚
    ENGAGED_TO = "ENGAGED_TO"    # 订婚
    FORMERLY_MARRIED = "FORMERLY_MARRIED"  # 曾婚


# 关系类型的中文名称映射
RELATION_TYPE_NAMES = {
    "KNOWS": "认识",
    "LIKES": "喜欢",
    "LOVES": "爱",
    "HATES": "恨",
    "WORKS_WITH": "共事",
    "WORKS_AT": "工作于",
    "RELATED_TO": "相关",
    "LOCATED_AT": "位于",
    "PART_OF": "属于",
    "MANAGES": "管理",
    "CREATED": "创建",
    "MENTIONS": "提及",
    "REPORTS_TO": "汇报给",
    "WORKS_ON": "参与",
    "INVESTED_BY": "被投资",
    "FRIENDS_WITH": "友好",
    "ENEMIES_WITH": "敌对",
    "MANAGED_BY": "被管理",
    "MARRIED_TO": "结婚",
    "ENGAGED_TO": "订婚",
    "FORMERLY_MARRIED": "曾婚",
}

# 实体类型的中文名称映射（已移动到 EntityType 类后面）
# 见上方 ENTITY_TYPE_NAMES 定义
