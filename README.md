# 写在最前面

- 本项目是100%由AI开发的项目，它是基于lancedb数据库+本地llama.cpp 运行 Qwen3向量模型 4b Q8的一个关于只能体记忆可视化的项目。
- 你需要写一个skill来让你的agent把需要记录的记忆以标准的json格式送给数据库，这样才能记录和可视化。
- 里面会有一些bug。你也可以然你的agent来修复它。
- 玩的开心。

# Memory Bank（记忆银行）

> OpenClaw 长期记忆系统 - 带生命周期的智能记忆存储与检索

## 核心特性

### 🧠 记忆生命周期管理

记忆不是静态的，会随时间衰减、被取代、或提炼成知识：

```
新记忆 → ACTIVE（活跃）→ ARCHIVED（归档）→ SUPERSEDED（取代）→ FORGOTTEN（遗忘）
           ↓              ↓                  ↓
        正常检索       降低权重           保留历史          标记删除
```

**核心公式**：
| 公式 | 用途 |
|------|------|
| `effective = confidence × e^(-λ × days)` | 有效置信度（时间衰减） |
| `cleanup = (1 - importance) × (1 - effective) × days` | 清理优先级 |
| `distill = importance × access_count × days` | 提炼优先级 |

**衰减率模式**：
| 稳定性 | 衰减率 | 关键词示例 |
|--------|--------|-----------|
| 恒定 | 0.0001 | 永远、始终、必然 |
| 长期 | 0.001 | 我是、我的、价值观 |
| 中期 | 0.01 | 正在、当前、项目 |
| 短期 | 0.05 | 打算、计划、下周 |
| 即时 | 0.2 | 今天、此刻、马上 |

### 🔄 矛盾检测与解决

当新记忆与旧记忆冲突时，自动选择处理策略：

```
new_effective > old_effective + 0.15  →  UPDATE（更新）
old_effective > new_effective + 0.15  →  KEEP（保留）
其他                                   →  CONFIRM（需确认）
```

### 🔍 混合搜索

- **BM25 全文检索**：精确关键词匹配
- **向量语义搜索**：Qwen3-Embedding-4B (2560维)
- **融合排序**：Reciprocal Rank Fusion

### 🏷️ 智能实体提取

- NER 自动识别命名实体
- 实体类型推断（人物/项目/工具/概念等）
- 关系自动提取

---

## 快速开始

### 安装

```bash
pip install -r requirements.txt
pip install lancedb jieba
```

### 启动

```bash
# 前台运行
./start.sh

# systemd 服务
./install-service.sh
sudo systemctl enable memory-bank
sudo systemctl start memory-bank
```

### 验证

```bash
curl http://localhost:8088/api/status
```

---

## API 接口

基础 URL: `http://localhost:8088/api`

### 搜索记忆

```bash
# 混合搜索
curl "http://localhost:8088/api/search?q=RAG&mode=hybrid&limit=10"

# 向量搜索
curl "http://localhost:8088/api/search?q=向量数据库&mode=vector&limit=10"

# 实体搜索
curl "http://localhost:8088/api/search?mode=entity&e=liu&limit=10"

# 时间过滤
curl "http://localhost:8088/api/search?q=项目&time=week&limit=20"
```

### 添加记忆

```bash
curl -X POST "http://localhost:8088/api/facts" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "liu 完成了记忆银行生命周期功能",
    "kind": "E",
    "confidence": 0.9,
    "importance": 0.7,
    "entities": [
      {"name": "liu", "type": "PERSON"},
      {"name": "记忆银行", "type": "PROJECT"}
    ],
    "relations": ["liu|完成|记忆银行"]
  }'
```

### 查看状态

```bash
curl http://localhost:8088/api/status
```

响应示例：
```json
{
  "success": true,
  "data": {
    "facts_count": 100,
    "entities_count": 25,
    "vectors_count": 85,
    "embedding_status": "ok"
  }
}
```

---

## 数据模型

### Fact（事实）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 唯一标识 |
| kind | str | 类型：W/E/O/S/B/L |
| content | str | 内容 |
| confidence | float | 置信度 (0-1) |
| importance | float | 重要程度 (0-1) |
| decay_rate | float | 衰减率 |
| access_count | int | 访问次数 |
| entities | List | 关联实体 |
| timestamp | datetime | 时间戳 |

