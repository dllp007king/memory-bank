"""
Similarity Detection and Update Strategies

From memory-lifecycle.md section 3.1:
- > 0.95: Overwrite update
- 0.85-0.95: Merge update
- 0.70-0.85: Link (create new, link to old)
- < 0.70: Create independently
"""

from enum import Enum
from typing import List, Optional, Tuple
from memory_bank.embedding import embed_single, cosine_similarity


class UpdateStrategy(Enum):
    """更新策略枚举"""
    OVERWRITE = "overwrite"  # 覆盖更新
    MERGE = "merge"          # 合并更新
    LINK = "link"            # 关联创建
    CREATE = "create"         # 独立创建


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两段文本的相似度

    Uses cosine similarity of embeddings.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score (0.0 - 1.0)
    """
    vec1 = embed_single(text1)
    vec2 = embed_single(text2)

    if vec1 is None or vec2 is None:
        return 0.0

    return cosine_similarity(vec1, vec2)


def get_update_strategy(similarity: float) -> UpdateStrategy:
    """
    根据相似度返回更新策略

    Args:
        similarity: Similarity score (0.0 - 1.0)

    Returns:
        Update strategy
    """
    if similarity > 0.95:
        return UpdateStrategy.OVERWRITE
    elif similarity >= 0.85:
        return UpdateStrategy.MERGE
    elif similarity >= 0.70:
        return UpdateStrategy.LINK
    else:
        return UpdateStrategy.CREATE


def find_similar_memories(
    content: str,
    existing_memories: List,
    threshold: float = 0.70
) -> List[Tuple]:
    """
    查找相似记忆

    Args:
        content: New memory content
        existing_memories: List of existing Memory objects
        threshold: Similarity threshold

    Returns:
        List of (memory, similarity) tuples, sorted by similarity desc
    """
    results = []
    for mem in existing_memories:
        if not hasattr(mem, 'content'):
            continue
        sim = calculate_similarity(content, mem.content)
        if sim >= threshold:
            results.append((mem, sim))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
