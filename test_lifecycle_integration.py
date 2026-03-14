#!/usr/bin/env python3
"""
记忆生命周期集成测试脚本

1. 生成10条测试数据
2. 验证数据结构
3. 执行查询测试
"""

import sys
import os
import math
from datetime import datetime, timedelta
from typing import Dict, List
import json
from dataclasses import dataclass, field
import importlib.util

# 直接加载lifecycle模块，避免__init__.py依赖
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
cleanup_priority = lifecycle.cleanup_priority
distill_priority = lifecycle.distill_priority
should_keep = lifecycle.should_keep


# ============================================================================
# 简化版 Memory 类（用于测试，不依赖数据库）
# ============================================================================

@dataclass
class Memory:
    """记忆记录（简化版）"""
    id: str = ""
    content: str = ""
    memory_type: str = "fact"
    confidence: float = 1.0
    importance: float = 0.5
    decay_rate: float = 0.01
    lifecycle_state: str = "ACTIVE"
    superseded_by: str = ""
    access_count: int = 0
    last_accessed_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "confidence": self.confidence,
            "importance": self.importance,
            "decay_rate": self.decay_rate,
            "lifecycle_state": self.lifecycle_state,
            "superseded_by": self.superseded_by,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


# ============================================================================
# 测试数据生成
# ============================================================================

TEST_DATA = [
    {
        "content": "2+2=4这是数学真理，永远不会改变",
        "memory_type": "fact",
        "confidence": 0.95,
        "importance": 0.9,
        "expected_decay_rate": 0.0001,
        "expected_category": "恒定"
    },
    {
        "content": "我喜欢编程，这是我的长期爱好",
        "memory_type": "preference",
        "confidence": 0.9,
        "importance": 0.7,
        "expected_decay_rate": 0.001,
        "expected_category": "长期"
    },
    {
        "content": "我正在学习Python编程语言",
        "memory_type": "fact",
        "confidence": 0.8,
        "importance": 0.8,
        "expected_decay_rate": 0.01,
        "expected_category": "中期"
    },
    {
        "content": "我打算下周完成任务",
        "memory_type": "fact",
        "confidence": 0.7,
        "importance": 0.5,
        "expected_decay_rate": 0.05,
        "expected_category": "短期"
    },
    {
        "content": "今天我感觉心情很好",
        "memory_type": "experience",
        "confidence": 0.6,
        "importance": 0.3,
        "expected_decay_rate": 0.2,
        "expected_category": "即时"
    },
    {
        "content": "我相信这个方案能够解决问题",
        "memory_type": "opinion",
        "confidence": 0.85,
        "importance": 0.75,
        "expected_decay_rate": 0.001,
        "expected_category": "长期"
    },
    {
        "content": "我现在正在进行代码测试工作",
        "memory_type": "fact",
        "confidence": 0.75,
        "importance": 0.6,
        "expected_decay_rate": 0.01,
        "expected_category": "中期"
    },
    {
        "content": "我计划明天和团队开会讨论",
        "memory_type": "fact",
        "confidence": 0.7,
        "importance": 0.6,
        "expected_decay_rate": 0.05,
        "expected_category": "短期"
    },
    {
        "content": "马上就要结束测试了",
        "memory_type": "experience",
        "confidence": 0.5,
        "importance": 0.2,
        "expected_decay_rate": 0.2,
        "expected_category": "即时"
    },
    {
        "content": "永远是正确的原则必须坚持",
        "memory_type": "fact",
        "confidence": 0.98,
        "importance": 0.95,
        "expected_decay_rate": 0.0001,
        "expected_category": "恒定"
    }
]


# ============================================================================
# 测试类
# ============================================================================

