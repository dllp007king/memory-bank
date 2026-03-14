"""
NER 批处理 CLI 工具

用法：
    python -m memory_bank.ner_batch --all
    python -m memory_bank.ner_batch --pending-only
    python -m memory_bank.ner_batch --from 2026-03-01 --to 2026-03-05
    python -m memory_bank.ner_batch --status
"""

import argparse
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_bank.database import init_database
from memory_bank.ner_queue import (
    get_queue_stats,
    enqueue_batch,
    get_pending_items
)


DB_PATH = "/home/myclaw/.openclaw/workspace/.memory/index.sqlite"


def show_status(db):
    """显示 NER 队列状态"""
    stats = get_queue_stats(db)
    
    print("\n" + "=" * 50)
    print("NER 队列状态")
    print("=" * 50)
    print(f"待处理 (pending):   {stats['pending']}")
    print(f"处理中 (processing): {stats['processing']}")
    print(f"已完成 (done):      {stats['done']}")
    print(f"失败 (failed):      {stats['failed']}")
    print(f"总计 (total):       {stats['total']}")
    print("=" * 50 + "\n")


def batch_all(db):
    """对所有记忆重新提取实体"""
    print("\n正在获取所有记忆...")
    
    cur = db.execute(
        """
        SELECT id, content FROM facts
        ORDER BY timestamp DESC
        """
    )
    
    items = []
    for row in cur.fetchall():
        items.append({
            'fact_id': row['id'],
            'content': row['content']
        })
    
    print(f"找到 {len(items)} 条记忆")
    
    if items:
        queued = enqueue_batch(db, items)
        print(f"✓ 已将 {queued} 条记忆加入 NER 队列")
    else:
        print("没有记忆需要处理")


def batch_pending_only(db):
    """只处理未提取实体的记忆"""
    print("\n正在查找未提取实体的记忆...")
    
    cur = db.execute(
        """
        SELECT f.id, f.content 
        FROM facts f
        LEFT JOIN fact_entities fe ON f.id = fe.fact_id
        WHERE fe.fact_id IS NULL
        ORDER BY f.timestamp DESC
        """
    )
    
    items = []
    for row in cur.fetchall():
        items.append({
            'fact_id': row['id'],
            'content': row['content']
        })
    
    print(f"找到 {len(items)} 条未提取实体的记忆")
    
    if items:
        queued = enqueue_batch(db, items)
        print(f"✓ 已将 {queued} 条记忆加入 NER 队列")
    else:
        print("所有记忆都已提取实体")


def batch_date_range(db, date_from: str, date_to: str):
    """处理指定日期范围的记忆"""
    print(f"\n正在查找 {date_from} 到 {date_to} 的记忆...")
    
    cur = db.execute(
        """
        SELECT id, content FROM facts
        WHERE date(timestamp) >= ? AND date(timestamp) <= ?
        ORDER BY timestamp DESC
        """,
        (date_from, date_to)
    )
    
    items = []
    for row in cur.fetchall():
        items.append({
            'fact_id': row['id'],
            'content': row['content']
        })
    
    print(f"找到 {len(items)} 条记忆")
    
    if items:
        queued = enqueue_batch(db, items)
        print(f"✓ 已将 {queued} 条记忆加入 NER 队列")
    else:
        print("该日期范围内没有记忆")


def main():
    parser = argparse.ArgumentParser(
        description='NER 批处理工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python -m memory_bank.ner_batch --status
  python -m memory_bank.ner_batch --all
  python -m memory_bank.ner_batch --pending-only
  python -m memory_bank.ner_batch --from 2026-03-01 --to 2026-03-05
        """
    )
    
    parser.add_argument('--status', action='store_true',
                        help='显示 NER 队列状态')
    parser.add_argument('--all', action='store_true',
                        help='对所有记忆重新提取实体')
    parser.add_argument('--pending-only', action='store_true',
                        help='只处理未提取实体的记忆')
    parser.add_argument('--from', dest='date_from', type=str,
                        help='开始日期 (YYYY-MM-DD)')
    parser.add_argument('--to', dest='date_to', type=str,
                        help='结束日期 (YYYY-MM-DD)')
    
    args = parser.parse_args()
    
    # 初始化数据库
    db = init_database(DB_PATH)
    
    # 显示状态
    if args.status:
        show_status(db)
        return
    
    # 批处理
    if args.all:
        batch_all(db)
    elif args.pending_only:
        batch_pending_only(db)
    elif args.date_from and args.date_to:
        batch_date_range(db, args.date_from, args.date_to)
    else:
        # 默认显示状态
        show_status(db)
        print("使用 --help 查看可用选项")


if __name__ == '__main__':
    main()
