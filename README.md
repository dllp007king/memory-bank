# Memory Bank（记忆银行）

> OpenClaw 长期记忆系统 - 基于 LanceDB 的智能记忆存储与检索

---

## 项目概述

Memory Bank 是 OpenClaw 的核心记忆管理模块，提供：

- **🧠 智能记忆存储**：支持多种记忆类型（事实、经验、观点、总结等）
- **🔄 生命周期管理**：记忆随时间衰减、归档、取代、遗忘
- **🔍 混合搜索**：向量语义搜索 + LanceDB 内置全文检索
- **🕸️ 知识图谱**：实体关系可视化，支持 3D 渲染
- **📊 Web UI**：可视化管理和搜索界面

**当前版本**: v2.2 (2026-03-20)

---

## 技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| 向量数据库 | **LanceDB** | 高性能列式存储，支持向量搜索和全文检索 |
| Web 框架 | Flask | RESTful API + Web UI |
| 向量嵌入 | **Qwen3-Embedding-4B** | 2560 维向量，通过 llm.cpp HTTP Server |
| 分词 | jieba | 中文分词 |
| 前端 | Tailwind CSS + Chart.js + ForceGraph3D | 响应式界面 + 3D 知识图谱 |

---

## 核心功能

### 1. 记忆生命周期管理

记忆不是静态的，会随时间经历不同状态：

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

### 2. 矛盾检测与解决

当新记忆与旧记忆冲突时，自动选择处理策略：

```
new_effective > old_effective + 0.15  →  UPDATE（更新）
old_effective > new_effective + 0.15  →  KEEP（保留）
其他                                   →  CONFIRM（需确认）
```

### 3. 混合搜索

- **BM25 全文检索**：精确关键词匹配
- **向量语义搜索**：Qwen3-Embedding-4B (2560维)
- **融合排序**：Reciprocal Rank Fusion

### 4. 知识图谱

- 3D 力导向图可视化
- 实体关系管理
- 多重边处理（A→B 和 B→A 分开显示）
- 支持贝塞尔曲线渲染
- Slug 精确匹配（区分大小写）

### 5. 实体与关系

- 实体自动创建与关联
- 实体类型推断（人物/项目/工具/概念等）
- 关系自动提取
- Slug 生成（Base62 编码，区分大小写）

---

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
pip install lancedb jieba flask flask-cors
```

### 启动服务

```bash
# 前台运行
./start.sh

# 后台运行
./restart.sh

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

### 状态与配置

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/status` | GET | 获取数据库状态 |
| `/api/config/data` | GET | 获取配置数据 |
| `/api/config/update` | POST | 更新配置 |
| `/api/config/reset` | POST | 重置配置 |

### 记忆管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/facts` | GET | 列出记忆（支持分页、筛选） |
| `/api/facts` | POST | 添加新记忆 |
| `/api/facts/<id>` | GET | 获取单个记忆详情 |
| `/api/facts/<id>` | DELETE | 删除记忆 |

### 搜索

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/search` | GET | 混合搜索（向量+全文） |
| `/api/search?mode=vector` | GET | 向量搜索 |
| `/api/search?mode=keyword` | GET | 关键词搜索 |
| `/api/search?mode=entity` | GET | 实体搜索 |

**搜索参数**：

```
q: 搜索关键词
mode: hybrid | vector | keyword | entity
e: 实体名称（实体搜索）
time: 时间过滤（day/week/month/year）
limit: 返回数量
```

### 实体管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/entities` | GET | 列出所有实体 |
| `/api/entities/search` | GET | 搜索实体 |
| `/api/entities/<slug>` | DELETE | 删除实体 |
| `/api/infer-entity-type` | POST | 推断实体类型 |

### 关系管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/relations` | GET | 列出所有关系 |
| `/api/relations/create-or-replace` | POST | 创建或替换关系 |
| `/api/relations/<source_slug>/current` | GET | 获取当前关系 |
| `/api/relations/<source_slug>/<type>/history` | GET | 获取关系历史 |
| `/api/relations/batch-update` | POST | 批量更新关系 |
| `/api/relations/batch-delete` | POST | 批量删除关系 |

### 知识图谱

| 端点 | 方法 | 说明 |
|------|------|------|
| `/graph` | GET | 3D 知识图谱页面 |
| `/api/graph` | GET | 图谱数据 API |

### 生命周期管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/lifecycle/stats` | GET | 生命周期统计 |
| `/api/lifecycle/cleanup-candidates` | GET | 清理候选列表 |
| `/api/lifecycle/distill-candidates` | GET | 提炼候选列表 |
| `/api/lifecycle/batch-cleanup` | POST | 批量清理 |
| `/api/lifecycle/batch-distill` | POST | 批量提炼 |

---

## 数据模型

### Memory（记忆）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 唯一标识 |
| kind | str | 类型：W/E/O/S/B/L |
| content | str | 内容 |
| confidence | float | 置信度 (0-1) |
| importance | float | 重要程度 (0-1) |
| decay_rate | float | 衰减率 |
| lifecycle_state | str | 生命周期状态 |
| access_count | int | 访问次数 |
| entities | List | 关联实体 |
| relations | List | 关联关系 |
| tags | List | 标签列表 |
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

