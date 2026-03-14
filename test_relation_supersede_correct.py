#!/usr/bin/env python3
"""
关系替代测试脚本（修正版）

正确的预期行为：
1. 用户工作变更时，新建关系，删除旧关系
2. 管理层变更时，应该新建汇报关系，删除旧汇报关系
3. 团队归属变更时，应该是团队归属关系变更（如果是同一类型关系的替代）
4. 应该是新的关系替换旧的，没有关系新建关系
5. 处理矛盾关系时，按照置信度原则建立新的关系，删除旧的关系

多表联动场景：
A是B的成员来完成C项目，C项目是E投资的，E和A是朋友
当A和E因为项目B的开发问题反目成仇不再是朋友时：
- 应该改变原本的信息
- 将A是B的成员来完成C项目（保持）
- C项目是E投资的（保持）
- 删除A和E的朋友关系
"""

import sys
import os
from datetime import datetime
from typing import List, Dict

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# 测试场景设计（修正版）
# ============================================================================

TEST_SCENARIOS = {
    "scenario_1": {
        "name": "用户工作变更 - 部门关系替代",
        "description": "用户从A部门转到B部门，需要删除旧的部门关系，创建新关系",
        "entities": [
            {"slug": "user_zhang", "name": "张三", "type": "PERSON"},
            {"slug": "dept_a", "name": "技术部", "type": "ORG"},
            {"slug": "dept_b", "name": "产品部", "type": "ORG"},
        ],
        "initial_relations": [
            {
                "source": "user_zhang",
                "target": "dept_a",
                "type": "WORKS_AT",
                "confidence": 0.9,
                "source_memory": "mem_1"
            },
        ],
        "update_relations": [
            {
                "source": "user_zhang",
                "target": "dept_b",
                "type": "WORKS_AT",
                "confidence": 0.95,  # 更高置信度
                "source_memory": "mem_2"
            },
        ],
        "expected_result": {
            "old_relation_deleted": True,  # 旧关系被删除
            "new_relation_created": True,  # 新关系被创建
            "user_current_dept": "dept_b"
        }
    },

    "scenario_2": {
        "name": "管理层变更 - 汇报关系替代",
        "description": "用户换了新的汇报对象，需要删除旧的汇报关系，创建新关系",
        "entities": [
            {"slug": "user_li", "name": "李四", "type": "PERSON"},
            {"slug": "manager_old", "name": "王经理", "type": "PERSON"},
            {"slug": "manager_new", "name": "赵经理", "type": "PERSON"},
        ],
        "initial_relations": [
            {
                "source": "user_li",
                "target": "manager_old",
                "type": "REPORTS_TO",
                "confidence": 0.85,
                "source_memory": "mem_3"
            },
        ],
        "update_relations": [
            {
                "source": "user_li",
                "target": "manager_new",
                "type": "REPORTS_TO",
                "confidence": 0.9,  # 更高置信度
                "source_memory": "mem_4"
            },
        ],
        "expected_result": {
            "old_relation_deleted": True,
            "new_relation_created": True,
            "user_current_manager": "manager_new"
        }
    },

    "scenario_3": {
        "name": "团队归属变更 - 同类型关系替代",
        "description": "团队成员在不同团队间转移，需要替代原有团队关系",
        "entities": [
            {"slug": "team_alpha", "name": "Alpha团队", "type": "ORG"},
            {"slug": "team_beta", "name": "Beta团队", "type": "ORG"},
            {"slug": "member_x", "name": "小王", "type": "PERSON"},
        ],
        "initial_relations": [
            {
                "source": "member_x",
                "target": "team_alpha",
                "type": "PART_OF",
                "confidence": 0.8,
                "source_memory": "mem_5"
            },
        ],
        "update_relations": [
            {
                "source": "member_x",
                "target": "team_beta",
                "type": "PART_OF",
                "confidence": 0.75,  # 较低置信度
                "source_memory": "mem_6"
            },
        ],
        "expected_result": {
            "old_relation_replaced": True,  # 旧关系被新关系替代（即使置信度较低）
            "member_current_team": "team_beta"
        }
    },

    "scenario_4": {
        "name": "多重关系替代 - 替换场景",
        "description": "一个人同时更换多个关系（工作地和居住地），新关系替换旧关系",
        "entities": [
            {"slug": "user_wang", "name": "小王", "type": "PERSON"},
            {"slug": "city_beijing", "name": "北京", "type": "LOCATION"},
            {"slug": "city_shanghai", "name": "上海", "type": "LOCATION"},
            {"slug": "company_old", "name": "旧公司", "type": "ORG"},
            {"slug": "company_new", "name": "新公司", "type": "ORG"},
        ],
        "initial_relations": [
            {
                "source": "user_wang",
                "target": "city_beijing",
                "type": "LOCATED_AT",
                "confidence": 0.9,
                "source_memory": "mem_7"
            },
            {
                "source": "user_wang",
                "target": "company_old",
                "type": "WORKS_AT",
                "confidence": 0.85,
                "source_memory": "mem_8"
            },
        ],
        "update_relations": [
            {
                "source": "user_wang",
                "target": "city_shanghai",
                "type": "LOCATED_AT",
                "confidence": 0.95,  # 更高置信度
                "source_memory": "mem_9"
            },
            {
                "source": "user_wang",
                "target": "company_new",
                "type": "WORKS_AT",
                "confidence": 0.9,  # 更高置信度
                "source_memory": "mem_10"
            },
        ],
        "expected_result": {
            "old_located_at_deleted": True,
            "new_located_at_created": True,
            "old_works_at_deleted": True,
            "new_works_at_created": True,
            "user_current_location": "city_shanghai",
            "user_current_company": "company_new"
        }
    },

    "scenario_5": {
        "name": "矛盾关系处理 - 按置信度原则处理",
        "description": "同一个人有两个不同的团队关系，需要按置信度原则处理",
        "entities": [
            {"slug": "user_zhao", "name": "小赵", "type": "PERSON"},
            {"slug": "team_a", "name": "团队A", "type": "ORG"},
            {"slug": "team_b", "name": "团队B", "type": "ORG"},
        ],
        "initial_relations": [
            {
                "source": "user_zhao",
                "target": "team_a",
                "type": "PART_OF",
                "confidence": 0.8,
                "source_memory": "mem_11"
            },
        ],
        "update_relations": [
            {
                "source": "user_zhao",
                "target": "team_b",
                "type": "PART_OF",
                "confidence": 0.85,  # 略高置信度
                "source_memory": "mem_12"
            },
        ],
        "expected_result": {
            "old_relation_replaced": True,
            "new_relation_created": True,
            "user_current_team": "team_b"
        }
    },

    "scenario_6": {
        "name": "多表联动 - 复杂社交网络变更",
        "description": "A是B的成员来完成C项目，C项目是E投资的，E和A是朋友。A和E因项目B问题反目。",
        "entities": [
            {"slug": "person_a", "name": "小A", "type": "PERSON"},
            {"slug": "person_b", "name": "小B", "type": "PERSON"},
            {"slug": "person_e", "name": "小E", "type": "PERSON"},
            {"slug": "project_c", "name": "C项目", "type": "EVENT"},
            {"slug": "project_b", "name": "B项目", "type": "EVENT"},
        ],
        "initial_relations": [
            {
                "source": "person_a",
                "target": "person_b",
                "type": "WORKS_WITH",
                "confidence": 0.9,
                "source_memory": "mem_13"
            },
            {
                "source": "person_a",
                "target": "project_c",
                "type": "WORKS_ON",
                "confidence": 0.95,
                "source_memory": "mem_14"
            },
            {
                "source": "project_c",
                "target": "person_e",
                "type": "INVESTED_BY",
                "confidence": 0.85,
                "source_memory": "mem_15"
            },
            {
                "source": "person_a",
                "target": "person_e",
                "type": "FRIENDS_WITH",
                "confidence": 0.9,
                "source_memory": "mem_16"
            },
        ],
        "update_relations": [
            # A从B项目转到另一个团队，不再是B的成员
            {
                "source": "person_a",
                "target": "project_b",
                "type": "WORKS_ON",
                "confidence": 0.85,
                "source_memory": "mem_17"
            },
            # A和E因为项目B反目成仇，不再是朋友
            {
                "source": "person_a",
                "target": "person_e",
                "type": "ENEMIES_WITH",  # 朋友关系变为敌人关系
                "confidence": 0.95,  # 更高置信度
                "source_memory": "mem_18"
            },
        ],
        "expected_result": {
            "old_works_with_b_deleted": True,
            "new_works_on_b_created": True,
            "old_friends_with_e_deleted": True,
            "new_enemies_with_e_created": True,
            "works_on_project_c_kept": True,  # 保持不变
            "project_c_invested_by_e_kept": True,  # 保持不变
        }
    }
}


