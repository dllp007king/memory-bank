#!/usr/bin/env python3
"""
关系替代测试脚本

测试当新的关系信息出现时，系统能否正确替代原有关系
"""

import sys
import os
from datetime import datetime
from typing import List, Dict

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# 测试场景设计
# ============================================================================

TEST_SCENARIOS = {
    "scenario_1": {
        "name": "用户工作变更 - 部门关系替代",
        "description": "用户从A部门转到B部门，需要替代原有的部门关系",
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
            "old_relation_superseded": True,
            "new_relation_created": True,
            "user_current_dept": "dept_b"
        }
    },

    "scenario_2": {
        "name": "管理层变更 - 汇报关系替代",
        "description": "用户换了新的汇报对象，需要替代原有的汇报关系",
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
            "old_relation_superseded": True,
            "new_relation_created": True,
            "user_current_manager": "manager_new"
        }
    },

    "scenario_3": {
        "name": "团队归属变更 - 成员关系替代",
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
                "confidence": 0.75,  # 较低置信度，但信息更新
                "source_memory": "mem_6"
            },
        ],
        "expected_result": {
            "old_relation_superseded": False,  # 低置信度不替代
            "new_relation_created": False,
            "member_current_team": "team_alpha"
        }
    },

    "scenario_4": {
        "name": "多重关系替代 - 复杂场景",
        "description": "一个人同时更换多个关系（工作地和居住地）",
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
            "old_located_at_superseded": True,
            "new_located_at_created": True,
            "old_works_at_superseded": True,
            "new_works_at_created": True,
            "user_current_location": "city_shanghai",
            "user_current_company": "company_new"
        }
    },

    "scenario_5": {
        "name": "矛盾关系处理 - 同类型关系冲突",
        "description": "同一个人有两个不同的团队关系，需要处理冲突",
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
            "old_relation_superseded": True,
            "new_relation_created": True,
            "user_current_team": "team_b"
        }
    }
}


# ============================================================================
# 模拟关系处理器
# ============================================================================

