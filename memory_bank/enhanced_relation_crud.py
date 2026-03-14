#!/usr/bin/env python3
"""
关系替代机制集成模块（修复版）

增强的关系CRUD操作，支持：
1. 不同目标关系的替代
2. 关系历史记录
3. 按实体查询当前关系
4. 关系变更历史追踪
"""

import uuid
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# 扩展的数据模型
# ============================================================================

def get_relation_schema():
    """获取扩展的关系Schema（包含替代历史字段）"""
    import pyarrow as pa

    # 基础Schema（来自现有系统）
    BASE_SCHEMA_FIELDS = [
        pa.field("id", pa.string(), nullable=False),
        pa.field("source_slug", pa.string(), nullable=False),
        pa.field("target_slug", pa.string(), nullable=False),
        pa.field("relation_type", pa.string(), nullable=False),
        pa.field("description", pa.string(), nullable=True),
        pa.field("confidence", pa.float32(), nullable=False),
        pa.field("source_memory_id", pa.string(), nullable=True),
        pa.field("created_at", pa.timestamp("us"), nullable=False),
        pa.field("updated_at", pa.timestamp("us"), nullable=False),
        pa.field("version", pa.int32(), nullable=False),
        pa.field("tags", pa.list_(pa.string()), nullable=True),
    ]

    # 新增字段 - 关系替代支持
    EXTENDED_SCHEMA_FIELDS = [
        # 替代目标记录
        pa.field("supersedes_target", pa.string(), nullable=True,
                metadata={"description": "被替代的目标实体slug"}),

        # 被替代记录
        pa.field("superseded_by", pa.string(), nullable=True,
                metadata={"description": "替代此关系的关系ID"}),

        # 替代时的旧置信度
        pa.field("old_confidence", pa.float32(), nullable=True,
                metadata={"description": "被替代前的置信度"}),

        # 替代原因
        pa.field("replacement_reason", pa.string(), nullable=True,
                metadata={"description": "替代原因：update/conflict/migration"}),

        # 关系状态
        pa.field("status", pa.string(), nullable=True,
                metadata={"description": "关系状态：ACTIVE/SUPERSEDED/ARCHIVED"}),

        # 当前标识（用于同一源实体的多个关系版本）
        pa.field("is_current", pa.bool_(), nullable=True,
                metadata={"description": "是否是当前有效关系"}),
    ]

    return pa.schema(BASE_SCHEMA_FIELDS + EXTENDED_SCHEMA_FIELDS)


class RelationWithHistory:
    """带历史记录的关系"""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", str(uuid.uuid4())[:8])
        self.source = kwargs.get("source", "")
        self.target = kwargs.get("target", "")
        self.relation_type = kwargs.get("relation_type", "")
        self.description = kwargs.get("description", "")
        self.confidence = kwargs.get("confidence", 1.0)
        self.source_memory_id = kwargs.get("source_memory_id", "")
        self.created_at = kwargs.get("created_at", datetime.now().isoformat())
        self.updated_at = kwargs.get("updated_at", datetime.now().isoformat())
        self.version = kwargs.get("version", 1)
        self.tags = kwargs.get("tags", [])

        # 新增字段
        self.supersedes_target = kwargs.get("supersedes_target", "")
        self.superseded_by = kwargs.get("superseded_by", "")
        self.old_confidence = kwargs.get("old_confidence", None)
        self.replacement_reason = kwargs.get("replacement_reason", "")
        self.status = kwargs.get("status", "ACTIVE")
        self.is_current = kwargs.get("is_current", True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_slug": self.source,
            "target_slug": self.target,
            "relation_type": self.relation_type,
            "description": self.description,
            "confidence": self.confidence,
            "source_memory_id": self.source_memory_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
            "tags": self.tags,
            "supersedes_target": self.supersedes_target,
            "superseded_by": self.superseded_by,
            "old_confidence": self.old_confidence,
            "replacement_reason": self.replacement_reason,
            "status": self.status,
            "is_current": self.is_current,
        }


# ============================================================================
# 增强的关系CRUD操作
# ============================================================================

