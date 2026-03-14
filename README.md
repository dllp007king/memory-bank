# Memory Bank

OpenClaw 长期记忆系统 - 基于 LanceDB 的向量记忆存储和检索。

## 特性

- **LanceDB 存储**：高性能向量数据库，支持嵌入向量存储
- **混合搜索**：BM25 + 向量检索
- **实体管理**：关联事实与实体（人物、项目、系统等）
- **Web UI 界面**：可视化管理和操作
- **实体类型自动推断**：基于规则的智能分类
- **NER 提取**：命名实体识别自动提取

## 安装

```bash
cd memory-bank
pip install -r requirements.txt
```

## 快速开始

### Python API

name: memory-bank
description: 记忆银行集成技能，提供结构化记忆的存储和检索能力。用于搜索记忆、添加记忆、查看知识图谱。
---

# Memory Bank Skill

记忆银行集成技能，提供结构化记忆的存储和检索能力。

## 功能

- **搜索记忆**：向量 + 全文混合搜索，支持时间衰减
- **添加记忆**：自动提取实体和关系
- **知识图谱**：实体关系可视化
- **知识提炼**：老记忆自动提炼成知识

## API 端点

基础 URL: `http://10.10.10.18:8088/api`

### 搜索记忆

```
GET /search?q={query}&mode={hybrid|vector|fts}&limit={n}
```

示例：
```bash
curl "http://10.10.10.18:8088/api/search?q=liu&mode=hybrid&limit=10"
```

### 添加记忆

```
POST /facts
Content-Type: application/json

{
  "content": "记忆内容",
  "entities": [{"name": "实体", "type": "PERSON(人物)"}],
  "relations": ["A|关系|B"],
  "confidence" :0.9,
  "importance": 0.5,
  "tags": ["标签"]
}
```

示例：
```bash
curl -X POST "http://10.10.10.18:8088/api/facts" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "liu 完成了记忆银行接入测试",
    "entities": [
      {"name": "liu", "type": "PERSON(人物)"},
      {"name": "记忆银行", "type": "PROJECT(项目)"}
    ],
    "relations": ["liu|完成|记忆银行"],
    "confidence" :0.9,
    "importance" :0.7,
    "tags": ["测试", "完成"]
  }'
```

### 查看知识图谱

```
GET /graph
```

浏览器访问：http://10.10.10.18:8088/graph

### 查看状态

```
GET /status
```

## 使用场景

### 1. 保存重要信息

当用户说「记住这个」「记下来」时：

```bash
curl -X POST "http://10.10.10.18:8088/api/facts" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "用户的内容",
    "confidence" :0.9,
    "importance": 0.8,
    "auto_extract": true
  }'
```

### 2. 检索相关记忆

回答问题时先搜索：

```bash
curl "http://10.10.10.18:8088/api/search?q=用户问题关键词&mode=hybrid&limit=5"
```

### 3. 查询实体关系

```
GET /entities/{slug}
```

## 实体类型

| 类型 | 说明 |
|------|------|
| PERSON(人物) | 真实的人 |
| PROJECT(项目) | 项目、系统、产品 |
| TOOL(工具) | 软件、工具、平台 |
| DOCUMENT(文档) | 文件、报告 |
| TASK(任务) | 任务、活动 |
| BUG(缺陷) | 错误、问题 |
| ROLE(角色) | 职位、头衔 |
| CONCEPT(概念) | 技术概念、理论 |

## 注意事项

### 1. 实体一致性
- 关系中的实体必须存在于 entities 列表中
- entities 列表中的实体必有关系存在，不能只有实体没有关系

### 置信度"confidence" 和重要程度 "importance"

- 置信度是体现消息来源准确性的关键因素，在对话中置信度比较高。但是自己推测和猜想的置信度较低。
- 重要程度是这个事实的重要程，计划，项目，知识都很重要。另外对应八卦，小道消息重要程度较低。


### 2. 关系连通性（重要！）
- **所有实体应该连通** - 形成一张完整的图，而不是多个孤立的小图
- **每个实体必须有关系** - 不能有孤立的实体
- **添加桥梁关系** - 当发现孤立的关系对时，需要添加桥梁关系连接到主链

❌ 错误示例（孤立的关系对）：
```json
{
  "entities": ["liu", "Web UI", "本地 LLM", "JSON格式"],
  "relations": [
    "liu|提出|Web UI",
    "本地 LLM|提取|JSON格式"  // ← 孤立！没有连接到主链
  ]
}
```

✅ 正确示例（添加桥梁关系）：
```json
{
  "entities": ["liu", "Web UI", "本地 LLM", "JSON格式"],
  "relations": [
    "liu|提出|Web UI",
    "Web UI|使用|本地 LLM",   // ← 桥梁关系
    "本地 LLM|提取|JSON格式"
  ]
}
```

### 3. 关系格式
- 使用 `A|关系|B` 格式
- A 和 B 必须都在 entities 列表中

### 4. 如何识别
- **名词** → 识别为实体（人、物、项目、概念等）
- **动词** → 识别为关系（动作、状态变化等）