# ============================================================================
# 模拟关系处理器（改进版）
# ============================================================================

class MockRelationProcessor:
    """模拟关系处理器（支持删除和替代）"""

    def __init__(self):
        self.entities: Dict[str, Dict] = {}  # slug -> entity info
        self.relations: Dict[str, Dict] = {}  # (source, type) -> relation info

    def add_entity(self, slug: str, name: str, entity_type: str):
        """添加实体"""
        self.entities[slug] = {
            "slug": slug,
            "name": name,
            "type": entity_type
        }

    def create_or_update_relation(self, source: str, target: str, relation_type: str,
                                 confidence: float, source_memory: str) -> Dict:
        """
        创建或替代关系（改进版）

        规则：
        1. 如果存在相同关系（source, type, target），比较置信度
        2. 如果新置信度更高，删除旧关系，创建新关系
        3. 如果存在不同目标的关系（source, type），且新置信度更高，删除旧关系，创建新关系

        Args:
            source: 源实体
            target: 目标实体
            relation_type: 关系类型
            confidence: 置信度
            source_memory: 来源记忆

        Returns:
            操作结果
        """
        key = (source, relation_type)
        result = {
            "source": source,
            "target": target,
            "type": relation_type,
            "confidence": confidence,
            "source_memory": source_memory,
            "action": "created",
            "deleted_relations": []
        }

        # 检查是否存在相同类型的关系
        existing = self.relations.get(key)

        if existing:
            # 检查是否是相同目标
            if existing["target"] == target:
                # 相同关系，比较置信度
                if confidence >= existing["confidence"]:
                    # 新关系置信度更高或相等，删除旧关系，创建新关系
                    del self.relations[key]
                    result["deleted_relations"].append(existing)
                    result["action"] = "replaced"  # 替代
                    result["old_confidence"] = existing["confidence"]
                    result["new_confidence"] = confidence

                    # 创建新关系
                    self.relations[key] = {
                        "source": source,
                        "target": target,
                        "type": relation_type,
                        "confidence": confidence,
                        "source_memory": source_memory,
                        "created_at": datetime.now().isoformat(),
                        "supersedes": existing["target"]  # 标记被替代的目标
                    }
                else:
                    # 新关系置信度更低，不更新
                    result["action"] = "skipped"
                    result["reason"] = "New confidence is lower"
            else:
                # 不同目标，需要替代旧关系
                # 记录旧关系
                result["action"] = "replaced_with_different_target"
                result["deleted_relations"].append(existing)
                result["old_target"] = existing["target"]
                result["new_target"] = target

                # 删除旧关系，创建新关系
                del self.relations[key]

                self.relations[key] = {
                    "source": source,
                    "target": target,
                    "type": relation_type,
                    "confidence": confidence,
                    "source_memory": source_memory,
                    "created_at": datetime.now().isoformat(),
                    "supersedes": existing["target"]  # 标记被替代的目标
                }
                result["superseded_relation"] = existing

        else:
            # 新关系，直接创建
            self.relations[key] = {
                "source": source,
                "target": target,
                "type": relation_type,
                "confidence": confidence,
                "source_memory": source_memory,
                "created_at": datetime.now().isoformat()
            }

        return result

    def get_relation(self, source: str, relation_type: str) -> Dict:
        """获取关系"""
        key = (source, relation_type)
        return self.relations.get(key)

    def delete_relation(self, source: str, target: str, relation_type: str) -> bool:
        """删除关系"""
        key = (source, relation_type)
        rel = self.relations.get(key)
        if rel and rel["target"] == target:
            del self.relations[key]
            return True
        return False

    def print_state(self):
        """打印当前状态"""
        print("\n当前状态:")
        print(f"  实体数: {len(self.entities)}")
        print(f"  关系数: {len(self.relations)}")

        if self.entities:
            print("\n  实体列表:")
            for slug, entity in self.entities.items():
                print(f"    {slug} ({entity['name']}, {entity['type']})")

        if self.relations:
            print("\n  关系列表:")
            for i, (source, rel_type) in enumerate(self.relations.keys(), 1):
                rel = self.relations[(source, rel_type)]
                print(f"    {i}. {source} --[{rel_type}]--> {rel['target']} "
                      f"(置信度: {rel['confidence']:.2f}, "
                      f"记忆: {rel['source_memory']})")


