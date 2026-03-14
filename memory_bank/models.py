"""
数据模型定义
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
import uuid


class FactKind(Enum):
    """事实类型"""
    WORLD = "W"        # 世界事实
    BIO = "B"          # 经验/传记
    OPINION = "O"      # 意见/偏好
    SUMMARY = "S"      # 总结
    WISH = "W"         # 愿望


@dataclass
class Fact:
    """事实记录"""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    kind: str = "W"  # W/B/O/S
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    source_path: str = ""
    source_line: int = 0
    entities: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "source_path": self.source_path,
            "source_line": self.source_line,
            "entities": self.entities,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Fact":
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            kind=data.get("kind", "W"),
            content=data.get("content", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            source_path=data.get("source_path", ""),
            source_line=data.get("source_line", 0),
            entities=data.get("entities", []),
            confidence=data.get("confidence", 1.0),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.now(),
        )


@dataclass
class Entity:
    """实体"""
    slug: str = ""
    name: str = ""
    summary: str = ""
    entity_type: str = "PERSON"
    first_seen: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "slug": self.slug,
            "name": self.name,
            "summary": self.summary,
            "entity_type": self.entity_type,
            "first_seen": self.first_seen.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Entity":
        return cls(
            slug=data.get("slug", ""),
            name=data.get("name", ""),
            summary=data.get("summary", ""),
            entity_type=data.get("entity_type", "PERSON"),
            first_seen=datetime.fromisoformat(data["first_seen"]) if "first_seen" in data else datetime.now(),
            last_updated=datetime.fromisoformat(data["last_updated"]) if "last_updated" in data else datetime.now(),
        )
