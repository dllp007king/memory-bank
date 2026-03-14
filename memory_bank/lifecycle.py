"""
Memory Lifecycle Management

Core formulas from memory-lifecycle.md:
- effective = confidence × e^(-λ × days)
- cleanup = (1 - importance) × (1 - effective) × days
- distill = importance × access_count × days
"""

import math
from datetime import datetime
from typing import Dict, List

# ============================================================================
# Decay Rate Patterns (from memory-lifecycle.md section 2.4)
# ============================================================================

STABILITY_PATTERNS: Dict[float, List[str]] = {
    # 恒定 - 永久性词汇
    0.0001: ["永远是", "始终", "永远", "必然", "一定", "真理"],

    # 长期 - 身份和特质
    0.001: ["我是", "我会", "我的", "相信", "价值观", "性格", "习惯"],

    # 中期 - 状态和关系
    0.01: ["正在", "当前", "现在", "最近", "这个月", "项目"],

    # 短期 - 计划和意图
    0.05: ["打算", "计划", "下周", "准备", "想要", "将要"],

    # 即时 - 瞬时状态
    0.2: ["今天", "此刻", "马上", "现在就"],
}

# Default decay rate (medium-term)
DEFAULT_DECAY_RATE = 0.01

# ============================================================================
# Core Formulas
# ============================================================================

def effective_confidence(memory) -> float:
    """
    有效置信度 = 基础置信度 × 时间衰减

    Args:
        memory: Memory object with confidence, decay_rate, timestamp/created_at attributes

    Returns:
        Effective confidence (0.0 - 1.0)
    """
    # Try to get timestamp from various possible attribute names
    timestamp = getattr(memory, 'timestamp', None) or getattr(memory, 'created_at', None)
    if timestamp is None:
        timestamp = datetime.now()
    elif isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)

    days = (datetime.now() - timestamp).total_seconds() / 86400
    decay = math.exp(-memory.decay_rate * days)
    return memory.confidence * decay


def infer_decay_rate(content: str) -> float:
    """
    从内容推断衰减率

    Args:
        content: Memory content

    Returns:
        Decay rate (default 0.01 if no pattern matches)
    """
    for rate, patterns in STABILITY_PATTERNS.items():
        for pattern in patterns:
            if pattern in content:
                return rate
    return DEFAULT_DECAY_RATE


def cleanup_priority(memory) -> float:
    """
    清理优先级（越高越应该清理）

    priority = (1 - importance) × (1 - effective) × days

    Args:
        memory: Memory object with importance, confidence, decay_rate, timestamp/created_at

    Returns:
        Cleanup priority score
    """
    effective = effective_confidence(memory)
    timestamp = getattr(memory, 'timestamp', None) or getattr(memory, 'created_at', None)
    if timestamp is None:
        timestamp = datetime.now()
    elif isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    days = (datetime.now() - timestamp).total_seconds() / 86400
    return (1 - memory.importance) * (1 - effective) * days


def distill_priority(memory) -> float:
    """
    提炼优先级（越高越应该提炼成知识）

    priority = importance × access_count × days

    Args:
        memory: Memory object with importance, access_count, timestamp/created_at

    Returns:
        Distill priority score
    """
    timestamp = getattr(memory, 'timestamp', None) or getattr(memory, 'created_at', None)
    if timestamp is None:
        timestamp = datetime.now()
    elif isinstance(timestamp, str):
        timestamp = datetime.fromisoformat(timestamp)
    days = (datetime.now() - timestamp).total_seconds() / 86400
    return memory.importance * memory.access_count * days


def should_keep(memory) -> bool:
    """
    判断是否应该保留记忆

    Args:
        memory: Memory object with importance, confidence, decay_rate, timestamp/created_at

    Returns:
        True if memory should be kept
    """
    effective = effective_confidence(memory)

    # 重要且可信 → 始终保留
    if memory.importance > 0.8 and effective > 0.5:
        return True

    # 不重要且不可信 → 清理
    if memory.importance < 0.3 and effective < 0.3:
        return False

    # 其他情况根据有效置信度判断
    return effective > 0.1


# ============================================================================
# Lifecycle State Constants
# ============================================================================

class LifecycleState:
    """生命周期状态常量"""
    ACTIVE = "ACTIVE"       # 活跃记忆，正常检索
    ARCHIVED = "ARCHIVED"   # 已归档，降低检索权重
    SUPERSEDED = "SUPERSEDED"  # 已被取代，仅保留历史
    FORGOTTEN = "FORGOTTEN"    # 已遗忘，标记待删除