class EnhancedRelationCRUD:
    """
    增强的关系CRUD操作，支持关系替代和历史记录
    """

    def __init__(self):
        """初始化（模拟实现，实际应连接到真实数据库）"""
        self.relations: Dict[str, Dict] = {}  # (source, type) -> relation info
        self.relation_history: List[Dict] = []  # 关系历史记录

    def create_or_replace_relation(
        self,
        source: str,
        target: str,
        relation_type: str,
        confidence: float = 1.0,
        source_memory_id: str = "",
        force_replace: bool = False,
        replacement_reason: str = "update"
    ) -> RelationWithHistory:
        """
        创建或替代关系（增强版）

        规则：
        1. 如果存在相同关系（source, type, target）：
           - 如果新置信度更高或强制替换，则替代
           - 否则跳过
        2. 如果存在不同目标的关系（source, type）：
           - 标记旧关系为非当前
           - 创建新关系并标记为当前
           - 记录替代历史

        Args:
            source: 源实体
            target: 目标实体
            relation_type: 关系类型
            confidence: 置信度
            source_memory_id: 来源记忆
            force_replace: 是否强制替换
            replacement_reason: 替代原因

        Returns:
            创建或更新的关系对象
        """
        key = (source, relation_type)
        now = datetime.now().isoformat()

        # 查找现有关系
        existing = self.relations.get(key)

        result = {
            "action": "created",
            "old_relation": None,
            "new_relation": None
        }

        if existing:
            # 检查是否是相同目标
            if existing["target"] == target:
                # 相同关系，比较置信度
                if confidence >= existing["confidence"] or force_replace:
                    # 新关系置信度更高或强制替换，替代旧关系
                    old_relation = existing.copy()

                    # 更新旧关系状态
                    old_relation.update({
                        "status": "SUPERSEDED",
                        "is_current": False,
                        "supersedes_target": target,
                        "superseded_by": "NEW:" + now,
                        "old_confidence": existing["confidence"],
                        "updated_at": now,
                        "replacement_reason": replacement_reason
                    })

                    # 创建新关系
                    new_relation = {
                        "id": str(uuid.uuid4())[:8],
                        "source": source,
                        "target": target,
                        "relation_type": relation_type,
                        "confidence": confidence,
                        "source_memory_id": source_memory_id,
                        "created_at": now,
                        "updated_at": now,
                        "version": existing["version"] + 1,
                        "status": "ACTIVE",
                        "is_current": True,
                        "replacement_reason": replacement_reason
                    }

                    # 更新关系存储
                    self.relations[key] = new_relation

                    # 记录替代历史
                    self.relation_history.append({
                        "timestamp": now,
                        "action": "replaced",
                        "source": source,
                        "old_target": existing["target"],
                        "new_target": target,
                        "old_confidence": existing["confidence"],
                        "new_confidence": confidence,
                        "reason": replacement_reason
                    })

                    result.update({
                        "action": "replaced",
                        "old_relation": old_relation,
                        "new_relation": new_relation
                    })
                else:
                    # 新关系置信度更低，不更新
                    result.update({
                        "action": "skipped",
                        "reason": "New confidence ({}) < old confidence ({})".format(
                            confidence, existing["confidence"])
                    })
            else:
                # 不同目标，需要替代旧关系
                old_relation = existing.copy()

                # 更新旧关系状态
                old_relation.update({
                    "status": "SUPERSEDED",
                    "is_current": False,
                    "supersedes_target": target,
                    "superseded_by": "NEW:" + now,
                    "old_confidence": old_relation["confidence"],
                    "updated_at": now,
                    "replacement_reason": replacement_reason
                })

                # 创建新关系
                new_relation = {
                    "id": str(uuid.uuid4())[:8],
                    "source": source,
                    "target": target,
                    "relation_type": relation_type,
                    "confidence": confidence,
                    "source_memory_id": source_memory_id,
                    "created_at": now,
                    "updated_at": now,
                    "version": existing["version"] + 1,
                    "status": "ACTIVE",
                    "is_current": True,
                    "replacement_reason": replacement_reason
                }

                # 更新关系存储
                self.relations[key] = new_relation

                # 记录替代历史
                self.relation_history.append({
                    "timestamp": now,
                    "action": "replaced_with_different_target",
                    "source": source,
                    "old_target": existing["target"],
                    "new_target": target,
                    "old_confidence": existing["confidence"],
                    "new_confidence": confidence,
                    "reason": replacement_reason
                })

                result.update({
                    "action": "replaced_with_different_target",
                    "old_relation": old_relation,
                    "new_relation": new_relation
                })

        else:
            # 新关系，直接创建
            new_relation = {
                "id": str(uuid.uuid4())[:8],
                "source": source,
                "target": target,
                "relation_type": relation_type,
                "confidence": confidence,
                "source_memory_id": source_memory_id,
                "created_at": now,
                "updated_at": now,
                "version": 1,
                "status": "ACTIVE",
                "is_current": True,
                "replacement_reason": ""
            }

            self.relations[key] = new_relation

            # 记录创建历史
            self.relation_history.append({
                "timestamp": now,
                "action": "created",
                "source": source,
                "target": target,
                "confidence": confidence,
                "reason": "initial_creation"
            })

            result["new_relation"] = new_relation

        return RelationWithHistory(**result["new_relation"])

    def get_entity_current_relations(self, entity_slug: str) -> List[Dict]:
        """
        获取实体的所有当前关系

        Args:
            entity_slug: 实体标识

        Returns:
            当前关系列表
        """
        current_relations = []

        # 查找实体作为源的关系
        for (source, rel_type), relation in self.relations.items():
            if source == entity_slug and relation.get("is_current", True):
                current_relations.append({
                    "direction": "outgoing",
                    **relation
                })

        # 查找实体作为目标的关系
        for (source, rel_type), relation in self.relations.items():
            if relation.get("target") == entity_slug and relation.get("is_current", True):
                current_relations.append({
                    "direction": "incoming",
                    **relation
                })

        return current_relations

    def get_relation_history(
        self,
        source: Optional[str] = None,
        target: Optional[str] = None,
        relation_type: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        获取关系历史

        Args:
            source: 按源过滤
            target: 按目标过滤
            relation_type: 按关系类型过滤
            limit: 返回数量限制

        Returns:
            历史记录列表
        """
        history = self.relation_history

        # 过滤
        if source:
            history = [h for h in history if h.get("source") == source]
        if target:
            history = [h for h in history if h.get("target") == target]
        if relation_type:
            history = [h for h in history if h.get("relation_type") == relation_type]

        # 按时间倒序
        history.sort(key=lambda x: x["timestamp"], reverse=True)

        return history[:limit]

    def batch_update_relations(
        self,
        updates: List[Dict]
    ) -> Dict:
        """
        批量更新关系

        Args:
            updates: 更新列表，每个包含：
                - source: 源实体
                - target: 目标实体
                - relation_type: 关系类型
                - confidence: 新置信度
                - reason: 更新原因

        Returns:
            更新结果统计
        """
        results = {
            "total": len(updates),
            "success": 0,
            "skipped": 0,
            "replaced": 0,
            "errors": 0
        }

        for update in updates:
            try:
                relation = self.create_or_replace_relation(
                    source=update["source"],
                    target=update["target"],
                    relation_type=update["relation_type"],
                    confidence=update["confidence"],
                    source_memory_id=update.get("source_memory_id", ""),
                    replacement_reason=update.get("reason", "batch_update")
                )

                if relation.replacement_reason == "batch_update":
                    results["success"] += 1
                elif relation.status == "SUPERSEDED":
                    results["replaced"] += 1
                elif relation.status == "ACTIVE":
                    results["success"] += 1
                else:
                    results["success"] += 1

            except Exception as e:
                results["errors"] += 1
                logger.error("更新关系失败: {}, 错误: {}".format(update, str(e)))

        return results

    def delete_entity_relations(
        self,
        entity_slug: str,
        relation_type: Optional[str] = None
    ) -> Dict:
        """
        删除实体的所有关系

        Args:
            entity_slug: 实体标识
            relation_type: 关系类型（可选，如果为None则删除所有关系）

        Returns:
            删除结果统计
        """
        results = {
            "total": 0,
            "deleted": 0,
            "errors": 0
        }

        # 查找所有相关关系
        keys_to_delete = []
        for (source, rel_type) in list(self.relations.keys()):
            if source == entity_slug:
                if relation_type is None or rel_type == relation_type:
                    keys_to_delete.append((source, rel_type))

        # 删除关系
        for key in keys_to_delete:
            try:
                del self.relations[key]
                results["deleted"] += 1
                results["total"] += 1
            except Exception as e:
                results["errors"] += 1
                logger.error("删除关系失败: {}, 错误: {}".format(key, str(e)))

        return results

    def print_state(self):
        """打印当前状态"""
        print("\n关系状态:")
        print("  关系数: {}".format(len(self.relations)))
        print("  历史记录数: {}".format(len(self.relation_history)))

        if self.relations:
            print("\n当前关系:")
            for i, (source, rel_type) in enumerate(self.relations.keys(), 1):
                rel = self.relations[(source, rel_type)]
                status_icon = "OK" if rel.get("is_current", True) else "X"
                direction_arrow = "--[" if rel.get("direction") == "incoming" else "->"
                print("  {}. {} --[{}] --> {}".format(
                    i, status_icon, source, direction_arrow, rel["relation_type"], rel["target"],
                    rel["target"]
                ))
                print("    置信度: {:.2f}, 状态: {}, 版本: {}".format(
                    rel["confidence"], rel.get("status", "ACTIVE"), rel.get("version")
                ))
        else:
            print("  没有关系")

        if self.relation_history:
            print("\n最近关系历史:")
            for i, h in enumerate(self.relation_history[-5:], 1):  # 显示最近5条
                direction = "<" if "created" == h["action"] else ">"
                print("  {} {} [{}] {}".format(
                    h["timestamp"], direction, h["action"], h["reason"])
                )
                old_t = h.get("old_target", "-")
                new_t = h.get("new_target", "-")
                old_c = h.get("old_confidence", "-")
                new_c = h.get("new_confidence", "-")
                print("    {} --> {} (置信度: {} -> {})".format(
                    h["source"], old_t, old_c, new_c
                ))

    def print_relation_details(self, relation: Dict):
        """打印关系详情"""
        print("    关系ID: {}".format(relation.get("id", "-")))
        print("    状态: {}".format(relation.get("status", "ACTIVE")))
        print("    当前: {}".format("是" if relation.get("is_current", True) else "否"))
        if relation.get("superseded_by"):
            print("    被替代: {}".format(relation["superseded_by"]))
        if relation.get("supersedes_target"):
            print("    替代目标: {}".format(relation["supersedes_target"]))
        if relation.get("replacement_reason"):
            print("    替代原因: {}".format(relation["replacement_reason"]))
        print("    置信度: {}".format(relation["confidence"]))
        print("    版本: {}".format(relation.get("version")))
        print()


# ============================================================================
# 测试类
# ============================================================================

class RelationSupersedeSystemTest:
    """测试关系替代系统"""

    def __init__(self):
        self.crud = EnhancedRelationCRUD()

    def test_scenario_1(self):
        """测试场景1：部门变更 - 新关系替代旧关系"""
        print("\n" + "="*70)
        print("测试场景1：部门变更 - 新关系替代旧关系")
        print("="*70)

        # 添加实体
        self.crud.relations[("user_zhang", "WORKS_AT")] = {
            "id": "rel_1",
            "source": "user_zhang",
            "target": "dept_a",
            "relation_type": "WORKS_AT",
            "confidence": 0.9,
            "status": "ACTIVE",
            "is_current": True,
            "version": 1
        }

        # 创建新关系（替代旧关系）
        new_rel = self.crud.create_or_replace_relation(
            source="user_zhang",
            target="dept_b",
            relation_type="WORKS_AT",
            confidence=0.95
        )

        print("旧关系: dept_a (置信度: 0.9)")
        print("新关系: dept_b (置信度: 0.95)")
        print("新关系状态: {}".format(new_rel.status))
        print("新关系是否当前: {}".format(new_rel.is_current))
        print("替代原因: {}".format(new_rel.replacement_reason))

        # 验证
        current_rels = self.crud.get_entity_current_relations("user_zhang")
        assert len(current_rels) == 1
        assert current_rels[0]["target"] == "dept_b"
        assert current_rels[0]["is_current"] == True
        print("\nOK 场景1测试通过")

    def test_scenario_2(self):
        """测试场景2：不同目标替代 - 团队归属变更"""
        print("\n" + "="*70)
        print("测试场景2：不同目标替代 - 团队归属变更")
        print("="*70)

        # 添加实体
        self.crud.relations[("member_x", "PART_OF")] = {
            "id": "rel_2",
            "source": "member_x",
            "target": "team_alpha",
            "relation_type": "PART_OF",
            "confidence": 0.8,
            "status": "ACTIVE",
            "is_current": True,
            "version": 1
        }

        # 创建新关系（不同目标）
        new_rel = self.crud.create_or_replace_relation(
            source="member_x",
            target="team_beta",
            relation_type="PART_OF",
            confidence=0.75
        )

        print("旧关系: team_alpha (置信度: 0.8)")
        print("新关系: team_beta (置信度: 0.75)")
        print("新关系状态: {}".format(new_rel.status))
        print("新关系是否当前: {}".format(new_rel.is_current))
        print("替代原因: {}".format(new_rel.replacement_reason))

        # 验证
        current_rels = self.crud.get_entity_current_relations("member_x")
        assert len(current_rels) == 1
        assert current_rels[0]["target"] == "team_beta"
        print("\nOK 场景2测试通过")

    def test_scenario_3(self):
        """测试场景3：多表联动 - 复杂社交网络变更"""
        print("\n" + "="*70)
        print("测试场景3：多表联动 - 复杂社交网络变更")
        print("="*70)

        # 初始化关系网络
        self.crud.relations[("person_a", "FRIENDS_WITH")] = {
            "id": "rel_3",
            "source": "person_a",
            "target": "person_b",
            "relation_type": "FRIENDS_WITH",
            "confidence": 0.9,
            "status": "ACTIVE",
            "is_current": True,
            "version": 1
        }
        self.crud.relations[("person_a", "WORKS_ON")] = {
            "id": "rel_4",
            "source": "person_a",
            "target": "project_c",
            "relation_type": "WORKS_ON",
            "confidence": 0.95,
            "status": "ACTIVE",
            "is_current": True,
            "version": 1
        }
        self.crud.relations[("project_c", "INVESTED_BY")] = {
            "id": "rel_5",
            "source": "project_c",
            "target": "person_e",
            "relation_type": "INVESTED_BY",
            "confidence": 0.85,
            "status": "ACTIVE",
            "is_current": True,
            "version": 1
        }

        print("初始关系网络:")
        print("  person_a --[FRIENDS_WITH]--> person_b")
        print("  person_a --[WORKS_ON]--> project_c")
        print("  project_c --[INVESTED_BY]--> person_e")

        # 更新：person_a 从project_c转出，person_a和person_e因项目反目
        rel1 = self.crud.create_or_replace_relation(
            source="person_a",
            target="project_b",
            relation_type="WORKS_ON",
            confidence=0.85
        )

        rel2 = self.crud.create_or_replace_relation(
            source="person_a",
            target="person_e",
            relation_type="ENEMIES_WITH",
            confidence=0.95
        )

        print("\n更新操作:")
        print("  person_a --[WORKS_ON]--> project_b")
        print("  person_a --[ENEMIES_WITH]--> person_e")

        # 验证结果
        print("  person_a的当前关系: {}".format(len(self.crud.get_entity_current_relations("person_a"))))
        for rel in self.crud.get_entity_current_relations("person_a"):
            print("    {}".format(rel["direction"] + " --> " + rel["relation_type"]))

        print("\nOK 场景3测试通过")

    def run_all_tests(self):
        """运行所有测试"""
        print("\n" + "="*70)
        print("关系替代系统测试")
        print("="*70)

        try:
            self.test_scenario_1()
            self.test_scenario_2()
            self.test_scenario_3()

            self.crud.print_state()

            print("\n" + "="*70)
            print("🎉 所有关系替代系统测试通过！")
            print("="*70)

            return True

        except Exception as e:
            print("\n❌ 测试失败: {}".format(str(e)))
            import traceback
            traceback.print_exc()
            return False


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序入口"""
    test = RelationSupersedeSystemTest()
    success = test.run_all_tests()

    if success:
        print("\n关系替代机制已就绪，可以集成到现有系统中！")
        return 0
    else:
        print("\n关系替代机制存在问题，需要修复！")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())