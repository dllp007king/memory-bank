"""
错误记录器

提供错误记录和查找功能，基于 Memory Bank 的 CRUD 和搜索功能。
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict

from .crud import create_fact, get_fact, update_fact, list_facts
from .search import search_facts, SearchResult

logger = logging.getLogger(__name__)

# 错误类型标记
ERROR_KIND = "E"


@dataclass
class ErrorRecord:
    """错误记录"""
    id: str
    error_type: str
    error_message: str
    context: Dict
    solution: str
    resolved: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    resolved_at: Optional[datetime] = None
    entity: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat() if self.created_at else None
        data["resolved_at"] = self.resolved_at.isoformat() if self.resolved_at else None
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ErrorRecord":
        data = dict(data)
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "resolved_at" in data and data["resolved_at"]:
            data["resolved_at"] = datetime.fromisoformat(data["resolved_at"])
        return cls(**data)

    @classmethod
    def from_fact(cls, fact) -> "ErrorRecord":
        """从 Fact 对象转换"""
        # 解析 content: 格式为 "error_type|error_message|solution|resolved|entity"
        parts = fact.content.split("|")
        error_type = parts[0] if len(parts) > 0 else ""
        error_message = parts[1] if len(parts) > 1 else ""
        solution = parts[2] if len(parts) > 2 else ""
        resolved = parts[3].lower() == "true" if len(parts) > 3 else False
        entity = parts[4] if len(parts) > 4 else ""

        # 解析 context
        context = {}
        for ent in fact.entities:
            if ent.startswith("ctx:"):
                try:
                    context = json.loads(ent[4:])
                except json.JSONDecodeError:
                    pass

        return cls(
            id=fact.id,
            error_type=error_type,
            error_message=error_message,
            context=context,
            solution=solution,
            resolved=resolved,
            created_at=fact.created_at,
            resolved_at=fact.updated_at if resolved else None,
            entity=entity,
        )

    def to_content(self) -> str:
        """转换为存储格式"""
        # 格式: error_type|error_message|solution|resolved|entity
        resolved_str = "true" if self.resolved else "false"
        parts = [
            self.error_type,
            self.error_message,
            self.solution,
            resolved_str,
            self.entity,
        ]
        return "|".join(parts)


class ErrorRecorder:
    """错误记录器"""

    def __init__(self, db=None):
        """
        初始化错误记录器
        
        Args:
            db: 数据库实例（可选，默认使用全局实例）
        """
        self._db = db
        self._embedding_available = self._check_embedding()

    def _check_embedding(self) -> bool:
        """检查 embedding 是否可用"""
        try:
            # 尝试导入 embedding 模块
            from . import embedding
            return True
        except ImportError:
            return False

    @property
    def db(self):
        """获取数据库实例"""
        if self._db is None:
            from .crud import get_db
            return get_db()
        return self._db

    def record_error(
        self,
        error_type: str,
        error_message: str,
        context: Dict,
        solution: str = "",
        entity: str = "",
    ) -> str:
        """
        记录错误

        Args:
            error_type: 错误类型
            error_message: 错误信息
            context: 上下文（操作、参数等）
            solution: 解决方案（如果已知）
            entity: 相关实体

        Returns:
            错误记录的 fact_id
        """
        # 构建 content
        error_record = ErrorRecord(
            id="",
            error_type=error_type,
            error_message=error_message,
            context=context,
            solution=solution,
            resolved=bool(solution),
            resolved_at=datetime.now() if solution else None,
            entity=entity,
        )

        # 创建实体列表（包含上下文）
        entities = []
        if entity:
            entities.append(entity)
        
        # 将 context 编码为实体标记
        if context:
            try:
                ctx_json = json.dumps(context, ensure_ascii=False)
                entities.append(f"ctx:{ctx_json}")
            except (TypeError, ValueError):
                logger.warning(f"Failed to serialize context: {context}")

        # 创建事实
        fact = create_fact(
            content=error_record.to_content(),
            kind=ERROR_KIND,
            entities=entities,
            confidence=1.0,
            db=self.db,
        )

        logger.info(f"Recorded error: {error_type} - {error_message[:50]}... (id: {fact.id})")
        return fact.id

    def find_similar_errors(
        self,
        error_message: str,
        limit: int = 5,
    ) -> List[ErrorRecord]:
        """
        查找类似错误

        使用 BM25 全文搜索查找相似的错误记录。

        Args:
            error_message: 错误信息关键词
            limit: 返回结果数量

        Returns:
            类似的错误记录列表
        """
        # 搜索错误类型
        results = search_facts(
            query=f"{ERROR_KIND} {error_message}",
            limit=limit,
            db=self.db,
        )

        # 过滤只保留错误类型
        error_records = []
        for result in results:
            if result.fact.kind == ERROR_KIND:
                error_records.append(ErrorRecord.from_fact(result.fact))

        return error_records[:limit]

    def get_solution(self, error_id: str) -> Optional[str]:
        """
        获取错误解决方案

        Args:
            error_id: 错误记录 ID

        Returns:
            解决方案文本，如果不存在返回 None
        """
        fact = get_fact(error_id, db=self.db)
        if fact is None:
            return None

        if fact.kind != ERROR_KIND:
            return None

        error_record = ErrorRecord.from_fact(fact)
        return error_record.solution if error_record.solution else None

    def update_solution(self, error_id: str, solution: str) -> bool:
        """
        更新错误解决方案

        Args:
            error_id: 错误记录 ID
            solution: 解决方案

        Returns:
            是否更新成功
        """
        fact = get_fact(error_id, db=self.db)
        if fact is None or fact.kind != ERROR_KIND:
            return False

        # 解析现有 content
        error_record = ErrorRecord.from_fact(fact)
        error_record.solution = solution
        error_record.resolved = True
        error_record.resolved_at = datetime.now()

        # 更新事实
        updated = update_fact(
            error_id,
            content=error_record.to_content(),
            db=self.db,
        )

        logger.info(f"Updated solution for error {error_id}")
        return updated is not None

    def list_errors(
        self,
        error_type: Optional[str] = None,
        resolved: Optional[bool] = None,
        limit: int = 100,
    ) -> List[ErrorRecord]:
        """
        列出错误记录

        Args:
            error_type: 错误类型过滤（可选）
            resolved: 是否已解决过滤（可选）
            limit: 返回结果数量

        Returns:
            错误记录列表
        """
        # 列出所有错误类型的事实
        facts = list_facts(
            kind=ERROR_KIND,
            limit=limit,
            db=self.db,
        )

        error_records = [ErrorRecord.from_fact(fact) for fact in facts]

        # 过滤
        if error_type:
            error_records = [r for r in error_records if r.error_type == error_type]
        if resolved is not None:
            error_records = [r for r in error_records if r.resolved == resolved]

        return error_records

    def mark_resolved(self, error_id: str, solution: str = "") -> bool:
        """
        标记错误为已解决

        Args:
            error_id: 错误记录 ID
            solution: 解决方案（可选）

        Returns:
            是否标记成功
        """
        return self.update_solution(error_id, solution)

    def get_error(self, error_id: str) -> Optional[ErrorRecord]:
        """
        获取单个错误记录

        Args:
            error_id: 错误记录 ID

        Returns:
            错误记录，如果不存在返回 None
        """
        fact = get_fact(error_id, db=self.db)
        if fact is None or fact.kind != ERROR_KIND:
            return None

        return ErrorRecord.from_fact(fact)


# 默认实例
_default_recorder: Optional[ErrorRecorder] = None


def get_recorder() -> ErrorRecorder:
    """获取默认错误记录器实例"""
    global _default_recorder
    if _default_recorder is None:
        _default_recorder = ErrorRecorder()
    return _default_recorder