### 5. 其他
- **重要性范围**：0.0 - 1.0，默认 0.5
- **服务地址**：确保 10.10.10.18:8088 可访问

```

### Web UI

#### 启动方式

```bash
cd memory-bank/web
python app.py
```

启动后访问：`http://localhost:8088`

#### 功能介绍

Web UI 提供以下功能：

1. **仪表盘** - 展示数据库概览
   - 事实总数、实体总数、向量覆盖率
   - 嵌入服务状态监控
   - 事实类型分布饼图

2. **搜索** - 多模式搜索
   - 混合搜索（BM25 + 向量检索）
   - 纯向量搜索
   - 实体搜索（按关联实体检索）
   - 时间范围过滤（今天/本周/本月/今年）

3. **添加事实** - 快速记录信息
   - 简化版：一个输入框，自动提取实体并推断类型
   - 完整版：手动指定实体类型、置信度
   - 自动创建向量索引（如果嵌入服务在线）

4. **数据列表** - 浏览和管理
   - 事实列表：按类型筛选、分页浏览、批量删除
   - 实体列表：查看实体详情、关联事实数、批量删除
   - 实体类型自动推断（PERSON/TOOL/SYSTEM/PROJECT 等）

5. **实体类型预览** - 实时推断
   - 输入实体名称时，自动显示推断的类型

#### 界面预览

- **事实类型**：W=世界知识, E=经历, O=观点, S=总结, B=传记, L=日志
- **实体类型**：PERSON=人物, TOOL=工具, SYSTEM=系统, PROJECT=项目, CONCEPT=概念, PLACE=地点, EVENT=事件, GAME=游戏, ORGANIZATION=组织

## API 接口文档

Web UI 提供以下 RESTful API 端点：

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/` | 主页（Web UI） |
| GET | `/api/status` | 获取数据库状态（统计信息、嵌入服务状态） |
| GET | `/api/facts` | 列出事实（支持按 kind 筛选、分页） |
| POST | `/api/facts` | 添加新事实（自动提取实体、创建向量索引） |
| DELETE | `/api/facts/<fact_id>` | 删除指定事实（同时删除向量索引） |
| GET | `/api/entities` | 列出所有实体（包含关联事实数） |
| DELETE | `/api/entities/<slug>` | 删除实体（同时删除关联的所有事实和向量） |
| POST | `/api/infer-entity-type` | 实时推断实体类型（用于预览） |
| GET | `/api/search` | 搜索（支持混合/向量/实体模式、时间过滤） |

### API 请求示例

#### 添加事实

```bash
curl -X POST http://localhost:8088/api/facts \
  -H "Content-Type: application/json" \
  -d '{
    "content": "安装了 VS Code 插件",
    "kind": "E",
    "confidence": 0.9
  }'
```

#### 搜索

```bash
# 混合搜索
curl "http://localhost:8088/api/search?q=VS Code&mode=hybrid&limit=20"

# 向量搜索
curl "http://localhost:8088/api/search?q=VS Code&mode=vector&limit=20"

# 实体搜索
curl "http://localhost:8088/api/search?mode=entity&e=liu&limit=20"

# 时间过滤
curl "http://localhost:8088/api/search?q=项目&mode=hybrid&time=week&limit=50"
```

#### 获取状态

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
    "embedding_status": "ok",
    "embedding_model": "Qwen3-Embedding-4B-Q8_0",
    "embedding_dim": 2560,
    "kind_stats": {
      "W": 40,
      "E": 30,
      "O": 20,
      "S": 10
    }
  }
}
```

## 嵌入模型配置

### 当前配置

- **模型名称**: `Qwen3-Embedding-4B-Q8_0`
- **向量维度**: `2560`
- **服务检测**: 自动检测嵌入服务健康状态
- **索引创建**: 添加事实时自动创建向量索引（如果服务在线）

### 配置位置

嵌入模型配置位于 `web/app.py` 文件顶部：

```python
# 嵌入模型信息
EMBEDDING_MODEL = "Qwen3-Embedding-4B-Q8_0"
EMBEDDING_DIM = 2560
```

### 状态监控

Web UI 仪表盘实时显示：
- 嵌入服务状态（在线/离线）
- 模型名称和维度
- 向量覆盖率（已索引事实数 / 总事实数）

## Python API

### CRUD 操作

```python
from memory_bank import get_crud

crud = get_crud()

# 事实操作
crud.create_fact(content, kind, entities, confidence, source_path, source_line)
crud.get_fact(fact_id)
crud.list_facts(kind, entity, since, limit)
crud.update_fact(fact_id, **kwargs)
crud.delete_fact(fact_id)

# 实体操作
crud.create_entity(slug, name, summary, entity_type)
crud.get_entity(slug)
crud.list_entities(entity_type, limit)
crud.link_fact_entity(fact_id, entity_slug)
```

### 搜索

```python
from memory_bank import get_searcher

searcher = get_searcher()

# 混合搜索（BM25 + 向量）
results = searcher.hybrid_search(query, limit=10)

# 纯向量搜索
results = searcher.vector_search(query, limit=10)

# 按实体搜索
results = searcher.search_by_entity(entity_slug, limit=10)
```