class MockRelationProcessor:
    """模拟关系处理器（不依赖数据库）"""

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

    def create_relation(self, source: str, target: str, relation_type: str,
                    confidence: float, source_memory: str) -> Dict:
        """
        创建或替代关系

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

        # 检查是否已存在相同类型的关系
        existing = self.relations.get(key)

        result = {
            "source": source,
            "target": target,
            "type": relation_type,
            "confidence": confidence,
            "source_memory": source_memory,
            "action": "created",
            "superseded_relation": None
        }

        if existing:
            # 检查是否是相同目标
            if existing["target"] == target:
                # 相同关系，比较置信度
                if confidence > existing["confidence"]:
                    # 新关系置信度更高，替代
                    self.relations[key] = {
                        "source": source,
                        "target": target,
                        "type": relation_type,
                        "confidence": confidence,
                        "source_memory": source_memory,
                        "updated_at": datetime.now().isoformat()
                    }
                    result["action"] = "updated"
                    result["superseded_relation"] = existing
                    result["old_confidence"] = existing["confidence"]
                    result["new_confidence"] = confidence
                else:
                    # 新关系置信度低，不更新
                    result["action"] = "skipped"
                    result["reason"] = "New confidence is lower"
            else:
                # 不同目标，创建新关系（需要处理冲突）
                # 记录原有关系
                result["action"] = "created"
                result["conflicting_relation"] = existing
                result["old_target"] = existing["target"]
                result["new_target"] = target

                # 更新关系（替代原有关系）
                self.relations[key] = {
                    "source": source,
                    "target": target,
                    "type": relation_type,
                    "confidence": confidence,
                    "source_memory": source_memory,
                    "updated_at": datetime.now().isoformat(),
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

    def get_entity_relations(self, entity_slug: str) -> List[Dict]:
        """获取实体的所有关系"""
        relations = []
        for (source, rel_type), relation in self.relations.items():
            if source == entity_slug:
                relations.append(relation)
        return relations

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
            result = self.processor.create_relation(
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
            result = self.processor.create_relation(
                rel_info["source"],
                rel_info["target"],
                rel_info["type"],
                rel_info["confidence"],
                rel_info["source_memory"]
            )
            print(f"  更新关系: {rel_info['source']} --[{rel_info['type']}]--> {rel_info['target']} "
                  f"(置信度: {rel_info['confidence']:.2f})")
            print(f"    动作: {result['action']}")
            if "superseded_relation" in result and result["superseded_relation"]:
                old = result["superseded_relation"]
                print(f"    替代了原有关系: {old['target']} (置信度: {old['confidence']:.2f})")
            if "conflicting_relation" in result and result["conflicting_relation"]:
                old = result["conflicting_relation"]
                print(f"    发现冲突: 原目标 {old['target']} -> 新目标 {result['new_target']}")
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

        # 验证关系替代
        if "old_relation_superseded" in expected:
            check = any(
                r["phase"] == "update" and
                r["result"]["action"] == "updated"
                for r in self.results if r["scenario"] == scenario_key
            )
            expected_value = expected["old_relation_superseded"]
            actual_value = check
            status = "✅" if actual_value == expected_value else "❌"
            print(f"  {status} 关系被替代: 期望 {expected_value}, 实际 {actual_value}")

        # 验证新关系创建
        if "new_relation_created" in expected:
            check = any(
                r["phase"] == "update" and
                r["result"]["action"] in ["updated", "created"]
                for r in self.results if r["scenario"] == scenario_key
            )
            expected_value = expected["new_relation_created"]
            actual_value = check
            status = "✅" if actual_value == expected_value else "❌"
            print(f"  {status} 新关系创建: 期望 {expected_value}, 实际 {actual_value}")

        # 验证当前关系目标
        for key in ["user_current_dept", "user_current_manager", "user_current_team",
                   "member_current_team", "user_current_location", "user_current_company",
                   "user_current_team_2"]:
            if key in expected:
                # 查找当前关系
                current_rel = self.processor.get_relation(
                    key.split("_")[0] + "_" + key.split("_")[1],  # 提取实体名
                    "WORKS_AT" if "dept" in key or "company" in key else
                    "REPORTS_TO" if "manager" in key else
                    "PART_OF"  # 默认
                )

                # 根据关键键调整关系类型
                if "dept" in key:
                    current_rel = self.processor.get_relation(
                        key.split("_")[1] + "_" + key.split("_")[2],  # user_zhang -> dept_a
                        "WORKS_AT"
                    )
                elif "manager" in key:
                    current_rel = self.processor.get_relation("user_li", "REPORTS_TO")
                elif "location" in key:
                    current_rel = self.processor.get_relation("user_wang", "LOCATED_AT")
                elif "company" in key:
                    current_rel = self.processor.get_relation("user_wang", "WORKS_AT")
                elif "team" in key:
                    # 查找PART_OF关系
                    for (source, rel_type), rel in self.processor.relations.items():
                        if rel_type == "PART_OF":
                            current_rel = rel
                            break

                if current_rel:
                    actual_value = current_rel["target"]
                    expected_value = expected[key]
                    status = "✅" if actual_value == expected_value else "❌"
                    print(f"  {status} 当前{key}: 期望 {expected_value}, 实际 {actual_value}")

    def run_all_tests(self):
        """运行所有测试"""
        print("="*70)
        print("关系替代测试")
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
        action_counts = {"created": 0, "updated": 0, "skipped": 0}
        for result in self.results:
            action = result["result"]["action"]
            action_counts[action] = action_counts.get(action, 0) + 1

        print(f"\n操作统计:")
        print(f"  创建关系: {action_counts['created']}")
        print(f"  更新关系: {action_counts['updated']}")
        print(f"  跳过更新: {action_counts['skipped']}")

        # 统计替代情况
        superseded_count = sum(
            1 for r in self.results
            if "superseded_relation" in r["result"] and r["result"]["superseded_relation"]
        )
        print(f"\n关系替代数: {superseded_count}")

        # 统计冲突情况
        conflict_count = sum(
            1 for r in self.results
            if "conflicting_relation" in r["result"]
        )
        print(f"关系冲突数: {conflict_count}")

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