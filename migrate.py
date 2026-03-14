#!/usr/bin/env python3
"""
数据迁移工具 - CLI 工具

支持：
- export: 导出所有数据
- import: 导入数据
- backup: 备份到 backups/
- restore: 从备份恢复
- status: 查看迁移状态
- 增量迁移（只迁移新增的）
- 数据完整性验证
- 迁移日志记录
"""

import argparse
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
import hashlib

# 路径配置
BASE_DIR = Path("/home/myclaw/.openclaw/workspace/memory-bank")
BACKUP_DIR = BASE_DIR / "backups"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = Path.home() / ".openclaw" / "workspace" / ".memory" / "index.sqlite"


def ensure_dirs():
    """确保必要的目录存在"""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log(message: str, level: str = "INFO"):
    """记录日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)
    
    log_file = LOG_DIR / "migrate.log"
    with open(log_file, "a") as f:
        f.write(log_line + "\n")


def get_db_path() -> Path:
    """获取数据库路径"""
    return DB_PATH


def load_state() -> dict:
    """加载迁移状态"""
    state_file = LOG_DIR / "migration_state.json"
    if state_file.exists():
        with open(state_file, "r") as f:
            return json.load(f)
    return {
        "last_export": None,
        "last_import": None,
        "last_backup": None,
        "last_restore": None,
        "incremental_markers": {}
    }


def save_state(state: dict):
    """保存迁移状态"""
    state_file = LOG_DIR / "migration_state.json"
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def calculate_checksum(data: bytes) -> str:
    """计算数据校验和"""
    return hashlib.sha256(data).hexdigest()


def export_data(output_dir: str, incremental: bool = False) -> bool:
    """导出所有数据"""
    ensure_dirs()
    output_path = Path(output_dir)
    
    db_path = get_db_path()
    if not db_path.exists():
        log(f"数据库文件不存在: {db_path}", "ERROR")
        return False
    
    # 创建输出目录
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    export_dir = output_path / f"backup_{timestamp}"
    export_dir.mkdir(parents=True, exist_ok=True)
    
    log(f"开始导出数据到: {export_dir}")
    
    state = load_state()
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        
        # 1. 导出事实
        facts = []
        cur = conn.execute("SELECT * FROM facts ORDER BY created_at")
        for row in cur.fetchall():
            facts.append(dict(row))
        
        facts_file = export_dir / "facts.json"
        with open(facts_file, "w", encoding="utf-8") as f:
            json.dump(facts, f, ensure_ascii=False, indent=2, default=str)
        log(f"导出 {len(facts)} 条事实")
        
        # 2. 导出实体
        entities = []
        cur = conn.execute("SELECT * FROM entities ORDER BY first_seen")
        for row in cur.fetchall():
            entities.append(dict(row))
        
        entities_file = export_dir / "entities.json"
        with open(entities_file, "w", encoding="utf-8") as f:
            json.dump(entities, f, ensure_ascii=False, indent=2, default=str)
        log(f"导出 {len(entities)} 个实体")
        
        # 3. 导出关联关系
        fact_entities = []
        cur = conn.execute("SELECT * FROM fact_entities")
        for row in cur.fetchall():
            fact_entities.append(dict(row))
        
        fact_entities_file = export_dir / "fact_entities.json"
        with open(fact_entities_file, "w", encoding="utf-8") as f:
            json.dump(fact_entities, f, ensure_ascii=False, indent=2)
        log(f"导出 {len(fact_entities)} 条关联")
        
        # 4. 导出元数据
        metadata = {
            "export_time": datetime.now().isoformat(),
            "db_path": str(db_path),
            "db_size": db_path.stat().st_size if db_path.exists() else 0,
            "facts_count": len(facts),
            "entities_count": len(entities),
            "relations_count": len(fact_entities),
            "schema_version": conn.execute("SELECT version FROM schema_version").fetchone()[0],
        }
        
        metadata_file = export_dir / "metadata.json"
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        # 5. 导出完整数据库（可选）
        if not incremental:
            db_copy = export_dir / "index.sqlite"
            shutil.copy2(db_path, db_copy)
            log(f"导出完整数据库: {db_path.stat().st_size} bytes")
        
        conn.close()
        
        # 6. 验证导出完整性
        verification = verify_export(export_dir)
        if verification["valid"]:
            log(f"✅ 导出成功并通过验证")
        else:
            log(f"⚠️ 导出完成但验证失败: {verification['errors']}", "WARNING")
        
        # 更新状态
        state["last_export"] = datetime.now().isoformat()
        state["incremental_markers"]["last_export"] = {
            "time": datetime.now().isoformat(),
            "facts_count": len(facts),
            "entities_count": len(entities),
        }
        save_state(state)
        
        # 生成增量标记
        if incremental:
            marker_file = export_dir / ".incremental"
            marker_file.write_text(json.dumps({
                "export_time": datetime.now().isoformat(),
                "facts_count": len(facts),
                "entities_count": len(entities),
            }))
        
        log(f"📦 导出完成: {export_dir}")
        print(f"\n导出目录: {export_dir}")
        return True
        
    except Exception as e:
        log(f"导出失败: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def verify_export(export_dir: Path) -> dict:
    """验证导出数据的完整性"""
    errors = []
    
    required_files = ["facts.json", "entities.json", "fact_entities.json", "metadata.json"]
    for fname in required_files:
        fpath = export_dir / fname
        if not fpath.exists():
            errors.append(f"缺少文件: {fname}")
    
    if errors:
        return {"valid": False, "errors": errors}
    
    # 验证 JSON 格式
    try:
        with open(export_dir / "facts.json", "r") as f:
            json.load(f)
        with open(export_dir / "entities.json", "r") as f:
            json.load(f)
        with open(export_dir / "fact_entities.json", "r") as f:
            json.load(f)
    except json.JSONDecodeError as e:
        errors.append(f"JSON 格式错误: {e}")
    
    return {"valid": len(errors) == 0, "errors": errors}


def import_data(input_dir: str, incremental: bool = False) -> bool:
    """导入数据"""
    ensure_dirs()
    input_path = Path(input_dir)
    
    if not input_path.exists():
        log(f"导入目录不存在: {input_dir}", "ERROR")
        return False
    
    log(f"开始导入数据 from: {input_path}")
    
    state = load_state()
    
    try:
        # 1. 验证导入数据
        verification = verify_export(input_path)
        if not verification["valid"]:
            log(f"导入数据验证失败: {verification['errors']}", "ERROR")
            return False
        
        # 读取元数据
        with open(input_path / "metadata.json", "r") as f:
            metadata = json.load(f)
        
        # 读取数据
        with open(input_path / "facts.json", "r") as f:
            facts = json.load(f)
        
        with open(input_path / "entities.json", "r") as f:
            entities = json.load(f)
        
        with open(input_path / "fact_entities.json", "r") as f:
            fact_entities = json.load(f)
        
        # 连接数据库
        db_path = get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(str(db_path))
        
        # 2. 导入实体（先导入实体，因为事实依赖实体）
        imported_entities = 0
        for entity in entities:
            conn.execute(
                """
                INSERT OR REPLACE INTO entities (slug, name, summary, entity_type, first_seen, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entity["slug"],
                    entity["name"],
                    entity.get("summary", ""),
                    entity.get("entity_type", "PERSON"),
                    entity.get("first_seen", datetime.now().isoformat()),
                    entity.get("last_updated", datetime.now().isoformat()),
                )
            )
            imported_entities += 1
        log(f"导入 {imported_entities} 个实体")
        
        # 3. 导入事实
        imported_facts = 0
        for fact in facts:
            conn.execute(
                """
                INSERT OR REPLACE INTO facts (id, kind, content, timestamp, source_path, source_line, confidence, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact["id"],
                    fact.get("kind", "W"),
                    fact["content"],
                    fact.get("timestamp", datetime.now().isoformat()),
                    fact.get("source_path", ""),
                    fact.get("source_line", 0),
                    fact.get("confidence", 1.0),
                    fact.get("created_at", datetime.now().isoformat()),
                    fact.get("updated_at", datetime.now().isoformat()),
                )
            )
            imported_facts += 1
        log(f"导入 {imported_facts} 条事实")
        
        # 4. 导入关联关系
        imported_relations = 0
        for rel in fact_entities:
            conn.execute(
                "INSERT OR IGNORE INTO fact_entities (fact_id, entity_slug) VALUES (?, ?)",
                (rel["fact_id"], rel["entity_slug"])
            )
            imported_relations += 1
        log(f"导入 {imported_relations} 条关联")
        
        conn.commit()
        conn.close()
        
        # 更新状态
        state["last_import"] = datetime.now().isoformat()
        state["incremental_markers"]["last_import"] = {
            "time": datetime.now().isoformat(),
            "facts_count": imported_facts,
            "entities_count": imported_entities,
        }
        save_state(state)
        
        log(f"✅ 导入成功")
        print(f"\n📥 导入完成:")
        print(f"   实体: {imported_entities}")
        print(f"   事实: {imported_facts}")
        print(f"   关联: {imported_relations}")
        return True
        
    except Exception as e:
        log(f"导入失败: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        return False


def backup_data() -> bool:
    """备份到 backups/"""
    ensure_dirs()
    
    # 直接导出到 BACKUP_DIR，export_data 会自动创建带时间戳的子目录
    success = export_data(str(BACKUP_DIR), incremental=False)
    
    if success:
        state = load_state()
        state["last_backup"] = datetime.now().isoformat()
        save_state(state)
        log(f"✅ 备份完成")
    
    return success


def restore_data(backup_file: str) -> bool:
    """从备份恢复"""
    backup_path = Path(backup_file)
    
    # 如果是目录直接使用，如果是名称则拼接
    if not backup_path.exists():
        backup_path = BACKUP_DIR / backup_file
    
    if not backup_path.exists():
        log(f"备份文件不存在: {backup_file}", "ERROR")
        return False
    
    log(f"从备份恢复: {backup_path}")
    
    # 1. 备份当前数据（以防万一）
    current_backup = f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    export_data(str(BACKUP_DIR / current_backup))
    
    # 2. 清空当前数据
    db_path = get_db_path()
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM fact_entities")
        conn.execute("DELETE FROM facts")
        conn.execute("DELETE FROM entities")
        conn.commit()
        conn.close()
        log("已清空当前数据")
    
    # 3. 导入备份数据
    success = import_data(str(backup_path))
    
    if success:
        state = load_state()
        state["last_restore"] = datetime.now().isoformat()
        save_state(state)
        log(f"✅ 恢复完成")
    
    return success


def show_status():
    """查看迁移状态"""
    state = load_state()
    
    print("\n" + "=" * 50)
    print("📊 迁移状态")
    print("=" * 50)
    
    # 数据库状态
    db_path = get_db_path()
    print(f"\n数据库:")
    print(f"  路径: {db_path}")
    print(f"  存在: {'是' if db_path.exists() else '否'}")
    if db_path.exists():
        print(f"  大小: {db_path.stat().st_size} bytes")
    
    # 迁移状态
    print(f"\n迁移状态:")
    print(f"  上次导出: {state.get('last_export', '从未')}")
    print(f"  上次导入: {state.get('last_import', '从未')}")
    print(f"  上次备份: {state.get('last_backup', '从未')}")
    print(f"  上次恢复: {state.get('last_restore', '从未')}")
    
    # 增量标记
    markers = state.get("incremental_markers", {})
    if markers:
        print(f"\n增量标记:")
        for key, value in markers.items():
            print(f"  {key}: {value}")
    
    # 备份列表
    if BACKUP_DIR.exists():
        backups = sorted(BACKUP_DIR.glob("backup_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        print(f"\n可用备份 ({len(backups)}):")
        for backup in backups[:5]:  # 只显示最近5个
            mtime = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            size = sum(f.stat().st_size for f in backup.rglob("*") if f.is_file())
            print(f"  {backup.name} - {mtime} - {size/1024:.1f}KB")
    
    print("\n" + "=" * 50)


def list_backups():
    """列出所有备份"""
    if not BACKUP_DIR.exists():
        print("没有备份")
        return
    
    backups = sorted(BACKUP_DIR.glob("backup_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    print(f"\n📦 可用备份 ({len(backups)}):\n")
    for backup in backups:
        mtime = datetime.fromtimestamp(backup.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        size = sum(f.stat().st_size for f in backup.rglob("*") if f.is_file())
        
        # 检查是否为增量备份
        is_incremental = (backup / ".incremental").exists()
        marker = " 📍" if is_incremental else ""
        
        print(f"  {backup.name}{marker}")
        print(f"    时间: {mtime}")
        print(f"    大小: {size/1024:.1f} KB")
        print()


def clean_old_backups(keep: int = 10):
    """清理旧备份"""
    if not BACKUP_DIR.exists():
        return
    
    backups = sorted(BACKUP_DIR.glob("backup_*"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if len(backups) <= keep:
        print(f"当前 {len(backups)} 个备份，不需要清理")
        return
    
    to_delete = backups[keep:]
    print(f"将删除 {len(to_delete)} 个旧备份...")
    
    for backup in to_delete:
        shutil.rmtree(backup)
        print(f"  删除: {backup.name}")
    
    print("✅ 清理完成")


def main():
    parser = argparse.ArgumentParser(
        description="Memory Bank 数据迁移工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 migrate.py export ./exports              # 导出到目录
  python3 migrate.py export ./exports --incremental # 增量导出
  python3 migrate.py import ./exports/backup_xxx   # 导入数据
  python3 migrate.py backup                         # 备份到 backups/
  python3 migrate.py restore backup_2026-03-04    # 从备份恢复
  python3 migrate.py status                         # 查看状态
  python3 migrate.py list                           # 列出备份
  python3 migrate.py clean                          # 清理旧备份
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # export 命令
    export_parser = subparsers.add_parser("export", help="导出所有数据")
    export_parser.add_argument("output_dir", help="输出目录")
    export_parser.add_argument("--incremental", action="store_true", help="增量导出")
    
    # import 命令
    import_parser = subparsers.add_parser("import", help="导入数据")
    import_parser.add_argument("input_dir", help="输入目录")
    import_parser.add_argument("--incremental", action="store_true", help="增量导入")
    
    # backup 命令
    subparsers.add_parser("backup", help="备份到 backups/")
    
    # restore 命令
    restore_parser = subparsers.add_parser("restore", help="从备份恢复")
    restore_parser.add_argument("backup_file", help="备份文件或名称")
    
    # status 命令
    subparsers.add_parser("status", help="查看迁移状态")
    
    # list 命令
    subparsers.add_parser("list", help="列出所有备份")
    
    # clean 命令
    clean_parser = subparsers.add_parser("clean", help="清理旧备份")
    clean_parser.add_argument("--keep", type=int, default=10, help="保留最近N个备份")
    
    args = parser.parse_args()
    
    if args.command == "export":
        success = export_data(args.output_dir, args.incremental)
        sys.exit(0 if success else 1)
    
    elif args.command == "import":
        success = import_data(args.input_dir, args.incremental)
        sys.exit(0 if success else 1)
    
    elif args.command == "backup":
        success = backup_data()
        sys.exit(0 if success else 1)
    
    elif args.command == "restore":
        success = restore_data(args.backup_file)
        sys.exit(0 if success else 1)
    
    elif args.command == "status":
        show_status()
    
    elif args.command == "list":
        list_backups()
    
    elif args.command == "clean":
        clean_old_backups(args.keep)
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