**Kind 类型**：
| 代码 | 类型 | 说明 |
|------|------|------|
| W | World | 世界知识 |
| E | Experience | 经历事件 |
| O | Opinion | 观点看法 |
| S | Summary | 总结提炼 |
| B | Biography | 传记信息 |
| L | Log | 系统日志 |

### Entity（实体）

| 字段 | 类型 | 说明 |
|------|------|------|
| slug | str | 唯一标识 |
| name | str | 名称 |
| entity_type | str | 类型 |
| summary | str | 摘要 |

**Entity 类型**：
PERSON / PROJECT / TOOL / SYSTEM / CONCEPT / PLACE / EVENT / GAME / ORGANIZATION

### LifecycleState（生命周期状态）

| 状态 | 说明 |
|------|------|
| ACTIVE | 活跃记忆，正常检索 |
| ARCHIVED | 已归档，降低检索权重 |
| SUPERSEDED | 已被取代，仅保留历史 |
| FORGOTTEN | 已遗忘，标记待删除 |

---

## 记忆生命周期详解

### 1. 时间衰减

记忆的"有效置信度"随时间自然衰减：

```python
effective = confidence × e^(-decay_rate × days)
```

- **高置信度 + 低衰减率** = 长期有效
- **低置信度 + 高衰减率** = 快速失效

### 2. 清理决策

系统自动计算清理优先级：

```python
cleanup_priority = (1 - importance) × (1 - effective) × days
```

**清理条件**：
- `importance < 0.3` 且 `effective < 0.3` → 清理
- `importance > 0.8` 且 `effective > 0.5` → 永久保留

### 3. 知识提炼

高频访问的重要记忆可提炼成知识：

```python
distill_priority = importance × access_count × days
```

### 4. 矛盾处理

当新旧记忆冲突时：

```python
if new_effective > old_effective + 0.15:
    return UPDATE  # 用新记忆替换
elif old_effective > new_effective + 0.15:
    return KEEP    # 保留旧记忆
else:
    return CONFIRM # 需要用户确认
```

---

## 项目结构

```
memory-bank/
├── memory_bank/
│   ├── lifecycle.py        # 记忆生命周期管理
│   ├── contradiction.py    # 矛盾检测与解决
│   ├── supervisor.py       # 任务监督器
│   ├── config.py           # 配置管理
│   ├── models.py           # 数据模型
│   ├── database.py         # 数据库连接
│   ├── lance_crud.py       # CRUD 操作
│   ├── lance_search.py     # 搜索功能
│   ├── embedding.py        # 向量嵌入
│   ├── ner_extractor.py    # NER 实体提取
│   └── entity_types.py     # 实体类型推断
├── web/
│   ├── app.py              # Flask 后端
│   └── templates/          # Web UI 模板
├── scripts/
│   ├── backup_lancedb.py   # 备份脚本
│   └── export_knowledge.py # 导出脚本
├── requirements.txt
├── start.sh / stop.sh / restart.sh
├── memory-bank.service     # systemd 配置
└── DEPLOY.md               # 部署指南
```

---

## 配置

配置文件首次运行时自动创建于 `config/memory_lifecycle.json`：

```json
{
  "decay_rates": {
    "permanent": 0.0001,
    "long_term": 0.001,
    "medium_term": 0.01,
    "short_term": 0.05,
    "instant": 0.2
  },
  "thresholds": {
    "cleanup_effective": 0.3,
    "cleanup_importance": 0.3,
    "keep_effective": 0.5,
    "keep_importance": 0.8
  }
}
```

---

## Web UI

访问 `http://localhost:8088` 可视化管理：

- **仪表盘**：统计概览、嵌入服务状态
- **搜索**：多模式搜索、时间过滤
- **添加**：快速记录、自动提取实体
- **管理**：浏览事实/实体、批量操作
- **图谱**：实体关系可视化

---

## 监督器

自动化任务执行器，带重试和错误分析：

```python
from memory_bank.supervisor import Supervisor

supervisor = Supervisor(max_retries=3)
result = supervisor.execute_with_supervision(my_task, "向量化任务")

if result.success:
    print(f"✅ 成功: {result.data}")
else:
    print(f"❌ 失败: {result.error}")
```

失败报告自动生成于 `logs/failure_reports.json`。

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 向量数据库 | LanceDB |
| Web 框架 | Flask |
| 向量嵌入 | Qwen3-Embedding-4B (2560维) |
| NER | LLM 命名实体识别 |
| 前端 | Tailwind CSS + Chart.js |

---

## 许可

MIT
