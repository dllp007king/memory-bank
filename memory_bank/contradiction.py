"""
Contradiction Detection and Resolution

From memory-lifecycle.md section 3.2:
- new_effective > old_effective + 0.15: UPDATE
- old_effective > new_effective + 0.15: KEEP
- Otherwise: CONFIRM (needs user confirmation)
"""

from enum import Enum
from memory_bank.lifecycle import effective_confidence


class ContradictionResolution(Enum):
    """矛盾解决策略"""
    UPDATE = "update"      # 更新旧记忆
    KEEP = "keep"          # 保留旧记忆
    CONFIRM = "confirm"    # 需要用户确认


def handle_contradiction(old, new) -> ContradictionResolution:
    """
    处理矛盾信息

    Uses effective confidence comparison with 0.15 threshold.

    Args:
        old: Old Memory object
        new: New Memory object

    Returns:
        Resolution strategy
    """
    old_effective = effective_confidence(old)
    new_effective = new.confidence  # New memory has no decay yet

    if new_effective > old_effective + 0.15:
        return ContradictionResolution.UPDATE
    elif old_effective > new_effective + 0.15:
        return ContradictionResolution.KEEP
    else:
        return ContradictionResolution.CONFIRM


def detect_contradiction(mem1_content: str, mem2_content: str) -> bool:
    """
    矛盾检测（关键词对立 + 否定词检测）

    Args:
        mem1_content: First memory content
        mem2_content: Second memory content

    Returns:
        True if contradiction detected
    """
    # 简化：检查矛盾模式
    negation_pairs = [
        ("喜欢", ["不喜欢", "不再喜欢", "不爱了", "不再爱"]),
        ("爱", ["不爱", "不再爱", "不爱了"]),
        ("会", ["不会", "不再会", "不会了"]),
        ("能", ["不能", "不再能", "不能了"]),
    ]

    content1 = mem1_content.lower()
    content2 = mem2_content.lower()

    for pos, neg_list in negation_pairs:
        # 检查是否有相反的含义
        for neg in neg_list:
            # 检查是否一个包含正面，另一个包含负面
            has_pos_1 = pos in content1
            has_neg_1 = neg in content1
            has_pos_2 = pos in content2
            has_neg_2 = neg in content2

            if (has_pos_1 and has_neg_2) or (has_pos_2 and has_neg_1):
                return True

    return False