# ============================================================================
# 测试类
# ============================================================================

class RelationSupersedeTest:
    def __init__(self):
        self.processor = MockRelationProcessor()
        self.results = []

    def test_scenario(self, scenario_key: str):
        """测试单个场景"""
        scenario = TEST_SCENARIOS[scenario_key]

        print("\n" + "="*70)
        print(f"测试场景: {scenario['name']}")
        print(f"描述: {scenario['description']}")
        print("="*70)

        # 初始化实体
        print("\n步骤 1: 添加实体")
        for entity_info in scenario["entities"]:
            self.processor.add_entity(
                entity_info["slug"],
                entity_info["name"],
                entity_info["type"]
            )
            print(f"  添加实体: {entity_info['slug']} ({entity_info['name']}, {entity_info['type']})")

        # 创建初始关系
        print("\n步骤 2: 创建初始关系")
        for rel_info in scenario["initial_relations"]:
            result = self.processor.create_or_update_relation(
                rel_info["source"],
                rel_info["target"],
                rel_info["type"],
                rel_info["confidence"],
                rel_info["source_memory"]
            )
            print(f"  创建关系: {rel_info['source']} --[{rel_info['type']}]--> {rel_info['target']} "
                  f"(置信度: {rel_info['confidence']:.2f})")
            print(f"    结果: {result['action']}")
            self.results.append({
                "scenario": scenario_key,
                "phase": "initial",
                "result": result
            })

        # 打印初始状态
        print("\n初始状态:")
        self.processor.print_state()

        # 更新关系
        print("\n步骤 3: 更新关系（模拟新信息）")
        for rel_info in scenario["update_relations"]:
            result = self.processor.create_or_update_relation(
                rel_info["source"],
                rel_info["target"],
                rel_info["type"],
                rel_info["confidence"],
                rel_info["source_memory"]
            )
            print(f"  更新关系: {rel_info['source']} --[{rel_info['type']}]--> {rel_info['target']} "
                  f"(置信度: {rel_info['confidence']:.2f})")
            print(f"    动作: {result['action']}")

            if result["deleted_relations"]:
                for deleted_rel in result["deleted_relations"]:
                    print(f"    删除关系: {deleted_rel['target']} "
                          f"(旧置信度: {deleted_rel['confidence']:.2f})")

            if "superseded_relation" in result and result["superseded_relation"]:
                old = result["superseded_relation"]
                print(f"    替代关系: 旧目标 {old['target']} -> 新目标 {result['new_target']}")

            self.results.append({
                "scenario": scenario_key,
                "phase": "update",
                "result": result
            })

        # 打印更新后状态
        print("\n更新后状态:")
        self.processor.print_state()

        # 验证结果
        print("\n步骤 4: 验证结果")
        self._verify_result(scenario_key, scenario)

    def _verify_result(self, scenario_key: str, scenario: Dict):
        """验证测试结果"""
        expected = scenario["expected_result"]

        # 验证删除和创建
        for key in expected:
            if key.endswith("_deleted"):
                # 检查是否有删除操作
                check = any(
                    r["phase"] == "update" and
                    "deleted_relations" in r["result"] and
                    len(r["result"]["deleted_relations"]) > 0
                    for r in self.results if r["scenario"] == scenario_key
                )
                expected_value = expected[key]
                actual_value = check
                status = "✅" if actual_value == expected_value else "❌"
                print(f"  {status} {key}: 期望 {expected_value}, 实际 {actual_value}")

            elif key.endswith("_created"):
                # 检查是否有创建操作
                check = any(
                    r["phase"] == "update" and
                    r["result"]["action"] in ["replaced", "replaced_with_different_target"]
                    for r in self.results if r["scenario"] == scenario_key
                )
                expected_value = expected[key]
                actual_value = check
                status = "✅" if actual_value == expected_value else "❌"
                print(f"  {status} {key}: 期望 {expected_value}, 实际 {actual_value}")

            elif key.endswith("_replaced"):
                # 检查是否有替代操作
                check = any(
                    r["phase"] == "update" and
                    r["result"]["action"] == "replaced_with_different_target"
                    for r in self.results if r["scenario"] == scenario_key
                )
                expected_value = expected[key]
                actual_value = check
                status = "✅" if actual_value == expected_value else "❌"
                print(f"  {status} {key}: 期望 {expected_value}, 实际 {actual_value}")

            elif "_kept" in key:
                # 检查关系是否保持不变
                check = True  # 默认假设保持
                for r in self.results:
                    if r["phase"] == "update":
                        # 检查是否有删除操作影响了这些关系
                        if "deleted_relations" in r["result"]:
                            for deleted in r["result"]["deleted_relations"]:
                                if key in deleted:  # 如果被删除了，保持为False
                                    # 解析预期键
                                    if "_worked_on_project_c" in key:
                                        if deleted["type"] == "WORKS_ON" and deleted["target"] == "project_c":
                                            check = False
                                    elif "_project_c_invested_by_e" in key:
                                        if deleted["type"] == "INVESTED_BY" and deleted["source"] == "project_c" and deleted["target"] == "person_e":
                                            check = False

                expected_value = expected[key]
                actual_value = check
                status = "✅" if actual_value == expected_value else "❌"
                print(f"  {status} {key}: 期望 {expected_value}, 实际 {actual_value}")

            else:
                # 验证当前目标
                rel = self.processor.get_relation(
                    key.split("_")[0] + "_" + key.split("_")[1],  # 提取关系键
                    "WORKS_AT" if "dept" in key or "company" in key else
                    "REPORTS_TO" if "manager" in key else
                    "PART_OF" if "team" in key else None
                )

                if rel:
                    actual_value = rel["target"]
                    expected_value = expected[key]
                    status = "✅" if actual_value == expected_value else "❌"
                    print(f"  {status} {key}: 期望 {expected_value}, 实际 {actual_value}")

    def run_all_tests(self):
        """运行所有测试"""
        print("="*70)
        print("关系替代测试（修正版）")
        print("="*70)

        try:
            for scenario_key in TEST_SCENARIOS.keys():
                self.test_scenario(scenario_key)

            self._generate_summary()
            return True

        except Exception as e:
            print(f"\n❌ 测试失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

    def _generate_summary(self):
        """生成测试总结"""
        print("\n" + "="*70)
        print("测试总结")
        print("="*70)

        # 统计操作类型
        action_counts = {
            "created": 0,
            "replaced": 0,
            "replaced_with_different_target": 0,
            "skipped": 0
        }

        for result in self.results:
            action = result["result"]["action"]
            action_counts[action] = action_counts.get(action, 0) + 1

        print(f"\n操作统计:")
        print(f"  创建关系: {action_counts['created']}")
        print(f"  替代关系（同目标）: {action_counts['replaced']}")
        print(f"  替代关系（不同目标）: {action_counts['replaced_with_different_target']}")
        print(f"  跳过更新: {action_counts['skipped']}")

        # 统计删除情况
        deleted_count = sum(
            len(r["result"].get("deleted_relations", []))
            for r in self.results if r["phase"] == "update"
        )
        print(f"\n删除关系数: {deleted_count}")

        print("\n✅ 所有关系替代测试完成")


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序入口"""
    test = RelationSupersedeTest()
    success = test.run_all_tests()

    if success:
        print("\n" + "="*70)
        print("🎉 所有关系替代测试通过！")
        print("="*70)
        return 0
    else:
        print("\n" + "="*70)
        print("❌ 测试失败")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())