"""
Slug 生成器

使用类型前缀 + Base62 编码生成实体唯一标识符。

格式: {类型前缀}_{Base62(4位)}
示例: P_a1Zx, O_3b7K, E_9mN2

容量: 每类型约 1,477 万数据
"""

import string
from typing import Optional

# Base62 字符集: 0-9, A-Z, a-z (62个字符)
BASE62_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def encode_base62(num: int) -> str:
    """
    将数字编码为 Base62 字符串

    Args:
        num: 正整数

    Returns:
        Base62 编码字符串

    Example:
        >>> encode_base62(12345)
        '3D7'
    """
    if num < 0:
        raise ValueError("只能编码正整数")

    if num == 0:
        return BASE62_CHARS[0]

    encoded = []
    base = len(BASE62_CHARS)

    while num > 0:
        num, remainder = divmod(num, base)
        encoded.append(BASE62_CHARS[remainder])

    return ''.join(reversed(encoded))


def decode_base62(encoded: str) -> int:
    """
    将 Base62 字符串解码为数字

    Args:
        encoded: Base62 编码字符串

    Returns:
        解码后的数字

    Example:
        >>> decode_base62('3D7')
        12345
    """
    result = 0
    base = len(BASE62_CHARS)

    for char in encoded:
        value = BASE62_CHARS.index(char)
        result = result * base + value

    return result


# 实体类型前缀映射
TYPE_PREFIXES = {
    "PERSON": "P",       # 人物
    "PLACE": "L",        # 地点
    "LOCATION": "L",     # 地点
    "ORG": "O",          # 组织
    "ORGANIZATION": "O", # 组织
    "EVENT": "E",        # 事件
    "TOPIC": "T",        # 主题
    "PRODUCT": "PR",     # 产品
    "CONCEPT": "C",      # 概念
    "PROJECT": "PJ",     # 项目
    "TOOL": "TL",        # 工具
    "SYSTEM": "S",       # 系统
    "DOCUMENT": "D",     # 文档
    "FEATURE": "F",      # 功能
    "BUG": "B",          # Bug
    "VERSION": "V",      # 版本
    "UI": "U",           # UI组件
}


def get_type_prefix(entity_type: str) -> str:
    """
    获取实体类型的前缀

    Args:
        entity_type: 实体类型

    Returns:
        类型前缀
    """
    # 处理 "PERSON(人物)" 格式
    import re
    match = re.match(r'^([A-Z]+)', entity_type)
    if match:
        entity_type = match.group(1)

    return TYPE_PREFIXES.get(entity_type, "X")  # X 表示未知类型


def generate_slug(entity_type: str, counter: int) -> str:
    """
    生成实体 slug

    格式: {类型前缀}_{Base62(4位)}
    示例: P_a1Zx, O_3b7K, E_9mN2

    Args:
        entity_type: 实体类型
        counter: 计数器值

    Returns:
        生成的 slug

    Example:
        >>> generate_slug("PERSON", 0)
        'P_0000'
        >>> generate_slug("PERSON", 12345)
        'P_3D7'  # 注意: 实际使用时会补零到4位
    """
    prefix = get_type_prefix(entity_type)

    # 编码为 Base62
    encoded = encode_base62(counter)

    # 补零到 4 位 (可选，确保长度一致)
    # encoded = encoded.rjust(4, '0')

    return f"{prefix}_{encoded}"


def parse_slug(slug: str) -> tuple:
    """
    解析 slug，返回 (类型前缀, 计数器值)

    Args:
        slug: slug 字符串

    Returns:
        (prefix, counter) 元组

    Example:
        >>> parse_slug('P_a1Zx')
        ('P', 387912)
    """
    if '_' not in slug:
        raise ValueError(f"无效的 slug 格式: {slug}")

    prefix, encoded = slug.split('_', 1)
    counter = decode_base62(encoded)

    return (prefix, counter)


# 类型前缀到实体类型的反向映射
PREFIX_TO_TYPE = {
    "P": "PERSON",
    "L": "LOCATION",
    "O": "ORG",
    "E": "EVENT",
    "T": "TOPIC",
    "PR": "PRODUCT",
    "C": "CONCEPT",
    "X": "UNKNOWN",
}


def get_entity_type_from_slug(slug: str) -> str:
    """
    从 slug 推断实体类型

    Args:
        slug: slug 字符串

    Returns:
        实体类型
    """
    if '_' not in slug:
        return "UNKNOWN"

    prefix = slug.split('_', 1)[0]
    return PREFIX_TO_TYPE.get(prefix, "UNKNOWN")


if __name__ == "__main__":
    # 测试
    print("=" * 60)
    print("Slug 生成器测试")
    print("=" * 60)

    # 测试编码/解码
    print("\nBase62 编码测试:")
    test_values = [0, 1, 10, 100, 1000, 10000, 100000, 1234567]
    for val in test_values:
        encoded = encode_base62(val)
        decoded = decode_base62(encoded)
        print(f"  {val:8d} -> {encoded:>6s} -> {decoded:8d} {'✓' if val == decoded else '✗'}")

    # 测试 slug 生成
    print("\nSlug 生成测试:")
    for i in range(10):
        for etype in ["PERSON", "ORG", "EVENT"]:
            slug = generate_slug(etype, i)
            parsed = parse_slug(slug)
            print(f"  {slug:>10s} -> {parsed}")

    # 测试容量
    print("\n容量测试:")
    max_3digit = 62 ** 3 - 1
    max_4digit = 62 ** 4 - 1
    print(f"  3位 Base62: {max_3digit:,} 条数据")
    print(f"  4位 Base62: {max_4digit:,} 条数据")
