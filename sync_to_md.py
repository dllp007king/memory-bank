#!/usr/bin/env python3
"""
Memory Bank → Markdown 同步工具

将 SQLite 中的记忆同步导出为 Markdown 文件，
供 OpenClaw memory_search 工具索引。
"""

import os
import sys
import sqlite3
from datetime import datetime
from pathlib import Path

# 配置
WORKSPACE = Path(__file__).parent.parent
DB_PATH = WORKSPACE / ".memory" / "index.sqlite"
OUTPUT_DIR = WORKSPACE / "memory" / "bank"

# 事实类型映射
KIND_LABELS = {
    "W": "愿望",
    "B": "经验",
    "O": "意见",
    "S": "总结"
}

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_facts(conn):
    """获取所有事实及其关联实体"""
    cursor = conn.execute("""
        SELECT 
            f.id, f.content, f.kind, f.confidence, f.created_at, f.updated_at,
            GROUP_CONCAT(e.name, ', ') as entities
        FROM facts f
        LEFT JOIN fact_entities fe ON f.id = fe.fact_id
        LEFT JOIN entities e ON fe.entity_slug = e.slug
        GROUP BY f.id
        ORDER BY f.updated_at DESC
    """)
    return cursor.fetchall()

def get_all_entities(conn):
    """获取所有实体"""
    cursor = conn.execute("""
        SELECT slug, name, summary, entity_type, first_seen
        FROM entities
        ORDER BY name
    """)
    return cursor.fetchall()

def get_facts_by_entity(conn, entity_slug):
    """获取指定实体关联的所有事实"""
    cursor = conn.execute("""
        SELECT f.id, f.content, f.kind, f.confidence, f.updated_at
        FROM facts f
        JOIN fact_entities fe ON f.id = fe.fact_id
        WHERE fe.entity_slug = ?
        ORDER BY f.updated_at DESC
    """, (entity_slug,))
    return cursor.fetchall()

def format_timestamp(ts):
    """格式化时间戳"""
    if not ts:
        return ""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return ts

def sync_facts_md(conn):
    """同步所有事实到 facts.md"""
    facts = get_all_facts(conn)
    
    lines = [
        "# Memory Bank - 所有事实",
        "",
        f"> 最后同步: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"> 共 {len(facts)} 条记录",
        "",
        "---",
        ""
    ]
    
    for fact in facts:
        kind_label = KIND_LABELS.get(fact["kind"], fact["kind"])
        entities = fact["entities"] or ""
        confidence = f"{fact['confidence']:.0%}" if fact["confidence"] else ""
        updated = format_timestamp(fact["updated_at"])
        
        lines.append(f"## [{kind_label}] {fact['id'][:8]}")
        lines.append("")
        lines.append(fact["content"])
        lines.append("")
        if entities:
            lines.append(f"- **实体**: {entities}")
        if confidence:
            lines.append(f"- **置信度**: {confidence}")
        if updated:
            lines.append(f"- **更新**: {updated}")
        lines.append("")
        lines.append("---")
        lines.append("")
    
    output_path = OUTPUT_DIR / "facts.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ 已导出 {len(facts)} 条事实 → {output_path}")

def sync_entities_md(conn):
    """同步实体到独立文件"""
    entities = get_all_entities(conn)
    entities_dir = OUTPUT_DIR / "entities"
    entities_dir.mkdir(parents=True, exist_ok=True)
    
    for entity in entities:
        facts = get_facts_by_entity(conn, entity["slug"])
        
        lines = [
            f"# {entity['name']}",
            "",
            f"> 类型: {entity['entity_type'] or '未知'}",
            f"> 创建: {format_timestamp(entity['first_seen'])}",
            ""
        ]
        
        if entity["summary"]:
            lines.append("## 简介")
            lines.append("")
            lines.append(entity["summary"])
            lines.append("")
        
        if facts:
            lines.append("## 相关记忆")
            lines.append("")
            for fact in facts:
                kind_label = KIND_LABELS.get(fact["kind"], fact["kind"])
                confidence = f" ({fact['confidence']:.0%})" if fact["confidence"] else ""
                lines.append(f"- **[{kind_label}]**{confidence} {fact['content']}")
            lines.append("")
        
        output_path = entities_dir / f"{entity['slug'].lower()}.md"
        output_path.write_text("\n".join(lines), encoding="utf-8")
        print(f"✓ 已导出实体 {entity['name']} → {output_path}")
    
    print(f"✓ 共导出 {len(entities)} 个实体")

def sync_index_md(conn):
    """创建索引文件"""
    entities = get_all_entities(conn)
    facts = get_all_facts(conn)
    
    # 按类型统计
    kind_counts = {}
    for fact in facts:
        kind = fact["kind"]
        kind_counts[kind] = kind_counts.get(kind, 0) + 1
    
    lines = [
        "# Memory Bank 索引",
        "",
        f"> 最后同步: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 统计",
        "",
        f"- **实体数**: {len(entities)}",
        f"- **事实数**: {len(facts)}",
        ""
    ]
    
    if kind_counts:
        lines.append("### 按类型")
        lines.append("")
        for kind, count in sorted(kind_counts.items()):
            label = KIND_LABELS.get(kind, kind)
            lines.append(f"- {label}: {count}")
        lines.append("")
    
    if entities:
        lines.append("## 实体列表")
        lines.append("")
        for entity in entities:
            lines.append(f"- [{entity['name']}](./entities/{entity['slug'].lower()}.md) - {entity['entity_type'] or '未知'}")
        lines.append("")
    
    lines.extend([
        "## 快速链接",
        "",
        "- [所有事实](./facts.md)",
        ""
    ])
    
    output_path = OUTPUT_DIR / "index.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ 已创建索引 → {output_path}")

def main():
    """主函数"""
    print("=" * 50)
    print("Memory Bank → Markdown 同步")
    print("=" * 50)
    print()
    
    # 检查数据库
    if not DB_PATH.exists():
        print(f"✗ 数据库不存在: {DB_PATH}")
        print("  请先运行: python3 memory_cli.py init")
        sys.exit(1)
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "entities").mkdir(parents=True, exist_ok=True)
    
    # 连接数据库
    conn = get_db_connection()
    
    try:
        sync_facts_md(conn)
        sync_entities_md(conn)
        sync_index_md(conn)
        print()
        print("=" * 50)
        print("✓ 同步完成!")
        print(f"  输出目录: {OUTPUT_DIR}")
        print()
        print("现在可以使用 memory_search 搜索这些文件了。")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