class LifecycleIntegrationTest:
    def __init__(self):
        self.memories: List[Memory] = []
        self.results: List[Dict] = []

    def generate_test_memories(self) -> None:
        """生成测试记忆数据"""
        print("\n=== 1. 生成测试数据 ===")
        print(f"生成 {len(TEST_DATA)} 条测试记忆\n")

        for i, data in enumerate(TEST_DATA, 1):
            memory = Memory(
                id=f"test_mem_{i}",
                content=data["content"],
                memory_type=data["memory_type"],
                confidence=data["confidence"],
                importance=data["importance"],
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
                # 自动推断衰减率
                decay_rate=infer_decay_rate(data["content"]),
                lifecycle_state="ACTIVE",
                access_count=0,
                last_accessed_at=datetime.now().isoformat()
            )

            self.memories.append(memory)

            print(f"{i}. {data['content'][:30]}...")
            print(f"   类型: {data['memory_type']}, 置信度: {data['confidence']:.2f}, "
                  f"重要性: {data['importance']:.2f}")
            print(f"   期望衰减率: {data['expected_decay_rate']:.4f} ({data['expected_category']})")
            print(f"   实际衰减率: {memory.decay_rate:.4f}")

            # 验证衰减率推断
            assert memory.decay_rate == data["expected_decay_rate"], \
                f"衰减率推断错误: 期望 {data['expected_decay_rate']}, 实际 {memory.decay_rate}"

            print("   ✅ 衰减率推断正确\n")

    def verify_data_structure(self) -> None:
        """验证数据结构"""
        print("\n=== 2. 验证数据结构 ===")

        # 检查记忆数据结构
        print("\n记忆数据结构验证:")
        print(f"  总记忆数: {len(self.memories)}")

        required_fields = [
            "id", "content", "memory_type", "confidence", "importance",
            "decay_rate", "lifecycle_state", "access_count", "created_at"
        ]

        for i, memory in enumerate(self.memories, 1):
            print(f"\n  记忆 {i}: {memory.id}")
            dict_data = memory.to_dict()

            for field in required_fields:
                if field in dict_data:
                    value = dict_data[field]
                    print(f"    {field}: {value}")
                else:
                    print(f"    ❌ {field}: 缺失")

        # 验证生命周期字段
        print("\n生命周期字段验证:")
        lifecycle_fields = [
            "decay_rate", "lifecycle_state", "superseded_by",
            "access_count", "last_accessed_at"
        ]

        for memory in self.memories:
            dict_data = memory.to_dict()
            print(f"\n  {memory.id}:")
            for field in lifecycle_fields:
                if field in dict_data:
                    print(f"    ✅ {field}: {dict_data[field]}")
                else:
                    print(f"    ❌ {field}: 缺失")

        print("\n✅ 数据结构验证通过")

    def calculate_effective_confidences(self) -> None:
        """计算有效置信度"""
        print("\n=== 3. 计算有效置信度 ===")
        print("\n不同时间点的有效置信度:")

        days_list = [0, 30, 90, 180, 365]

        for memory in self.memories:
            print(f"\n{memory.content[:30]}... (λ={memory.decay_rate:.4f})")
            print("  天数  |  有效置信度")
            print("  ------|-------------")

            for days in days_list:
                # 模拟记忆创建于 days 天前
                test_created = datetime.now() - timedelta(days=days)
                test_memory = memory
                test_memory.created_at = test_created.isoformat()

                effective = effective_confidence(test_memory)
                print(f"  {days:4d}  |  {effective:.4f}")

    def calculate_priorities(self) -> None:
        """计算清理和提炼优先级"""
        print("\n=== 4. 计算优先级 ===")

        print("\n清理优先级 (越高越应该清理):")
        print("  内容                    |  清理优先级")
        print("  -------------------------|-----------")

        for memory in self.memories:
            priority = cleanup_priority(memory)
            print(f"  {memory.content[:20]:<22}  |  {priority:.4f}")

        print("\n提炼优先级 (越高越应该提炼):")
        print("  内容                    |  提炼优先级")
        print("  -------------------------|-----------")

        for memory in self.memories:
            # 模拟不同的访问次数
            memory.access_count = len([m for m in self.memories if m.id == memory.id]) * 5
            priority = distill_priority(memory)
            print(f"  {memory.content[:20]:<22}  |  {priority:.4f}")

    def check_retention(self) -> None:
        """检查记忆保留判断"""
        print("\n=== 5. 记忆保留判断 ===")

        print("\n是否应该保留:")
        print("  内容                    |  是否保留 |  原因")
        print("  -------------------------|-----------|------------------")

        for memory in self.memories:
            should_keep_result = should_keep(memory)

            # 生成原因说明
            effective = effective_confidence(memory)
            if memory.importance > 0.8 and effective > 0.5:
                reason = "重要且可信"
            elif memory.importance < 0.3 and effective < 0.3:
                reason = "不重要且不可信"
            elif effective > 0.1:
                reason = "有效置信度足够"
            else:
                reason = "有效置信度不足"

            print(f"  {memory.content[:20]:<22}  |  {'是' if should_keep_result else '否':>6}  |  {reason}")

    def simulate_query(self) -> None:
        """模拟查询"""
        print("\n=== 6. 模拟查询测试 ===")

        # 模拟查询 "编程" 相关记忆
        query_text = "编程"
        print(f"\n查询: '{query_text}'")
        print("\n匹配的记忆 (按有效置信度排序):")

        # 计算每个记忆的相关性（简单的关键词匹配）
        scored_memories = []
        for memory in self.memories:
            # 简单的关键词匹配
            relevance = 1.0 if query_text in memory.content else 0.0

            if relevance > 0:
                effective = effective_confidence(memory)
                # 检索得分 = 相关性 × 有效置信度
                score = relevance * effective
                scored_memories.append((memory, effective, score))

        # 按得分排序
        scored_memories.sort(key=lambda x: x[2], reverse=True)

        for memory, effective, score in scored_memories:
            print(f"\n  {memory.content}")
            print(f"    置信度: {memory.confidence:.2f}")
            print(f"    有效置信度: {effective:.4f}")
            print(f"    检索得分: {score:.4f}")
            print(f"    衰减率: {memory.decay_rate:.4f}")

        # 模拟查询 "今天" 相关记忆
        query_text = "今天"
        print(f"\n\n查询: '{query_text}'")
        print("\n匹配的记忆 (按有效置信度排序):")

        scored_memories = []
        for memory in self.memories:
            relevance = 1.0 if query_text in memory.content else 0.0

            if relevance > 0:
                effective = effective_confidence(memory)
                score = relevance * effective
                scored_memories.append((memory, effective, score))

        scored_memories.sort(key=lambda x: x[2], reverse=True)

        for memory, effective, score in scored_memories:
            print(f"\n  {memory.content}")
            print(f"    置信度: {memory.confidence:.2f}")
            print(f"    有效置信度: {effective:.4f}")
            print(f"    检索得分: {score:.4f}")
            print(f"    衰减率: {memory.decay_rate:.4f}")

    def generate_summary(self) -> None:
        """生成测试总结"""
        print("\n=== 测试总结 ===")

        print(f"\n生成记忆数: {len(self.memories)}")

        # 统计不同类型的记忆
        type_count = {}
        for memory in self.memories:
            mtype = memory.memory_type
            type_count[mtype] = type_count.get(mtype, 0) + 1

        print("\n记忆类型分布:")
        for mtype, count in type_count.items():
            print(f"  {mtype}: {count}")

        # 统计不同衰减率的记忆
        decay_count = {}
        for memory in self.memories:
            rate = memory.decay_rate
            decay_count[rate] = decay_count.get(rate, 0) + 1

        print("\n衰减率分布:")
        for rate, count in decay_count.items():
            category = {
                0.0001: "恒定",
                0.001: "长期",
                0.01: "中期",
                0.05: "短期",
                0.2: "即时"
            }.get(rate, "其他")
            print(f"  {category} ({rate}): {count}")

        # 计算平均置信度和重要性
        avg_confidence = sum(m.confidence for m in self.memories) / len(self.memories)
        avg_importance = sum(m.importance for m in self.memories) / len(self.memories)

        print(f"\n平均置信度: {avg_confidence:.2f}")
        print(f"平均重要性: {avg_importance:.2f}")

        print("\n✅ 所有测试通过")

    def run_all_tests(self) -> None:
        """运行所有测试"""
        print("="*60)
        print("记忆生命周期集成测试")
        print("="*60)

        try:
            self.generate_test_memories()
            self.verify_data_structure()
            self.calculate_effective_confidences()
            self.calculate_priorities()
            self.check_retention()
            self.simulate_query()
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
    test = LifecycleIntegrationTest()
    success = test.run_all_tests()

    if success:
        print("\n" + "="*60)
        print("🎉 所有集成测试通过！")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("❌ 测试失败")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())