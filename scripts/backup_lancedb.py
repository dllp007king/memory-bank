#!/usr/bin/env python3
"""
LanceDB 自动备份脚本

功能：
1. 导出为 JSON（可读）
2. 复制 LanceDB 目录（快速恢复）
3. 压缩备份文件
4. 保留最近 N 天备份
5. 可选：上传到云存储

用法：
    python backup_lancedb.py                    # 默认备份
    python backup_lancedb.py --full             # 完整备份（保留更久）
    python backup_lancedb.py --no-compress      # 不压缩
    python backup_lancedb.py --keep-days 60     # 保留60天

Cron 配置：
    # 每天凌晨 3 点备份
    0 3 * * * /path/to/backup_lancedb.py

    # 每周日凌晨 4 点完整备份
    0 4 * * 0 /path/to/backup_lancedb.py --full --keep-days 90
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# 添加 memory_bank 模块路径
sys.path.insert(0, str(Path(__file__).parent.parent))


class LanceDBBackup:
    """LanceDB 备份管理器"""

    def __init__(self, db_path=None, backup_dir=None):
        # 默认路径
        workspace = Path.home() / ".openclaw" / "workspace"
        self.db_path = Path(db_path) if db_path else workspace / ".memory" / "lancedb"
        self.backup_dir = Path(backup_dir) if backup_dir else workspace / "memory-bank" / "backups"

        # 确保备份目录存在
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def backup(self, full=False, compress=True, keep_days=30):
        """执行备份

        Args:
            full: 是否完整备份（保留更久）
            compress: 是否压缩
            keep_days: 保留天数

        Returns:
            备份路径
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_type = "full" if full else "daily"
        backup_name = f"backup_{backup_type}_{timestamp}"
        backup_path = self.backup_dir / backup_name

        print(f"📦 开始备份 LanceDB...")
        print(f"   数据库路径: {self.db_path}")
        print(f"   备份路径: {backup_path}")
        print(f"   备份类型: {backup_type}")

        # 1. 创建备份目录
        backup_path.mkdir(parents=True, exist_ok=True)

        # 2. 复制 LanceDB（快速恢复）
        print("   复制 LanceDB 数据...")
        if self.db_path.exists():
            lancedb_backup = backup_path / "lancedb"
            shutil.copytree(self.db_path, lancedb_backup)
            print(f"   ✓ LanceDB 已复制: {lancedb_backup}")
        else:
            print(f"   ⚠ LanceDB 路径不存在: {self.db_path}")

        # 3. 导出为 JSON（可读、可迁移）
        print("   导出 JSON...")
        export_path = backup_path / "export"
        export_path.mkdir(exist_ok=True)
        self._export_to_json(export_path)

        # 4. 创建元信息文件
        self._create_metadata(backup_path, backup_type)

        # 5. 压缩备份
        if compress:
            print("   压缩备份...")
            archive_path = shutil.make_archive(
                str(backup_path),
                'zip',
                backup_path
            )
            # 删除原目录
            shutil.rmtree(backup_path)
            backup_path = Path(archive_path)
            print(f"   ✓ 已压缩: {backup_path}")

        # 6. 清理旧备份
        print(f"   清理旧备份（保留 {keep_days} 天）...")
        self.cleanup_old_backups(days=keep_days, backup_type=backup_type)

        # 7. 显示统计
        self._show_stats(backup_path)

        print(f"\n✅ 备份完成: {backup_path}")
        return backup_path

    def _export_to_json(self, export_path):
        """导出为 JSON"""
        try:
            from memory_bank.lance_crud import MemoryCRUD

            crud = MemoryCRUD()

            # 导出记忆
            memories = crud.list_memories(limit=100000)
            memories_data = []
            for m in memories:
                mem_dict = m.to_dict()
                # 排除向量数据（太大）
                if 'vector' in mem_dict:
                    del mem_dict['vector']
                if 'embedding' in mem_dict:
                    del mem_dict['embedding']
                memories_data.append(mem_dict)

            with open(export_path / "memories.json", "w", encoding="utf-8") as f:
                json.dump(memories_data, f, ensure_ascii=False, indent=2)
            print(f"     ✓ 记忆: {len(memories_data)} 条")

            # 导出实体
            entities = crud.list_entities(limit=100000)
            entities_data = []
            for e in entities:
                ent_dict = e.to_dict()
                # 排除向量数据
                if 'vector' in ent_dict:
                    del ent_dict['vector']
                if 'embedding' in ent_dict:
                    del ent_dict['embedding']
                entities_data.append(ent_dict)

            with open(export_path / "entities.json", "w", encoding="utf-8") as f:
                json.dump(entities_data, f, ensure_ascii=False, indent=2)
            print(f"     ✓ 实体: {len(entities_data)} 个")

            # 导出关系
            relations = crud.list_relations(limit=100000)
            relations_data = [r.to_dict() for r in relations]

            with open(export_path / "relations.json", "w", encoding="utf-8") as f:
                json.dump(relations_data, f, ensure_ascii=False, indent=2)
            print(f"     ✓ 关系: {len(relations_data)} 条")

        except Exception as e:
            print(f"     ⚠ 导出失败: {e}")

    def _create_metadata(self, backup_path, backup_type):
        """创建元信息文件"""
        metadata = {
            "backup_time": datetime.now().isoformat(),
            "backup_type": backup_type,
            "db_path": str(self.db_path),
            "version": "2.0",
            "python_version": sys.version,
        }

        with open(backup_path / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)

    def _show_stats(self, backup_path):
        """显示统计信息"""
        if backup_path.is_file():
            size = backup_path.stat().st_size
            size_mb = size / (1024 * 1024)
            print(f"   备份大小: {size_mb:.2f} MB")

        # 统计备份数量
        backups = list(self.backup_dir.glob("backup_*.zip"))
        print(f"   总备份数: {len(backups)} 个")

    def cleanup_old_backups(self, days=30, backup_type=None):
        """清理旧备份

        Args:
            days: 保留天数
            backup_type: 备份类型（None 表示所有类型）
        """
        cutoff = datetime.now() - timedelta(days=days)

        # 查找备份文件
        pattern = f"backup_{backup_type}_*.zip" if backup_type else "backup_*.zip"
        backups = sorted(self.backup_dir.glob(pattern))

        deleted_count = 0
        for backup in backups:
            # 从文件名提取时间戳
            try:
                timestamp_str = backup.stem.split("_")[-1]
                backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")

                if backup_time < cutoff:
                    backup.unlink()
                    deleted_count += 1
            except (ValueError, IndexError):
                continue

        if deleted_count > 0:
            print(f"   已删除 {deleted_count} 个旧备份")

    def restore(self, backup_path):
        """从备份恢复

        Args:
            backup_path: 备份文件路径（.zip）
        """
        backup_path = Path(backup_path)

        if not backup_path.exists():
            raise FileNotFoundError(f"备份文件不存在: {backup_path}")

        print(f"🔄 开始恢复 LanceDB...")
        print(f"   备份文件: {backup_path}")

        # 1. 解压备份
        if backup_path.suffix == ".zip":
            print("   解压备份...")
            temp_dir = backup_path.parent / f"restore_temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.unpack_archive(backup_path, temp_dir)
            backup_dir = temp_dir
        else:
            backup_dir = backup_path

        # 2. 恢复 LanceDB
        lancedb_backup = backup_dir / "lancedb"
        if lancedb_backup.exists():
            print(f"   恢复 LanceDB 到: {self.db_path}")

            # 备份当前数据库（以防万一）
            if self.db_path.exists():
                current_backup = self.db_path.parent / f"lancedb_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                shutil.move(self.db_path, current_backup)
                print(f"   当前数据库已备份到: {current_backup}")

            # 恢复
            shutil.copytree(lancedb_backup, self.db_path)
            print("   ✓ LanceDB 已恢复")
        else:
            print("   ⚠ 备份中没有 LanceDB 数据")

        # 3. 清理临时文件
        if backup_path.suffix == ".zip" and temp_dir.exists():
            shutil.rmtree(temp_dir)

        print(f"\n✅ 恢复完成！")
        print("   请重启记忆银行服务以应用更改")

    def list_backups(self):
        """列出所有备份"""
        backups = sorted(self.backup_dir.glob("backup_*.zip"))

        if not backups:
            print("没有找到备份文件")
            return

        print(f"📋 备份列表（共 {len(backups)} 个）:")
        print("=" * 80)

        for backup in backups:
            stat = backup.stat()
            size_mb = stat.st_size / (1024 * 1024)
            mtime = datetime.fromtimestamp(stat.st_mtime)

            # 提取备份类型
            parts = backup.stem.split("_")
            backup_type = parts[1] if len(parts) > 1 else "unknown"

            print(f"  {backup.name:<40} {size_mb:>6.2f} MB  {mtime.strftime('%Y-%m-%d %H:%M')}  [{backup_type}]")


def main():
    parser = argparse.ArgumentParser(description="LanceDB 备份工具")
    parser.add_argument("--full", action="store_true", help="完整备份（保留更久）")
    parser.add_argument("--no-compress", action="store_true", help="不压缩备份")
    parser.add_argument("--keep-days", type=int, default=30, help="保留天数（默认30天）")
    parser.add_argument("--db-path", help="数据库路径")
    parser.add_argument("--backup-dir", help="备份目录")
    parser.add_argument("--restore", metavar="BACKUP_FILE", help="从备份恢复")
    parser.add_argument("--list", action="store_true", help="列出所有备份")

    args = parser.parse_args()

    backup = LanceDBBackup(db_path=args.db_path, backup_dir=args.backup_dir)

    if args.list:
        backup.list_backups()
    elif args.restore:
        backup.restore(args.restore)
    else:
        backup.backup(
            full=args.full,
            compress=not args.no_compress,
            keep_days=args.keep_days
        )


if __name__ == "__main__":
    main()
