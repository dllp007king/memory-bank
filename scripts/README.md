# Memory Bank Scripts

记忆银行实用脚本集合。

## 脚本列表

### export_knowledge.py - 知识导出

从记忆银行导出知识库，支持多种格式。

**用法**：
```bash
# 导出所有格式（JSON + Markdown + HTML）
python3 export_knowledge.py --output knowledge_export

# 只导出 JSON
python3 export_knowledge.py --output knowledge_export --format json

# 只导出 Markdown
python3 export_knowledge.py --output knowledge_export --format markdown
```

**输出**：
- `data/memories.json` - 所有记忆
- `data/entities.json` - 所有实体
- `data/relations.json` - 所有关系
- `docs/` - Markdown 文档
- `visualization/graph.html` - 知识图谱

---

### backup_lancedb.py - 数据库备份

自动备份 LanceDB 数据库，支持定时任务和恢复。

**用法**：
```bash
# 每日备份（默认保留 30 天）
python3 backup_lancedb.py

# 完整备份（保留更久）
python3 backup_lancedb.py --full --keep-days 90

# 列出所有备份
python3 backup_lancedb.py --list

# 从备份恢复
python3 backup_lancedb.py --restore backup_daily_20260307.zip
```

**Cron 配置**：
```bash
# 每天凌晨 3 点备份
0 3 * * * /path/to/backup_lancedb.py --keep-days 30 >> /path/to/backup.log 2>&1

# 每周日凌晨 4 点完整备份
0 4 * * 0 /path/to/backup_lancedb.py --full --keep-days 90 >> /path/to/backup_full.log 2>&1
```

---

## 依赖

- Python 3.8+
- lancedb
- flask（Web UI）

## 安装

```bash
cd /home/myclaw/.openclaw/workspace/memory-bank
pip install -r requirements.txt
```

---

**版本**：v1.0
**更新**：2026-03-07
