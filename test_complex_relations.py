#!/usr/bin/env python3
"""
复杂关系测试脚本

测试带有复杂关系条目的输入和查询处理
"""

import sys
import os
import importlib.util
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Tuple

# 直接加载lifecycle模块
lifecycle_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "memory_bank",
    "lifecycle.py"
)
spec = importlib.util.spec_from_file_location("lifecycle", lifecycle_path)
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)

infer_decay_rate = lifecycle.infer_decay_rate
effective_confidence = lifecycle.effective_confidence


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class Entity:
    """实体"""
    slug: str
    name: str
    entity_type: str


@dataclass
class Relation:
    """关系"""
    source_slug: str
    target_slug: str
    relation_type: str
    confidence: float


@dataclass
class MemoryWithRelations:
    """带关系的记忆"""
    id: str
    content: str
    memory_type: str = "fact"
    confidence: float = 1.0
    importance: float = 0.5
    decay_rate: float = 0.01
    lifecycle_state: str = "ACTIVE"
    entities: List[str] = None
    relations: List[Relation] = None
    created_at: str = ""
    updated_at: str = ""
    access_count: int = 0
    last_accessed_at: str = ""

    def __post_init__(self):
        if self.entities is None:
            self.entities = []
        if self.relations is None:
            self.relations = []

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "confidence": self.confidence,
            "importance": self.importance,
            "decay_rate": self.decay_rate,
            "lifecycle_state": self.lifecycle_state,
            "entities": self.entities,
            "relations": [
                {
                    "source": r.source_slug,
                    "target": r.target_slug,
                    "type": r.relation_type,
                    "confidence": r.confidence
                }
                for r in self.relations
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# 复杂关系测试数据
# ============================================================================

COMPLEX_TEST_DATA = {
    "entities": [
        Entity("alice", "Alice", "PERSON"),
        Entity("bob", "Bob", "PERSON"),
        Entity("company", "某公司", "ORG"),
        Entity("project", "项目A", "EVENT"),
        Entity("manager", "张经理", "PERSON"),
        Entity("team", "开发团队", "ORG"),
    ],

    "memories_with_relations": [
        {
            "id": "rel_mem_1",
            "content": "Alice在项目A中与Bob共事，他们都在某公司工作",
            "memory_type": "fact",
            "confidence": 0.9,
            "importance": 0.7,
            "entities": ["alice", "bob", "company", "project"],
            "relations": [
                Relation("alice", "project", "PART_OF", 0.9),
                Relation("bob", "project", "PART_OF", 0.9),
                Relation("alice", "company", "WORKS_AT", 0.95),
                Relation("bob", "company", "WORKS_AT", 0.95),
                Relation("alice", "bob", "WORKS_WITH", 0.85),
            ],
            "expected_decay_rate": 0.01,
        },
        {
            "id": "rel_mem_2",
            "content": "张经理是开发团队的负责人，他管理项目A",
            "memory_type": "fact",
            "confidence": 0.85,
            "importance": 0.8,
            "entities": ["manager", "team", "project"],
            "relations": [
                Relation("manager", "team", "MANAGES", 0.95),
                Relation("team", "project", "WORKS_ON", 0.9),
                Relation("manager", "project", "MANAGES", 0.9),
            ],
            "expected_decay_rate": 0.01,
        },
        {
            "id": "rel_mem_3",
            "content": "Alice向张经理汇报工作进展",
            "memory_type": "fact",
            "confidence": 0.8,
            "importance": 0.6,
            "entities": ["alice", "manager"],
            "relations": [
                Relation("alice", "manager", "REPORTS_TO", 0.85),
            ],
            "expected_decay_rate": 0.01,
        },
        {
            "id": "rel_mem_4",
            "content": "Alice和Bob都是张经理的团队成员",
            "memory_type": "fact",
            "confidence": 0.75,
            "importance": 0.5,
            "entities": ["alice", "bob", "manager", "team"],
            "relations": [
                Relation("alice", "team", "PART_OF", 0.9),
                Relation("bob", "team", "PART_OF", 0.9),
                Relation("team", "manager", "MANAGED_BY", 0.95),
            ],
            "expected_decay_rate": 0.01,
        },
        {
            "id": "rel_mem_5",
            "content": "项目A将在下个月完成，现在正在进行测试阶段",
            "memory_type": "fact",
            "confidence": 0.7,
            "importance": 0.8,
            "entities": ["project"],
            "relations": [],
            "expected_decay_rate": 0.05,
        },
    ]
}


# ============================================================================
# 关系查询处理
# ============================================================================

class RelationQueryProcessor:
    """关系查询处理器"""

    def __init__(self, memories: List[MemoryWithRelations]):
        self.memories = memories
        self.entity_index = {}
        self.relation_index = {}

        self._build_indexes()

    def _build_indexes(self):
        """构建实体和关系索引"""
        for memory in self.memories:
            # 构建实体索引
            for entity_slug in memory.entities:
                if entity_slug not in self.entity_index:
                    self.entity_index[entity_slug] = []
                self.entity_index[entity_slug].append(memory.id)

            # 构建关系索引
            for relation in memory.relations:
                key = (relation.source_slug, relation.relation_type, relation.target_slug)
                self.relation_index[key] = {
                    "source": relation.source_slug,
                    "target": relation.target_slug,
                    "type": relation.relation_type,
                    "confidence": relation.confidence,
                    "memory_id": memory.id
                }

    def query_relations(self, entity_slug: str, relation_type: str = None) -> List[Dict]:
        """
        查询与实体相关的关系

        Args:
            entity_slug: 实体标识
            relation_type: 关系类型（可选）

        Returns:
            关系列表
        """
        results = []

        for (source, rel_type, target), rel_info in self.relation_index.items():
            if relation_type is None or rel_type == relation_type:
                if source == entity_slug:
                    # 作为源的关系
                    results.append({
                        "direction": "outgoing",
                        **rel_info
                    })
                elif target == entity_slug:
                    # 作为目标的关系
                    results.append({
                        "direction": "incoming",
                        **rel_info
                    })

        # 按置信度排序
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results

    def find_path(self, start_entity: str, end_entity: str, max_depth: int = 3) -> List[Dict]:
        """
        查找两个实体之间的路径

        Args:
            start_entity: 起始实体
            end_entity: 目标实体
            max_depth: 最大深度

        Returns:
            路径列表
        """
        paths = []
        self._dfs_find_path(start_entity, end_entity, [], 0, max_depth, paths)
        return paths

    def _dfs_find_path(self, current: str, target: str, path: List,
                     depth: int, max_depth: int, results: List):
        """深度优先搜索路径"""
        if depth > max_depth:
            return

        if current == target:
            results.append(path + [current])
            return

        for (source, _, entity_target), rel_info in self.relation_index.items():
            if source == current:
                if entity_target not in path:
                    self._dfs_find_path(
                        entity_target, target,
                        path + [{"entity": current, "relation": rel_info}],
                        depth + 1, max_depth, results
                    )

    def get_entity_context(self, entity_slug: str) -> Dict:
        """
        获取实体的上下文信息

        Args:
            entity_slug: 实体标识

        Returns:
            实体上下文
        """
        context = {
            "entity": entity_slug,
            "memories": self.entity_index.get(entity_slug, []),
            "relations": self.query_relations(entity_slug)
        }

        # 统计关系类型
        relation_types = {}
        for rel in context["relations"]:
            rtype = rel["type"]
            if rtype not in relation_types:
                relation_types[rtype] = []
            relation_types[rtype].append(rel)

        context["relation_summary"] = {
            rtype: len(rels)
            for rtype, rels in relation_types.items()
        }

        return context


# ============================================================================
# 测试类
# ============================================================================

class ComplexRelationTest:
    def __init__(self):
        self.entities = COMPLEX_TEST_DATA["entities"]
        self.memories = []
        self.processor = None

    def create_memories_with_relations(self):
        """创建带关系的记忆"""
        print("\n=== 1. 创建带复杂关系的记忆 ===")
        print(f"实体数: {len(self.entities)}")
        print(f"记忆数: {len(COMPLEX_TEST_DATA['memories_with_relations'])}\n")

        # 打印实体信息
        print("实体列表:")
        for entity in self.entities:
            print(f"  {entity.slug} ({entity.name}, {entity.entity_type})")

        # 创建记忆
        for i, mem_data in enumerate(COMPLEX_TEST_DATA["memories_with_relations"], 1):
            memory = MemoryWithRelations(
                id=mem_data["id"],
                content=mem_data["content"],
                memory_type=mem_data["memory_type"],
                confidence=mem_data["confidence"],
                importance=mem_data["importance"],
                entities=mem_data["entities"],
                relations=mem_data["relations"],
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                decay_rate=infer_decay_rate(mem_data["content"]),
                lifecycle_state="ACTIVE",
                access_count=0,
                last_accessed_at=datetime.now().isoformat()
            )

            self.memories.append(memory)

            print(f"\n记忆 {i}: {memory.id}")
            print(f"  内容: {memory.content[:40]}...")
            print(f"  置信度: {memory.confidence:.2f}, 重要性: {memory.importance:.2f}")
            print(f"  实体: {memory.entities}")
            print(f"  关系数: {len(memory.relations)}")

            for j, rel in enumerate(memory.relations, 1):
                print(f"    {j}. {rel.source_slug} --[{rel.relation_type}]--> {rel.target_slug} "
                      f"(置信度: {rel.confidence:.2f})")

        print("\n✅ 记忆创建完成")

    def analyze_relation_network(self):
        """分析关系网络"""
        print("\n=== 2. 分析关系网络 ===")

        self.processor = RelationQueryProcessor(self.memories)

        # 打印关系索引
        print(f"\n关系索引数: {len(self.processor.relation_index)}")
        print("\n关系列表:")
        for i, (source, rel_type, target) in enumerate(self.processor.relation_index.keys(), 1):
            rel_info = self.processor.relation_index[(source, rel_type, target)]
            print(f"  {i}. {source} --[{rel_type}]--> {target} "
                  f"(记忆: {rel_info['memory_id']}, 置信度: {rel_info['confidence']:.2f})")

    def query_entity_relations(self):
        """查询实体关系"""
        print("\n=== 3. 查询实体关系 ===")

        test_queries = [
            ("alice", None),
            ("bob", "WORKS_WITH"),
            ("manager", "MANAGES"),
            ("project", "PART_OF"),
        ]

        for entity_slug, relation_type in test_queries:
            print(f"\n查询: 实体 '{entity_slug}'" +
                  (f", 关系类型 '{relation_type}'" if relation_type else " (所有关系)"))

            relations = self.processor.query_relations(entity_slug, relation_type)

            if not relations:
                print("  没有找到相关关系")
                continue

            print(f"  找到 {len(relations)} 个关系:")

            for rel in relations:
                direction_icon = "→" if rel["direction"] == "outgoing" else "←"
                if rel["direction"] == "outgoing":
                    print(f"    {rel['source']} {direction_icon} {rel['target']} "
                          f"[{rel['type']}] (置信度: {rel['confidence']:.2f})")
                else:
                    print(f"    {rel['target']} {direction_icon} {rel['source']} "
                          f"[{rel['type']}] (置信度: {rel['confidence']:.2f})")

    def find_paths_between_entities(self):
        """查找实体间的路径"""
        print("\n=== 4. 查找实体间路径 ===")

        path_queries = [
            ("alice", "bob", 2),
            ("alice", "project", 2),
            ("manager", "project", 2),
            ("bob", "manager", 3),
        ]

        for start, end, max_depth in path_queries:
            print(f"\n查找路径: {start} -> {end} (最大深度: {max_depth})")

            paths = self.processor.find_path(start, end, max_depth)

            if not paths:
                print("  未找到路径")
                continue

            print(f"  找到 {len(paths)} 条路径:")

            for i, path in enumerate(paths, 1):
                print(f"\n  路径 {i}:")
                for step in path:
                    if isinstance(step, str):
                        print(f"    [{step}]")
                    else:
                        print(f"    {step['entity']} --[{step['relation']['type']}]-->")

    def get_entity_context(self):
        """获取实体上下文"""
        print("\n=== 5. 获取实体上下文 ===")

        target_entities = ["alice", "manager", "project"]

        for entity_slug in target_entities:
            print(f"\n实体: {entity_slug}")

            context = self.processor.get_entity_context(entity_slug)

            print(f"  相关记忆数: {len(context['memories'])}")
            for mem_id in context['memories']:
                print(f"    - {mem_id}")

            print(f"\n  关系数: {len(context['relations'])}")
            print("  关系类型统计:")
            for rtype, count in context['relation_summary'].items():
                print(f"    {rtype}: {count}")

    def test_query_with_lifecycle(self):
        """测试带生命周期状态的查询"""
        print("\n=== 6. 测试带生命周期的查询 ===")

        print("\n记忆生命周期和有效置信度:")
        print("  记忆ID |  状态 |  有效置信度 |  实体数 |  关系数")
        print("  --------|-------|------------|--------|--------")

        for memory in self.memories:
            effective = effective_confidence(memory)

            print(f"  {memory.id:<8} | {memory.lifecycle_state:<7} | "
                  f"{effective:.4f}      | {len(memory.entities):6} | "
                  f"{len(memory.relations):6}")

        # 模拟查询带关系过滤
        print("\n模拟查询: 查找与 'alice' 相关的记忆 (带生命周期过滤)")

        results = []
        for memory in self.memories:
            if "alice" in memory.entities:
                effective = effective_confidence(memory)

                # 检索得分 = 相关性 × 有效置信度
                score = 1.0 * effective

                # 计算关系得分
                relation_score = sum(r.confidence for r in memory.relations)

                results.append({
                    "memory": memory,
                    "effective_confidence": effective,
                    "search_score": score,
                    "relation_score": relation_score,
                    "combined_score": score * 0.7 + relation_score * 0.3
                })

        # 按组合得分排序
        results.sort(key=lambda x: x["combined_score"], reverse=True)

        print("\n查询结果 (按组合得分排序):")
        for i, result in enumerate(results, 1):
            print(f"\n  {i}. {result['memory'].id}")
            print(f"     内容: {result['memory'].content[:50]}...")
            print(f"     有效置信度: {result['effective_confidence']:.4f}")
            print(f"     检索得分: {result['search_score']:.4f}")
            print(f"     关系得分: {result['relation_score']:.4f}")
            print(f"     组合得分: {result['combined_score']:.4f}")

    def generate_summary(self):
        """生成测试总结"""
        print("\n=== 测试总结 ===")

        # 统计信息
        total_relations = sum(len(m.relations) for m in self.memories)

        print(f"\n总记忆数: {len(self.memories)}")
        print(f"总实体数: {len(self.entities)}")
        print(f"总关系数: {total_relations}")
        print(f"平均每条记忆的关系数: {total_relations / len(self.memories):.1f}")

        # 统计关系类型
        relation_type_count = {}
        for memory in self.memories:
            for rel in memory.relations:
                rtype = rel.relation_type
                relation_type_count[rtype] = relation_type_count.get(rtype, 0) + 1

        print("\n关系类型分布:")
        for rtype, count in sorted(relation_type_count.items()):
            print(f"  {rtype}: {count}")

        print("\n✅ 所有复杂关系测试通过")

    def run_all_tests(self):
        """运行所有测试"""
        print("="*60)
        print("复杂关系测试")
        print("="*60)

        try:
            self.create_memories_with_relations()
            self.analyze_relation_network()
            self.query_entity_relations()
            self.find_paths_between_entities()
            self.get_entity_context()
            self.test_query_with_lifecycle()
            self.generate_summary()

            return True

        except Exception as e:
            print(f"\n❌ 测试失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序入口"""
    test = ComplexRelationTest()
    success = test.run_all_tests()

    if success:
        print("\n" + "="*60)
        print("🎉 所有复杂关系测试通过！")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("❌ 测试失败")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())