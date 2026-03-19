#!/usr/bin/env python3
"""
迁移脚本：给 memories 表添加 content_tokens 字段并填充数据

- 为每条现有记录生成 jieba 分词后的 content_tokens
- 用 PyArrow 做批量列添加（不逐行删除重插）
- 重建 FTS 索引到 content_tokens 字段
"""

import sys
import lancedb
import pyarrow as pa
import pyarrow.compute as pc

sys.path.insert(0, "/home/myclaw/.openclaw/workspace/memory-bank")
from memory_bank.jieba_dict import init_jieba, tokenize_to_string

LANCE_PATH = "/home/myclaw/.openclaw/workspace/.memory/lancedb"
TABLE = "memories"


def main():
    init_jieba()

    db = lancedb.connect(LANCE_PATH)
    t = db.open_table(TABLE)

    print(f"当前表行数: {t.count_rows()}")
    print(f"当前字段: {t.schema.names}")

    # 检查是否已有 content_tokens 字段
    has_field = "content_tokens" in t.schema.names

    if has_field:
        # 字段已存在：只更新 content_tokens 为 NULL 的记录
        print("content_tokens 字段已存在，补填缺失值...")
        all_rows = t.search().to_list()
        missing = [r for r in all_rows if not r.get("content_tokens")]
        print(f"  需要补填: {len(missing)} 条")

        for row in missing:
            rid = row["id"]
            tokens = tokenize_to_string(row["content"], mode="index")
            # 删除旧行，重插带 tokens 的新行
            updated = dict(row)
            updated["content_tokens"] = tokens
            t.delete(f"id = '{rid}'")
            t.add([updated])
            print(f"  补填: {rid[:8]} -> {tokens[:40]}...")
    else:
        # 字段不存在：用 add_columns 批量添加
        print("content_tokens 字段不存在，批量添加...")
        all_data = t.search().to_arrow()
        contents = all_data.column("content").to_pylist()
        tokens_list = [tokenize_to_string(c, mode="index") for c in contents]
        tokens_array = pa.array(tokens_list, type=pa.string())

        # LanceDB add_columns API: 传入 PA RecordBatch 或用 merge
        # 方式：读取全部 -> 添加列 -> 覆盖写回
        new_table = all_data.append_column(
            pa.field("content_tokens", pa.string()),
            tokens_array,
        )
        # 用 overwrite 模式写回（保留 schema 上的其他字段）
        db.drop_table(TABLE)
        new_t = db.create_table(TABLE, data=new_table)
        print(f"  重建表完成，共 {new_t.count_rows()} 条记录")
        t = new_t

    # 重建 FTS 索引（content_tokens 字段）
    print("重建 FTS 索引 (content_tokens)...")
    # 先删除旧的 content_idx（如果有）
    try:
        t.drop_index("content_idx")
        print("  删除旧索引 content_idx")
    except Exception:
        pass
    t.create_fts_index("content_tokens", replace=True)
    print("  FTS 索引重建完成")

    # 验证
    print("\n--- 验证 ---")
    print(f"行数: {t.count_rows()}")
    print(f"字段: {t.schema.names}")

    # 抽样检查
    sample = t.search().limit(2).to_list()
    for row in sample:
        print(f"\n  content: {row['content'][:50]}")
        print(f"  tokens:  {row.get('content_tokens', 'N/A')[:60]}")

    # FTS 搜索测试
    print("\n--- FTS 搜索测试 ---")
    for q in ["记忆银行", "OpenClaw", "liu", "搜索"]:
        q_tokens = tokenize_to_string(q, mode="search")
        try:
            results = t.search(q_tokens, query_type="fts", fts_columns="content_tokens").limit(3).to_list()
            print(f"  '{q}' (分词: {q_tokens!r}): {len(results)} 条")
            for r in results[:1]:
                print(f"    {r['content'][:60]}")
        except Exception as e:
            print(f"  '{q}' 错误: {e}")

    print("\n迁移完成！")


if __name__ == "__main__":
    main()
