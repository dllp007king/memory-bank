"""
迁移 memories 表：添加 tags 字段

LanceDB schema 更新需要：
1. 读取现有数据
2. 删除旧表
3. 创建带 tags 字段的新表
4. 重新插入数据
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_bank.lance_schema import MEMORIES_SCHEMA


def add_tags_to_memories(db_path: str = None, dry_run: bool = True):
    """
    给 memories 表添加 tags 字段

    Args:
        db_path: LanceDB database path
        dry_run: If True, don't make changes
    """
    try:
        import lancedb
    except ImportError:
        print("错误: 需要安装 lancedb")
        return 0

    # 数据库路径
    if db_path is None:
        db_path = str(Path.home() / ".openclaw" / "workspace" / ".memory" / "lancedb")

    print(f"连接数据库: {db_path}")

    db = lancedb.connect(db_path)

    # 检查表是否存在
    tables = db.list_tables()
    # list_tables() 返回 ListTablesResponse，需要 .tables 取列表
    table_list = tables.tables if hasattr(tables, 'tables') else list(tables)
    if 'memories' not in table_list:
        print("表 memories 不存在，跳过")
        return 0

    table = db.open_table('memories')
    print(f"当前 memories 表字段: {[f.name for f in table.schema]}")

    # 读取所有数据
    print("读取现有数据...")
    all_data = table.search().to_list()
    old_count = len(all_data)
    print(f"现有记录数: {old_count}")

    if old_count == 0:
        print("表为空，跳过数据迁移")
        old_count_check = 0
    else:
        old_count_check = old_count

    if dry_run:
        print(f"\n[DRY RUN] 将为 {old_count_check} 条记录添加 tags: [] 字段")
        print("运行时不加 --dry-run 参数来应用更改")
        return old_count_check

    # 给每条记录添加 tags 字段
    print("添加 tags 字段到每条记录...")
    new_data = []
    for row in all_data:
        row_dict = dict(row)
        # 添加 tags 字段（默认为空列表）
        row_dict["tags"] = row_dict.get("tags", [])
        new_data.append(row_dict)

    # 删除旧表
    print("删除旧表...")
    db.drop_table("memories")

    # 用新 schema 创建表
    print("创建新的 memories 表（带 tags 字段）...")
    new_table = db.create_table(
        "memories",
        schema=MEMORIES_SCHEMA,
        mode="overwrite"
    )

    # 重新插入数据
    if new_data:
        print(f"插入 {len(new_data)} 条记录...")
        new_table.add(new_data)

    # 验证
    verify_table = db.open_table("memories")
    verify_fields = [f.name for f in verify_table.schema]
    verify_count = len(verify_table.search().to_list())

    print(f"\n✅ 迁移完成！")
    print(f"  迁移记录: {len(new_data)}")
    print(f"  验证记录: {verify_count}")
    print(f"  新字段: {verify_fields}")

    return len(new_data)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="给 memories 表添加 tags 字段")
    parser.add_argument("--dry-run", action="store_true", help="不要实际修改")
    parser.add_argument("--db-path", help="LanceDB 数据库路径")

    args = parser.parse_args()

    print("=" * 50)
    print("Memories 表 Schema 迁移：添加 tags 字段")
    print("=" * 50)

    count = add_tags_to_memories(
        db_path=args.db_path,
        dry_run=args.dry_run
    )

    if args.dry_run:
        print(f"\n[DRY RUN] 共 {count} 条记录待迁移")
    else:
        print(f"\n✅ 已完成，共迁移 {count} 条记录")
