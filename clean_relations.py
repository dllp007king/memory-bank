"""
清理重复关系

删除数据库中的所有重复关系，只保留每组关系的第一个。
"""

import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from memory_bank.lance_crud import get_crud


def clean_duplicate_relations():
    """清理重复关系"""
    crud = get_crud()

    # 获取所有关系
    all_relations = crud.list_relations(limit=10000)
    print(f"总关系数: {len(all_relations)}")

    # 按 (source, target, relation_type) 分组
    groups = {}
    for rel in all_relations:
        key = (rel.source, rel.target, rel.relation_type)
        if key not in groups:
            groups[key] = []
        groups[key].append(rel)

    print(f"唯一关系组数: {len(groups)}")

    # 统计重复
    duplicate_count = 0
    total_duplicates = 0

    for key, relations in groups.items():
        if len(relations) > 1:
            duplicate_count += 1
            total_duplicates += len(relations) - 1
            source, target, rel_type = key
            print(f"\n重复关系: {source} -> {rel_type} -> {target}")
            print(f"  数量: {len(relations)}")
            for rel in relations:
                print(f"    ID: {rel.id}, 创建时间: {rel.created_at}")

    print(f"\n总结:")
    print(f"  重复的关系组: {duplicate_count}")
    print(f"  总重复数: {total_duplicates}")
    print(f"  清理后预期关系数: {len(groups)}")

    # 询问是否清理
    response = input("\n是否清理所有关系并重新导入？(yes/no): ")
    if response.lower() != 'yes':
        print("取消清理")
        return

    # 删除所有关系
    print("\n删除所有关系...")

    # LanceDB 直接删除表
    table = crud._get_relations_table()

    # 获取表名并删除
    table_name = "relations"
    db = crud.conn
    try:
        db.drop_table(table_name)
        print(f"已删除表: {table_name}")
    except Exception as e:
        print(f"删除表失败: {e}")

    # 重新初始化 Schema（会重建表）
    print("重新初始化 Schema...")
    crud._init_schema()

    # 从唯一关系组中重建
    print("重建关系表...")
    success_count = 0
    for key, relations in groups.items():
        # 只保留每组第一个关系
        first_rel = relations[0]
        try:
            crud.create_relation(
                source=first_rel.source,
                target=first_rel.target,
                relation_type=first_rel.relation_type,
                properties=first_rel.properties,
                confidence=first_rel.confidence,
                source_memory=first_rel.source_memory,
            )
            success_count += 1
        except Exception as e:
            print(f"  创建关系失败: {e}")

    # 验证结果
    final_count = len(crud.list_relations(limit=10000))
    print(f"\n清理完成！")
    print(f"成功重建关系数: {success_count}")
    print(f"最终关系数: {final_count}")


if __name__ == '__main__':
    print("=" * 60)
    print("清理重复关系")
    print("=" * 60)
    clean_duplicate_relations()
