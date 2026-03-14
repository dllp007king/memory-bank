"""
更新 LanceDB Schema 添加关系历史追踪字段

为现有的 relations 表添加新字段：status, is_current, superseded_by, supersedes_target, old_confidence, replacement_reason
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))


def update_relations_schema(db_path: str = None, dry_run: bool = True):
    """
    更新 relations 表 schema 添加历史追踪字段

    LanceDB 的 schema 更新需要：
    1. 获取现有数据
    2. 删除旧表
    3. 创建新的 relations 表（包含新字段）
    4. 重新插入数据

    Args:
        db_path: LanceDB database path
        dry_run: If True, don't make changes

    Returns:
        Number of relations updated
    """
    import datetime

    try:
        import lancedb
    except ImportError:
        print("错误: 需要安装 lancedb")
        print("安装命令: pip install lancedb")
        return 0

    # 数据库路径
    if db_path is None:
        db_path = "/home/myclaw/.openclaw/workspace/.memory/lancedb"

    print(f"数据库路径: {db_path}")

    try:
        db = lancedb.connect(db_path)
    except Exception as e:
        print(f"连接数据库失败: {e}")
        return 0

    try:
        # 获取现有的 relations 表
        try:
            old_table = db.open_table("relations")
            old_count = len(old_table)
            print(f"现有关系数: {old_count}")
        except Exception as e:
            print(f"relations 表不存在或无法访问: {e}")
            db.close()
            return 0

        # 备份现有数据
        import pyarrow as pa
        old_data = old_table.to_arrow()

        # 定义新的 schema（包含历史追踪字段）
        new_schema = pa.schema([
            pa.field("id", pa.string(), nullable=False),
            pa.field("source_slug", pa.string(), nullable=False),
            pa.field("target_slug", pa.string(), nullable=False),
            pa.field("relation_type", pa.string(), nullable=False),
            pa.field("description", pa.string(), nullable=True),
            pa.field("confidence", pa.float32(), nullable=False),
            pa.field("source_memory_id", pa.string(), nullable=True),
            pa.field("created_at", pa.timestamp("us"), nullable=False),
            pa.field("updated_at", pa.timestamp("us"), nullable=False),
            pa.field("version", pa.int32(), nullable=False),
            pa.field("tags", pa.list_(pa.string()), nullable=True),
            # 新增的历史追踪字段
            pa.field("status", pa.string(), nullable=False,
                     metadata={"description": "状态: ACTIVE/SUPERSEDED/ARCHIVED/FORGOTTEN"}),
            pa.field("is_current", pa.bool_(), nullable=False,
                     metadata={"description": "是否为当前有效关系"}),
            pa.field("superseded_by", pa.string(), nullable=True,
                     metadata={"description": "取代此关系的新关系ID"}),
            pa.field("supersedes_target", pa.string(), nullable=True,
                     metadata={"description": "此关系替代的目标实体slug"}),
            pa.field("old_confidence", pa.float32(), nullable=True,
                     metadata={"description": "被替代前的置信度"}),
            pa.field("replacement_reason", pa.string(), nullable=True,
                     metadata={"description": "替代原因"}),
        ])

        print(f"新 schema 字段数: {len(new_schema)}")

        if dry_run:
            print(f"[DRY RUN] 将更新 {old_count} 条关系记录")
            print("新字段将添加默认值：")
            print("  status = 'ACTIVE'")
            print("  is_current = True")
            print("  superseded_by = ''")
            print("  supersedes_target = ''")
            print("  old_confidence = 0.0")
            print("  replacement_reason = ''")
            print("  version = 1")
            db.close()
            return old_count

        # 迁移数据
        print("迁移数据...")
        new_data = []

        # 将 pyarrow.Table 转换为字典列表
        for i in range(len(old_data)):
            row_dict = {}
            for col_name in old_data.column_names:
                col_data = old_data[col_name]
                if col_name in row_dict:
                    continue
                # 处理不同的数据类型
                value = col_data[i].as_py() if hasattr(col_data[i], 'as_py') else col_data[i]
                row_dict[col_name] = value

            new_row = {
                "id": row_dict.get("id", ""),
                "source_slug": row_dict.get("source_slug", ""),
                "target_slug": row_dict.get("target_slug", ""),
                "relation_type": row_dict.get("relation_type", ""),
                "description": row_dict.get("description", ""),
                "confidence": row_dict.get("confidence", 1.0),
                "source_memory_id": row_dict.get("source_memory_id", ""),
                "created_at": row_dict.get("created_at"),
                "updated_at": row_dict.get("updated_at"),
                "version": row_dict.get("version", 1),
                "tags": row_dict.get("tags", []),
                # 新字段默认值
                "status": "ACTIVE",
                "is_current": True,
                "superseded_by": "",
                "supersedes_target": "",
                "old_confidence": 0.0,
                "replacement_reason": "",
            }
            new_data.append(new_row)

        # 删除旧表
        print("删除旧表...")
        db.drop_table("relations")

        # 创建新的 relations 表（使用新的 schema）
        print("创建新的 relations 表...")
        final_table = db.create_table(
            "relations",
            schema=new_schema,
            mode="overwrite"
        )

        # 插入数据
        if new_data:
            final_table.add(new_data)

        print(f"Schema 更新完成！")
        print(f"  原始记录: {old_count}")
        print(f"  迁移记录: {len(new_data)}")

        return len(new_data)

    except Exception as e:
        print(f"Schema 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Update LanceDB schema for relation history tracking")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    parser.add_argument("--db-path", help="LanceDB database path")

    args = parser.parse_args()

    print("=" * 50)
    print("LanceDB Schema 更新")
    print("=" * 50)

    count = update_relations_schema(
        db_path=args.db_path,
        dry_run=args.dry_run
    )

    if args.dry_run:
        print(f"[DRY RUN] 将更新 {count} 条关系记录")
        print("运行时不加 --dry-run 参数来应用更改")
    else:
        print(f"已更新 {count} 条关系记录")