## 数据模型

### Fact（事实）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 唯一标识 |
| kind | str | 类型：W/B/O/E/S/L |
| content | str | 内容 |
| timestamp | datetime | 时间戳 |
| entities | List[str] | 关联实体 |
| confidence | float | 置信度 (0-1) |
| source_path | str | 来源文件 |
| source_line | int | 来源行号 |

**Kind 类型说明**：
- `W` - 世界知识（World）：通用知识、事实
- `E` - 经历（Experience）：个人经历、事件
- `O` - 观点（Opinion）：个人观点、看法
- `S` - 总结（Summary）：总结性内容
- `B` - 传记（Biography）：人物传记信息
- `L` - 日志（Log）：系统日志、操作记录

### Entity（实体）

| 字段 | 类型 | 说明 |
|------|------|------|
| slug | str | 唯一标识 |
| name | str | 名称 |
| summary | str | 摘要 |
| entity_type | str | 类型：PERSON/TOOL/SYSTEM/PROJECT/CONCEPT/PLACE/EVENT/GAME/ORGANIZATION |
| first_seen | datetime | 首次出现 |
| last_updated | datetime | 最后更新 |

**Entity 类型说明**：
- `PERSON` - 人物
- `TOOL` - 工具、软件
- `SYSTEM` - 系统、平台
- `PROJECT` - 项目、产品
- `CONCEPT` - 概念、术语
- `PLACE` - 地点
- `EVENT` - 事件
- `GAME` - 游戏
- `ORGANIZATION` - 组织、公司

## 项目结构

```
memory-bank/
├── memory_bank/
│   ├── __init__.py          # 模块导出
│   ├── lance.py             # LanceDB 连接管理
│   ├── lance_crud.py        # CRUD 操作
│   ├── lance_search.py      # 搜索功能
│   ├── lance_schema.py      # 数据库模式
│   ├── models.py            # 数据模型
│   ├── embedding.py         # 向量嵌入
│   ├── ner_extractor.py     # NER 实体提取
│   ├── entity_type_cache.py # 实体类型推断缓存
│   ├── session_hook.py      # 会话钩子
│   └── supervisor.py        # 监督器
├── web/
│   ├── app.py               # Flask 后端
│   └── templates/
│       └── index.html       # Web UI 前端
├── tests/
├── requirements.txt
└── README.md
```

## 测试

```bash
cd memory-bank
pytest tests/ -v
```

## 技术栈

- **数据库**: LanceDB 向量数据库
- **Web 框架**: Flask
- **前端**: Tailwind CSS + Chart.js
- **向量检索**: Qwen3-Embedding-4B (2560维)
- **NER**: LLM 命名实体识别

## 许可

MIT

## 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                    Web UI (Flask)                       │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │
│  │ 仪表盘  │ │  搜索   │ │ 添加    │ │  管理   │       │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘       │
└───────┼──────────┼──────────┼──────────┼───────────────┘
        │          │          │          │
        └──────────┴──────────┴──────────┘
                        │
              ┌─────────▼─────────┐
              │   RESTful API     │
              │  (8 端点)         │
              └─────────┬─────────┘
                        │
    ┌───────────────────┼───────────────────┐
    │                   │                   │
┌───▼───┐         ┌─────▼─────┐       ┌─────▼─────┐
│ CRUD  │         │  Search   │       │ Embedding │
│ 操作  │         │  搜索     │       │  向量化   │
└───┬───┘         └─────┬─────┘       └─────┬─────┘
    │                   │                   │
    └───────────────────┼───────────────────┘
                        │
              ┌─────────▼─────────┐
              │     LanceDB       │
              │  向量数据库存储    │
              └───────────────────┘
```

## 搜索模式

| 模式 | 说明 |
|------|------|
| 混合搜索 | BM25 + 向量语义融合，Reciprocal Rank Fusion 排序 |
| 向量搜索 | Qwen3-Embedding-4B (2560维)，理解语义相似性 |
| 实体搜索 | 按关联实体精确检索 |
| 时间搜索 | 今天/本周/本月/今年 范围过滤 |

## 技术亮点

| 特性 | 实现方式 |
|------|----------|
| 向量存储 | LanceDB 原生向量支持，高效 ANN 检索 |
| 实体提取 | LLM NER 自动识别命名实体 |
| 类型推断 | 基于规则的智能实体类型分类 |
| 降级策略 | 嵌入服务离线时自动回退到文本搜索 |
| 统一 API | 标准化返回格式 {success, data/error} |

## 使用场景

```
你："我记得之前看过一篇关于 RAG 的文章..."

Memory Bank:
┌─────────────────────────────────────┐
│ 🔍 搜索: "RAG"                      │
│                                     │
│ 📄 2026-03-03: RAG 技术综述...      │
│ 📄 2026-03-02: 向量数据库对比...    │
│ 📄 2026-02-28: LangChain RAG 实践... │
│                                     │
│ 关联实体: RAG, LangChain, 向量数据库 │
└─────────────────────────────────────┘
```
