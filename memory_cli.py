#!/usr/bin/env python3
"""
Memory Bank CLI - 记忆系统命令行工具

用法:
    python memory_cli.py init              # 初始化数据库
    python memory_cli.py add "内容"        # 添加事实
    python memory_cli.py search "查询"     # 搜索
    python memory_cli.py entity add slug   # 添加实体
    python memory_cli.py list              # 列出事实
    python memory_cli.py status            # 显示状态
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# 添加模块路径
sys.path.insert(0, str(Path(__file__).parent))

from memory_bank.database import init_database
from memory_bank.crud import (
    create_fact, get_fact, list_facts, update_fact, delete_fact,
    create_entity, get_entity, list_entities, set_db,
    index_fact_embedding, index_all_facts, get_fact_embedding,
)
from memory_bank.search import search_facts, search_by_entity, hybrid_search, vector_search
from memory_bank.embedding import check_server_health, get_config, EmbeddingConfig
from memory_bank.session_hook import get_session_hook, SessionHook


DB_PATH = Path.home() / ".openclaw" / "workspace" / ".memory" / "index.sqlite"


def cmd_init(args):
    """初始化数据库"""
    print(f"初始化数据库: {DB_PATH}")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = init_database(str(DB_PATH))
    set_db(db)
    print("✓ 数据库初始化完成")
    print(f"  Schema 版本: {db.get_schema_version()}")


def cmd_add(args):
    """添加事实"""
    db = _get_db()
    
    # 解析实体
    entities = args.entities.split(",") if args.entities else []
    
    fact = create_fact(
        content=args.content,
        kind=args.kind,
        entities=entities,
        confidence=args.confidence,
        source_path=args.source or "",
    )
    
    print(f"✓ 创建事实: {fact.id}")
    print(f"  类型: {fact.kind}")
    print(f"  内容: {fact.content[:50]}...")
    print(f"  实体: {fact.entities}")


def cmd_search(args):
    """搜索事实"""
    db = _get_db()
    
    if args.entity:
        results = search_by_entity(args.entity, limit=args.limit)
    elif args.hybrid:
        results = hybrid_search(args.query, limit=args.limit)
    else:
        results = search_facts(args.query, limit=args.limit)
    
    if not results:
        print("无搜索结果")
        return
    
    print(f"找到 {len(results)} 条结果:\n")
    for i, result in enumerate(results, 1):
        print(f"[{i}] {result.fact.id} (score: {result.score:.2f}, type: {result.match_type})")
        print(f"    {result.fact.content[:80]}...")
        print(f"    实体: {result.fact.entities}")
        print()


def cmd_list(args):
    """列出事实"""
    db = _get_db()
    
    facts = list_facts(
        kind=args.kind,
        entity=args.entity,
        limit=args.limit,
    )
    
    if not facts:
        print("无事实记录")
        return
    
    print(f"共 {len(facts)} 条事实:\n")
    for fact in facts:
        print(f"[{fact.id}] {fact.kind} | {fact.timestamp.strftime('%Y-%m-%d %H:%M')}")
        if args.full:
            # 完整显示
            print(f"    {fact.content}")
        else:
            # 截断显示
            content = fact.content[:80] + "..." if len(fact.content) > 80 else fact.content
            print(f"    {content}")
        if fact.entities:
            print(f"    实体: {fact.entities}")
        print()


def cmd_entity(args):
    """实体操作"""
    db = _get_db()
    
    if args.entity_cmd == "add":
        entity = create_entity(
            slug=args.slug,
            name=args.name or args.slug,
            summary=args.summary or "",
            entity_type=args.type or "PERSON",
        )
        print(f"✓ 创建实体: {entity.slug}")
        print(f"  名称: {entity.name}")
        print(f"  类型: {entity.entity_type}")
    
    elif args.entity_cmd == "list":
        entities = list_entities(entity_type=args.type, limit=args.limit)
        print(f"共 {len(entities)} 个实体:\n")
        for entity in entities:
            print(f"[{entity.slug}] {entity.name} ({entity.entity_type})")
            if entity.summary:
                print(f"    {entity.summary[:60]}...")
            print()
    
    elif args.entity_cmd == "get":
        entity = get_entity(args.slug)
        if entity:
            print(f"实体: {entity.slug}")
            print(f"  名称: {entity.name}")
            print(f"  类型: {entity.entity_type}")
            print(f"  摘要: {entity.summary}")
            print(f"  首次出现: {entity.first_seen}")
            print(f"  最后更新: {entity.last_updated}")
        else:
            print(f"实体不存在: {args.slug}")


def cmd_status(args):
    """显示状态"""
    if not DB_PATH.exists():
        print("数据库未初始化，请运行: python memory_cli.py init")
        return
    
    db = _get_db()
    
    # 统计
    facts_count = db.execute("SELECT COUNT(*) as cnt FROM facts").fetchone()["cnt"]
    entities_count = db.execute("SELECT COUNT(*) as cnt FROM entities").fetchone()["cnt"]
    links_count = db.execute("SELECT COUNT(*) as cnt FROM fact_entities").fetchone()["cnt"]
    
    # 向量统计
    try:
        vec_count = db.execute("SELECT COUNT(*) as cnt FROM vec_embeddings").fetchone()["cnt"]
    except sqlite3.OperationalError:
        vec_count = 0
    
    # 检查嵌入服务
    server_ok = check_server_health()
    
    print("Memory Bank 状态")
    print("=" * 40)
    print(f"数据库路径: {DB_PATH}")
    print(f"Schema 版本: {db.get_schema_version()}")
    print(f"事实数量: {facts_count}")
    print(f"实体数量: {entities_count}")
    print(f"关联数量: {links_count}")
    print(f"向量索引: {vec_count}/{facts_count}")
    print(f"嵌入服务: {'✅ 在线' if server_ok else '❌ 离线'}")
    print(f"数据库大小: {DB_PATH.stat().st_size / 1024:.1f} KB")


def cmd_delete(args):
    """删除事实"""
    db = _get_db()
    
    result = delete_fact(args.fact_id)
    if result:
        print(f"✓ 删除事实: {args.fact_id}")
    else:
        print(f"事实不存在: {args.fact_id}")


def cmd_hook(args):
    """会话钩子操作"""
    hook = get_session_hook()
    
    if args.hook_cmd == "start":
        # 添加默认回调
        hook.add_callback(SessionHook.on_idle_timeout)
        hook.start_monitor()
        status = hook.get_status()
        print(f"✅ 会话钩子已启动 (超时: {status['idle_timeout']}秒)")
        print(f"   监控中: {status['is_monitoring']}")
        print(f"   上次活动: {status['last_activity']}")
        
    elif args.hook_cmd == "stop":
        hook.stop_monitor()
        print("✅ 会话钩子已停止")
        
    elif args.hook_cmd == "status":
        status = hook.get_status()
        print("📊 Session Hook 状态:")
        print(f"   运行中: {status['is_running']}")
        print(f"   监控中: {status['is_monitoring']}")
        print(f"   上次活动: {status['last_activity']}")
        print(f"   空闲时间: {status['idle_seconds']}秒")
        print(f"   超时设置: {status['idle_timeout']}秒")
        print(f"   总触发次数: {status['total_triggers']}")
        
    elif args.hook_cmd == "trigger":
        hook.trigger()
        print("✅ 手动触发完成")


def cmd_index(args):
    """向量索引操作"""
    db = _get_db()
    
    if args.index_cmd == "all":
        print("正在为所有事实创建向量索引...")
        success, failed = index_all_facts()
        print(f"✅ 完成: 成功 {success}, 失败 {failed}")
        
    elif args.index_cmd == "fact":
        if index_fact_embedding(args.fact_id):
            print(f"✅ 已为事实 {args.fact_id} 创建向量索引")
        else:
            print(f"❌ 创建失败: {args.fact_id}")
    
    elif args.index_cmd == "status":
        # 统计向量索引情况
        facts_count = db.execute("SELECT COUNT(*) as cnt FROM facts").fetchone()["cnt"]
        vec_count = db.execute("SELECT COUNT(*) as cnt FROM vec_embeddings").fetchone()["cnt"]
        
        print(f"📊 向量索引状态:")
        print(f"   已索引: {vec_count}/{facts_count}")
        print(f"   覆盖率: {vec_count/facts_count*100:.1f}%" if facts_count > 0 else "   覆盖率: N/A")
        
        # 检查嵌入服务
        server_ok = check_server_health()
        print(f"   嵌入服务: {'✅ 在线' if server_ok else '❌ 离线 (将使用 CLI)'}")
        
        config = get_config()
        print(f"   向量维度: {config.dimension}")
        print(f"   模型路径: {config.model_path}")


def cmd_search(args):
    """搜索事实"""
    db = _get_db()
    
    if args.entity:
        results = search_by_entity(args.entity, limit=args.limit)
    elif args.vector:
        results = vector_search(args.query, limit=args.limit)
    elif args.hybrid:
        results = hybrid_search(args.query, limit=args.limit)
    else:
        results = search_facts(args.query, limit=args.limit)
    
    if not results:
        print("无搜索结果")
        return
    
    print(f"找到 {len(results)} 条结果:\n")
    for i, result in enumerate(results, 1):
        print(f"[{i}] {result.fact.id} (score: {result.score:.2f}, type: {result.match_type})")
        print(f"    {result.fact.content[:80]}...")
        print(f"    实体: {result.fact.entities}")
        print()


def _get_db():
    """获取数据库实例"""
    if not DB_PATH.exists():
        print("数据库未初始化，请运行: python memory_cli.py init")
        sys.exit(1)
    db = init_database(str(DB_PATH))
    set_db(db)
    return db


def main():
    parser = argparse.ArgumentParser(description="Memory Bank CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")

    # init
    parser_init = subparsers.add_parser("init", help="初始化数据库")
    parser_init.set_defaults(func=cmd_init)

    # add
    parser_add = subparsers.add_parser("add", help="添加事实")
    parser_add.add_argument("content", help="事实内容")
    parser_add.add_argument("-k", "--kind", default="W", help="类型: W/B/O/S")
    parser_add.add_argument("-e", "--entities", help="关联实体，逗号分隔")
    parser_add.add_argument("-c", "--confidence", type=float, default=1.0, help="置信度")
    parser_add.add_argument("-s", "--source", help="来源路径")
    parser_add.set_defaults(func=cmd_add)

    # search
    parser_search = subparsers.add_parser("search", help="搜索事实")
    parser_search.add_argument("query", nargs="?", help="搜索查询")
    parser_search.add_argument("-e", "--entity", help="按实体搜索")
    parser_search.add_argument("--hybrid", action="store_true", help="混合搜索")
    parser_search.add_argument("--vector", action="store_true", help="纯向量搜索")
    parser_search.add_argument("-l", "--limit", type=int, default=10, help="结果数量")
    parser_search.set_defaults(func=cmd_search)

    # list
    parser_list = subparsers.add_parser("list", help="列出事实")
    parser_list.add_argument("-k", "--kind", help="按类型过滤")
    parser_list.add_argument("-e", "--entity", help="按实体过滤")
    parser_list.add_argument("-l", "--limit", type=int, default=20, help="结果数量")
    parser_list.add_argument("-f", "--full", action="store_true", help="显示完整内容")
    parser_list.set_defaults(func=cmd_list)

    # entity
    parser_entity = subparsers.add_parser("entity", help="实体操作")
    entity_subparsers = parser_entity.add_subparsers(dest="entity_cmd")
    
    entity_add = entity_subparsers.add_parser("add", help="添加实体")
    entity_add.add_argument("slug", help="实体标识")
    entity_add.add_argument("-n", "--name", help="实体名称")
    entity_add.add_argument("-s", "--summary", help="实体摘要")
    entity_add.add_argument("-t", "--type", help="实体类型")
    entity_add.set_defaults(func=cmd_entity)
    
    entity_list = entity_subparsers.add_parser("list", help="列出实体")
    entity_list.add_argument("-t", "--type", help="按类型过滤")
    entity_list.add_argument("-l", "--limit", type=int, default=20, help="结果数量")
    entity_list.set_defaults(func=cmd_entity)
    
    entity_get = entity_subparsers.add_parser("get", help="获取实体")
    entity_get.add_argument("slug", help="实体标识")
    entity_get.set_defaults(func=cmd_entity)

    # status
    parser_status = subparsers.add_parser("status", help="显示状态")
    parser_status.set_defaults(func=cmd_status)

    # delete
    parser_delete = subparsers.add_parser("delete", help="删除事实")
    parser_delete.add_argument("fact_id", help="事实ID")
    parser_delete.set_defaults(func=cmd_delete)

    # hook
    parser_hook = subparsers.add_parser("hook", help="会话钩子管理")
    hook_subparsers = parser_hook.add_subparsers(dest="hook_cmd", required=True)
    
    hook_start = hook_subparsers.add_parser("start", help="开始监控")
    hook_start.set_defaults(func=cmd_hook)
    
    hook_stop = hook_subparsers.add_parser("stop", help="停止监控")
    hook_stop.set_defaults(func=cmd_hook)
    
    hook_status = hook_subparsers.add_parser("status", help="查看状态")
    hook_status.set_defaults(func=cmd_hook)
    
    hook_trigger = hook_subparsers.add_parser("trigger", help="手动触发")
    hook_trigger.set_defaults(func=cmd_hook)

    # index (向量索引)
    parser_index = subparsers.add_parser("index", help="向量索引管理")
    index_subparsers = parser_index.add_subparsers(dest="index_cmd", required=True)
    
    index_all = index_subparsers.add_parser("all", help="为所有事实创建向量索引")
    index_all.set_defaults(func=cmd_index)
    
    index_fact = index_subparsers.add_parser("fact", help="为单个事实创建向量索引")
    index_fact.add_argument("fact_id", help="事实ID")
    index_fact.set_defaults(func=cmd_index)
    
    index_status = index_subparsers.add_parser("status", help="查看向量索引状态")
    index_status.set_defaults(func=cmd_index)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