**LifecycleState 状态**：

| 状态 | 说明 |
|------|------|
| ACTIVE | 活跃记忆，正常检索 |
| ARCHIVED | 已归档，降低检索权重 |
| SUPERSEDED | 已被取代，仅保留历史 |
| FORGOTTEN | 已遗忘，标记待删除 |

### Entity（实体）

| 字段 | 类型 | 说明 |
|------|------|------|
| slug | str | 唯一标识（Base62 编码） |
| name | str | 名称 |
| entity_type | str | 类型 |
| summary | str | 摘要 |
| vector | List[float] | 向量嵌入 |
| first_seen | datetime | 首次发现 |
| last_updated | datetime | 最后更新 |

**Entity 类型**：

| 类型 | 说明 |
|------|------|
| PERSON | 人物 |
| PROJECT | 项目 |
| TOOL | 工具 |
| SYSTEM | 系统 |
| CONCEPT | 概念 |
| PLACE | 地点 |
| EVENT | 事件 |
| GAME | 游戏 |
| ORGANIZATION | 组织 |
| DOCUMENT | 文档 |
| CREDENTIAL | 凭证 |
| SCRIPT | 脚本 |
| DATABASE | 数据库 |

### Relation（关系）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 唯一标识 |
| source_slug | str | 源实体 slug |
| target_slug | str | 目标实体 slug |
| relation_type | str | 关系类型 |
| confidence | float | 置信度 |
| source_memory_id | str | 来源记忆 ID |

---

## 项目结构

```
memory-bank/
├── memory_bank/                 # 核心模块 (16 个文件, ~5745 行)
│   ├── __init__.py             # 模块入口 (v2.2.0)
│   ├── config.py               # 配置管理
│   ├── models.py               # 数据模型 (Fact, FactKind)
│   ├── lance.py                # LanceDB 连接
│   ├── lance_schema.py         # Schema 定义
│   ├── lance_crud.py           # CRUD 操作 (1585行，核心模块)
│   ├── lance_search.py         # 搜索功能
│   ├── embedding.py            # 向量嵌入
│   ├── entity_types.py         # 实体/关系类型定义
│   ├── lifecycle.py            # 记忆生命周期管理
│   ├── contradiction.py        # 矛盾检测与解决
│   ├── similarity.py           # 相似度计算
│   ├── slug_generator.py       # Slug 生成器
│   ├── jieba_dict.py           # Jieba 词典管理
│   ├── error_recorder.py       # 错误记录器
│   └── supervisor.py           # 任务监督器
├── web/                         # Web 模块
│   ├── app.py                  # Flask 后端 (40+ API 端点)
│   ├── static/                 # 静态资源
│   │   ├── index.html          # 主页面 (127KB)
│   │   ├── graph.html          # 3D 知识图谱 (67KB)
│   │   └── config.html         # 配置页面 (14KB)
│   └── README.md               # Web UI 说明
├── scripts/                     # 工具脚本
│   ├── backup_lancedb.py       # LanceDB 备份
│   ├── export_knowledge.py     # 知识导出
│   ├── add_tags_to_memories.py # 标签添加
│   ├── migrate_lifecycle.py    # 生命周期迁移
│   └── update_lance_schema.py  # Schema 更新
├── tests/                       # 测试用例
│   ├── test_slug_case.py       # Slug 大小写冲突测试
│   ├── test_lifecycle.py       # 生命周期测试
│   ├── test_similarity.py      # 相似度测试
│   └── test_contradiction.py   # 矛盾检测测试
├── config/                      # 配置文件
│   └── memory_lifecycle.json   # 生命周期配置
├── logs/                        # 日志目录
├── backups/                     # 备份目录
├── docs/                        # 文档
│   ├── ARCHITECTURE_ISSUES.md  # 架构问题报告
│   ├── CODE_REVIEW_ISSUES.md   # 代码审查报告
│   ├── LIFECYCLE.md            # 生命周期详解
│   └── plans/                  # 计划文档
├── requirements.txt             # Python 依赖
├── migrate.py                  # 数据迁移工具
├── start.sh / stop.sh / restart.sh # 服务脚本
├── restart_web.sh              # Web 服务重启
├── install-service.sh          # systemd 安装
├── memory-bank.service         # systemd 配置
├── DEPLOY.md                   # 部署指南
├── MAINTENANCE.md              # 维护指南
└── README.md                   # 本文档
```

---

## 数据存储

### 存储位置

```
~/.openclaw/workspace/.memory/
└── lancedb/               # LanceDB 向量数据库
    ├── memories.lance/    # 记忆向量
    ├── entities.lance/    # 实体向量
    └── relations.lance/   # 关系数据
```

### LanceDB 表结构

**memories 表**：
- id, kind, content, timestamp, embedding
- confidence, importance, decay_rate
- lifecycle_state, access_count, tags
- entities, relations

**entities 表**：
- slug, name, entity_type, summary, aliases
- vector, first_seen, last_updated

