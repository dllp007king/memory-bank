#!/usr/bin/env python3
"""
修复 slug 大小写敏感导致的关系显示错误问题

问题：
1. 实体表中有两个 slug 只有大小写不同的实体：
   - X_a: add_tags_to_memories.py (SCRIPT)
   - X_A: api (CREDENTIAL)

2. 关系表中存储的是 X_a，但图谱 API 使用 slug.lower() 查询时，两个 slug 都变成 x_a
3. 第一个出现的实体被保留（X_A, api），第二个被跳过（X_a, add_tags_to_memories.py）
4. 导致关系显示错误

修复方案：
1. 删除错误的实体 X_A (api)
2. 删除关联的错误关系
3. 修复实体创建逻辑，添加 slug 冲突检查
"""

import sys
sys.path.insert(0, '/home/myclaw/.openclaw/workspace/memory-bank')

from memory_bank.lance_crud import MemoryCRUD
import lancedb
from pathlib import Path

def fix_slug_case_bug():
    print("=" * 60)
    print("修复 slug 大小写敏感问题")
    print("=" * 60)
    
    # 连接数据库
    db_path = str(Path.home() / '.openclaw' / 'workspace' / '.memory' / 'lancedb')
    db = lancedb.connect(db_path)
    
    entities_table = db.open_table('entities')
    relations_table = db.open_table('relations')
    
    # 1. 查找所有包含 X_a 的实体
    print("\n=== 步骤 1: 查找 slug 冲突的实体 ===")
    all_entities = entities_table.search().to_list()
    conflict_entities = [e for e in all_entities if 'x_a' in e['slug'].lower()]
    
    for e in conflict_entities:
        print(f"  slug: {e['slug']}, name: {e['name']}, type: {e['entity_type']}")
    
    # 2. 查找需要修复的关系
    print("\n=== 步骤 2: 查找关联的关系 ===")
    all_relations = relations_table.search().to_list()
    related_relations = [r for r in all_relations if 'x_a' in r['source_slug'].lower() or 'x_a' in r['target_slug'].lower()]
    
    for r in related_relations:
        print(f"  ID: {r['id']}, source: {r['source_slug']}, target: {r['target_slug']}, type: {r['relation_type']}")
    
    # 3. 删除错误的实体 X_A (api)
    print("\n=== 步骤 3: 删除错误的实体 X_A (api) ===")
    try:
        entities_table.delete("slug = 'X_A'")
        print("  ✅ 已删除实体 X_A (api)")
    except Exception as e:
        print(f"  ⚠️ 删除实体失败: {e}")
    
    # 4. 删除关联的错误关系
    print("\n=== 步骤 4: 删除关联的错误关系 ===")
    deleted_count = 0
    for r in related_relations:
        if r['source_slug'] == 'X_A' or r['target_slug'] == 'X_A':
            try:
                relations_table.delete(f"id = '{r['id']}'")
                deleted_count += 1
                print(f"  ✅ 已删除关系 {r['id']}")
            except Exception as e:
                print(f"  ⚠️ 删除关系 {r['id']} 失败: {e}")
    
    print(f"\n  总计删除 {deleted_count} 条关系")
    
    # 5. 验证修复结果
    print("\n=== 步骤 5: 验证修复结果 ===")
    
    # 重新查询实体
    all_entities = entities_table.search().to_list()
    conflict_entities = [e for e in all_entities if 'x_a' in e['slug'].lower()]
    
    print(f"  剩余的 slug 冲突实体数量: {len(conflict_entities)}")
    for e in conflict_entities:
        print(f"    slug: {e['slug']}, name: {e['name']}")
    
    # 重新查询关系
    all_relations = relations_table.search().to_list()
    related_relations = [r for r in all_relations if 'x_a' in r['source_slug'].lower() or 'x_a' in r['target_slug'].lower()]
    
    print(f"  剩余的关联关系数量: {len(related_relations)}")
    for r in related_relations:
        source_entity = [e for e in all_entities if e['slug'] == r['source_slug']]
        target_entity = [e for e in all_entities if e['slug'] == r['target_slug']]
        
        source_name = source_entity[0]['name'] if source_entity else 'Unknown'
        target_name = target_entity[0]['name'] if target_entity else 'Unknown'
        
        print(f"    {source_name} | {r['relation_type']} | {target_name}")
    
    print("\n" + "=" * 60)
    print("修复完成！请刷新图谱页面查看效果")
    print("=" * 60)

if __name__ == '__main__':
    fix_slug_case_bug()