**relations 表**：
- id, source_slug, target_slug, relation_type
- confidence, source_memory_id

> **注意**: v2.2 已完全移除 SQLite，所有数据存储在 LanceDB 中。

---

## 配置

配置文件位于 `config/memory_lifecycle.json`：

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
  },
  "confidence": {
    "user_direct": 0.95,
    "user_uncertain": 0.70,
    "inference": 0.60,
    "contradiction_threshold": 0.15
  }
}
```

---

## Web UI

访问 `http://localhost:8088` 可视化管理：

- **📊 仪表盘**：统计概览、嵌入服务状态、类型分布饼图
- **🔍 搜索**：多模式搜索（向量/混合/实体）、时间过滤
- **📝 添加**：快速记录、自动提取实体和关系
- **📋 管理**：浏览事实/实体/关系、批量操作
- **🕸️ 图谱**：3D 实体关系可视化、力导向图
- **⚙️ 配置**：生命周期参数配置
- **🔄 生命周期**：清理/提炼候选管理

### 3D 知识图谱

访问 `http://localhost:8088/graph`：

- ForceGraph3D 力导向布局
- 多重边处理（A→B 和 B→A 分开显示）
- 贝塞尔曲线渲染
- 支持缩放、旋转、拖拽
- 实体类型颜色区分
- 关系类型颜色区分

---

## 最近更新

### v2.2 (2026-03-20)

**重大更新**：
- 🗑️ **彻底移除 SQLite**：完全使用 LanceDB，代码量减少 41.6%
- 🗑️ **移除 NER 模块**：实体提取由 OpenClaw 预处理完成，不再需要自动 NER
- 🗑️ **清理死代码**：删除 9 个废弃文件，约 4098 行代码

**删除的模块**：
- NER 模块 (5 文件): ner_extractor, ner_llm, ner_queue, ner_worker, ner_batch
- SQLite 相关 (3 文件): database.py, models.py Entity, entity_type_cache.py
- 废弃代码 (4 文件): enhanced_relation_crud.py, memory_cli.py, retain_extractor.py, session_hook.py, logger.py

**代码审查修复**：
- ✅ FactKind 枚举冲突 (WISH = "H")
- ✅ 实体类型定义统一 (entity_types.py)
- ✅ 关系类型定义统一
- ✅ 向量维度注释 (2560)
- ✅ 日志调用格式统一

### v2.1 (2026-03-19)

**修复**：
- 🔧 修复 slug 大小写冲突导致图谱显示错误的问题
  - `create_entity` 添加 slug 冲突检测
  - 图谱 API 使用精确匹配而非 `.lower()`
  - 添加测试用例 `tests/test_slug_case.py`

**改进**：
- ✨ 3D 图谱多重边处理优化
- ✨ 添加边贝塞尔曲线渲染
- ✨ 本地化 JS 库，解决 CDN 超时问题

### v2.0 (2026-03-13)

**新增**：
- 🧠 记忆生命周期管理（ACTIVE → ARCHIVED → SUPERSEDED → FORGOTTEN）
- 🔄 矛盾检测与解决机制
- 🏷️ 标签系统
- 🕸️ 3D 知识图谱可视化
- 📊 Web UI 管理界面

**迁移**：
- 从 SQLite 迁移到 LanceDB
- 向量嵌入升级到 Qwen3-Embedding-4B (2560维)

---

## 常见问题

### Q: 如何备份数据？

```bash
./scripts/backup_lancedb.py
```

### Q: 如何重建向量索引？

```bash
# 删除并重建
rm -rf ~/.openclaw/workspace/.memory/lancedb
./migrate.py
```

### Q: 嵌入服务不可用怎么办？

检查 llm.cpp HTTP Server 是否运行：

```bash
curl http://localhost:8080/v1/embeddings
```

### Q: 图谱显示错误？

检查 slug 是否有冲突：

```bash
cd ~/.openclaw/workspace/memory-bank
python3 tests/test_slug_case.py
```

### Q: 录入记忆时如何指定实体和关系？

在 POST /api/facts 请求中直接提供：

```json
{
  "content": "张三在使用 GPT-4 开发新项目",
  "entities": ["张三", "GPT-4", "新项目"],
  "relations": ["张三|使用|GPT-4", "张三|开发|新项目"]
}
```

> **注意**: v2.2 移除了 NER 自动提取功能，实体和关系需要显式指定。

---

## 开发

### 运行测试

```bash
cd ~/.openclaw/workspace/memory-bank
python3 -m pytest tests/
```

### 查看日志

```bash
tail -f ~/.openclaw/workspace/memory-bank/logs/memory_bank.log
```

### 调试模式

```bash
FLASK_DEBUG=1 python3 web/app.py
```

---

## 许可

MIT

---

## 相关文档

- [部署指南](./DEPLOY.md)
- [维护指南](./MAINTENANCE.md)
- [升级计划](./UPGRADE-PLAN.md)
- [生命周期文档](./docs/LIFECYCLE.md)
- [Web UI 说明](./web/README.md)
