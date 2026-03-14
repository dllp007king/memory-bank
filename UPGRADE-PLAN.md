# Memory Bank v2.0 升级计划

## 目标

将 Memory Bank 从简单的存储工具升级为 OpenClaw 的**智能记忆中枢**。

---

## 核心需求

| 需求 | 描述 |
|------|------|
| 自动整理 | 对话结束 10 分钟无新输入 → 自动提取 Retain 存入 |
| 错误记忆 | 记录错误 + 解决方案，下次优先查找 |
| 向量搜索 | 使用 llm.cpp + qwen3-embedding:4b Q8 量化 |
| 监督机制 | minimax-m2.5 监督，报错自修复 |
| 日志记录 | 记录执行过程，卡死后可定位 |
| 数据迁移 | 数据库可迁移到其他位置 |

---

## 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory Bank v2.0                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │ Session Hook │  │  Retain     │  │  Error      │        │
│  │ (10min触发)  │  │  Extractor  │  │  Recorder   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │
│         └────────────────┼────────────────┘                │
│                          ▼                                 │
│              ┌─────────────────────┐                       │
│              │   Memory Core       │                       │
│              │   (SQLite + FTS5)   │                       │
│              └──────────┬──────────┘                       │
│                         │                                  │
│         ┌───────────────┼───────────────┐                  │
│         ▼               ▼               ▼                  │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐           │
│  │ llm.cpp    │  │  CLI/API   │  │   Logger   │           │
│  │ Embedding  │  │  查询接口   │  │  日志系统   │           │
│  │ (Q8 量化)   │  │            │  │            │           │
│  └────────────┘  └────────────┘  └────────────┘           │
│                                                             │
└─────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │   Supervisor        │
                    │   (minimax-m2.5)    │
                    │   - 监控任务执行     │
                    │   - 报错自修复       │
                    │   - 汇报状态        │
                    └─────────────────────┘
```

---

## 记忆类型扩展

| 代码 | 类型 | 描述 |
|------|------|------|
| W | 愿望 | 用户想要什么 |
| B | 经验 | 发生了什么 |
| O | 意见 | 偏好/观点 + 置信度 |
| S | 总结 | 归纳性结论 |
| **E** | **错误** | **错误描述 + 解决方案** |
| **L** | **日志** | **执行过程记录** |

---

## 模块清单

### 1. 向量化模块 (embedding.py)
- 连接 llm.cpp HTTP Server (ggml-qwen3-embedding-4b-q8_0.gguf)
- 批量向量化
- 向量存储 (sqlite-vec)
- Fallback 到 Ollama（可选）

### 2. Retain 提取器 (retain_extractor.py)
- 解析每日日志
- 提取 Retain 条目
- 转换为 Memory Bank 格式

### 3. 错误记录器 (error_recorder.py)
- 捕获异常
- 记录错误 + 解决方案
- 支持查询历史错误

### 4. Session Hook (session_hook.py)
- 监控会话空闲时间
- 10 分钟无输入触发整理
- 调用 Retain 提取器

### 5. 日志系统 (logger.py)
- 结构化日志
- 写入 memory-bank/logs/
- 支持查询

### 6. 监督者 (supervisor.py)
- 监控各模块执行
- 报错时尝试修复
- 向 myclaw 汇报

### 7. 数据迁移工具 (migrate.py)
- 导出/导入数据库
- 支持不同路径

---

## 文件结构

```
memory-bank/
├── memory_bank/
│   ├── __init__.py
│   ├── database.py      # 数据库管理
│   ├── models.py        # 数据模型
│   ├── crud.py          # CRUD 操作
│   ├── search.py        # 搜索功能
│   ├── embedding.py     # [NEW] 向量化
│   ├── retain_extractor.py  # [NEW] Retain 提取
│   ├── error_recorder.py    # [NEW] 错误记录
│   ├── session_hook.py      # [NEW] 会话钩子
│   ├── logger.py            # [NEW] 日志系统
│   └── supervisor.py        # [NEW] 监督者
├── logs/                    # [NEW] 执行日志
├── tests/
├── memory_cli.py
├── sync_to_md.py
├── migrate.py               # [NEW] 迁移工具
└── README.md
```

---

## 子代理任务分配

| 代理 | 任务 | 模型 |
|------|------|------|
| Agent-1 | 向量化模块 (embedding.py) | minimax-m2.5 |
| Agent-2 | Retain 提取器 | minimax-m2.5 |
| Agent-3 | 错误记录器 | minimax-m2.5 |
| Agent-4 | Session Hook + 日志系统 | minimax-m2.5 |
| Agent-5 | 监督者 + 迁移工具 | minimax-m2.5 |

---

## 执行顺序

1. **Phase 1**: 向量化模块 (Agent-1)
2. **Phase 2**: Retain 提取器 + 错误记录器 (Agent-2, Agent-3 并行)
3. **Phase 3**: Session Hook + 日志系统 (Agent-4)
4. **Phase 4**: 监督者 + 迁移工具 (Agent-5)
5. **Phase 5**: 集成测试

---

## 监督流程

```
┌─────────────┐
│  任务开始   │
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│  执行任务   │────▶│  检查结果   │
└─────────────┘     └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │             │
                 成功            失败
                    │             │
                    ▼             ▼
              ┌──────────┐  ┌──────────────┐
              │ 记录日志  │  │ 分析错误原因  │
              │ 返回结果  │  │ 尝试修复      │
              └──────────┘  └───────┬───────┘
                                    │
                                    ▼
                            ┌───────────────┐
                            │ 重试 (最多3次) │
                            └───────┬───────┘
                                    │
                             ┌──────┴──────┐
                             │             │
                          成功           失败
                             │             │
                             ▼             ▼
                       ┌──────────┐  ┌──────────────┐
                       │ 继续     │  │ 汇报 myclaw  │
                       └──────────┘  │ 请求人工干预  │
                                     └──────────────┘
```

---

## 开始时间

2026-03-04 03:05


## 更新
OpenClaw 长期记忆系统升级计划
项目代号: MemoryBank v1.0
创建时间: 2026-03-04
负责人: myclaw (总指挥)
协作者: coder (编程副官) + 子代理池

一、项目背景
现有系统分析
OpenClaw 现有记忆架构：

基于 Markdown 文件（MEMORY.md + memory/YYYY-MM-DD.md）
支持 memory_search 工具（语义搜索）
SQLite 后端 + sqlite-vec 向量加速
支持多种嵌入提供商（OpenAI, Gemini, local, Ollama）
不足之处：

缺乏实体感知检索（"告诉我关于 Peter 的事"）
缺乏意见/偏好追踪（置信度 + 证据）
缺乏自动整理机制（Retain/Recall/Reflect 循环）
时间约束查询较弱
目标架构（Hindsight × Letta 风格）
~/.openclaw/workspace/
├── MEMORY.md                    # 核心记忆（小而精）
├── memory/
│   ├── daily/YYYY-MM/YYYY-MM-DD.md  # 每日日志
│   ├── config/                       # 配置文件
│   └── reports/YYYY-MM/              # 早报存档
├── bank/                        # 类型化记忆页面（新增）
│   ├── world.md                 # 客观事实
│   ├── experience.md            # 经验记录
│   ├── opinions.md              # 主观偏好 + 置信度
│   └── entities/                # 实体页面
│       ├── liu.md
│       ├── xiaoP.md
│       └── ...
└── .memory/
    └── index.sqlite             # 衍生索引（可重建）
二、技术方案
2.1 目录树管理
新增 bank/ 目录结构：

bank/world.md - 客观世界事实
bank/experience.md - 代理经验记录
bank/opinions.md - 用户偏好 + 置信度 + 证据
bank/entities/*.md - 实体专属页面
每日日志增强：

添加 ## Retain 章节用于结构化记忆
格式：[类型] @实体: 内容
类型：W(world), B(biographical), O(opinion), S(summary)
置信度：O(c=0.95)
2.2 向量存储
方案 A: 利用 OpenClaw 内置

配置 memorySearch.provider = "local"
使用 sqlite-vec 扩展
自动嵌入缓存
方案 B: 自建轻量向量库

使用 Python + sentence-transformers
或 Node.js + transformers.js
存储到 SQLite + 向量扩展
2.3 数据库管理
SQLite Schema:

-- 事实表
CREATE TABLE facts (
  id TEXT PRIMARY KEY,
  kind TEXT,  -- world|experience|opinion|summary
  content TEXT,
  timestamp DATETIME,
  source_path TEXT,
  source_line INTEGER,
  entities JSON,
  confidence REAL,
  created_at DATETIME,
  updated_at DATETIME
);

-- 实体表
CREATE TABLE entities (
  slug TEXT PRIMARY KEY,
  name TEXT,
  summary TEXT,
  first_seen DATETIME,
  last_updated DATETIME
);

-- 事实-实体关联
CREATE TABLE fact_entities (
  fact_id TEXT,
  entity_slug TEXT,
  PRIMARY KEY (fact_id, entity_slug)
);

-- 向量表（sqlite-vec）
CREATE VIRTUAL TABLE vec_embeddings USING vec0(
  fact_id TEXT PRIMARY KEY,
  embedding FLOAT[384]  -- 或 768/1536 取决于模型
);

-- FTS5 全文搜索
CREATE VIRTUAL TABLE facts_fts USING fts5(
  content, 
  source_path,
  tokenize='porter unicode61'
);
2.4 混合搜索
检索流程：

BM25 关键词搜索（精确匹配）
向量语义搜索（语义相似）
融合排序（加权）
可选 MMR 去重
可选时间衰减
三、开发计划（TDD）
Phase 1: 基础设施 (Day 1)
任务：

创建 bank/ 目录结构
设计 SQLite Schema
编写数据库迁移脚本
单元测试：Schema 创建、CRUD 操作
测试用例：

def test_create_fact():
    """测试创建事实记录"""
    
def test_fact_entity_link():
    """测试事实-实体关联"""
    
def test_fts_search():
    """测试全文搜索"""
Phase 2: 向量索引 (Day 1-2)
任务：

选择嵌入模型（本地优先）
实现文本嵌入函数
实现向量存储/检索
单元测试：嵌入质量、相似度计算
测试用例：

def test_embedding_dimension():
    """测试嵌入维度正确"""
    
def test_similarity_search():
    """测试相似度搜索返回相关结果"""
    
def test_semantic_vs_keyword():
    """测试语义搜索与关键词搜索的区别"""
Phase 3: 混合搜索 (Day 2)
任务：

实现 BM25 搜索
实现向量搜索
实现融合排序算法
单元测试：搜索质量、性能
测试用例：

def test_hybrid_search_ranking():
    """测试混合搜索排序合理性"""
    
def test_exact_match_boost():
    """测试精确匹配提升权重"""
Phase 4: Retain/Recall/Reflect (Day 2-3)
任务：

实现从每日日志提取 Retain 章节
实现 Recall API（多维度查询）
实现 Reflect 自动整理（更新实体页面、意见置信度）
集成测试
测试用例：

def test_retain_extraction():
    """测试从日志提取 Retain 章节"""
    
def test_recall_by_entity():
    """测试按实体检索"""
    
def test_recall_temporal():
    """测试时间范围检索"""
    
def test_opinion_confidence_update():
    """测试意见置信度更新"""
Phase 5: CLI 集成 (Day 3)
任务：

创建 memory-cli.py 命令行工具
命令：init, index, search, reflect, status
与 OpenClaw 集成
端到端测试
测试用例：

def test_cli_init():
    """测试 CLI 初始化"""
    
def test_cli_search():
    """测试 CLI 搜索"""
    
def test_cli_reflect():
    """测试 CLI 反思整理"""
Phase 6: 验收测试 (Day 3)
任务：

集成测试：完整工作流
性能测试：搜索延迟
边界测试：空数据、错误输入
文档：使用说明
四、任务分配
子代理任务（MiniMax-M2.5 池）
代理	任务	输出
Agent-1	研究 sentence-transformers 本地模型选择	memory/config/嵌入模型选型.md
Agent-2	设计实体识别规则和格式	memory/config/实体识别规范.md
Agent-3	编写测试数据和预期结果	memory/tests/test_data.json
Agent-4	搜索 OpenClaw memory plugin API 文档	memory/config/plugin-api-reference.md
coder 任务（GLM-5 + GLM-4.7 池）
阶段	任务	优先级
Phase 1	数据库 Schema + 迁移脚本	P0
Phase 1	基础 CRUD 操作 + 单元测试	P0
Phase 2	嵌入函数 + 向量存储	P0
Phase 3	混合搜索实现	P1
Phase 4	Retain/Recall/Reflect	P1
Phase 5	CLI 工具	P2
五、容错方案
5.1 模型额度耗尽
主方案: GLM-5 → GLM-4.7 → MiniMax-M2.5
备用: 全部切换到 MiniMax-M2.5（并发5）
本地兜底: Ollama 本地模型（无额度限制）
5.2 嵌入服务不可用
主方案: 本地 sentence-transformers
备用: OpenAI Embeddings API
兜底: 纯 BM25 搜索（无向量）
5.3 数据库错误
SQLite 锁定：重试机制 + WAL 模式
数据损坏：从 Markdown 重建索引
磁盘满：清理旧日志 + 压缩
5.4 子代理超时
单任务超时：5分钟
总任务超时：30分钟
超时处理：记录进度，分批继续
六、验收标准
功能验收
能创建/读取/更新/删除事实记录
能按实体、时间、类型检索
混合搜索返回相关结果
Reflect 能更新实体页面和意见
CLI 工具可用
性能验收
搜索延迟 < 500ms（1000条记录）
索引构建 < 30s（100条记录）
内存占用 < 200MB
质量验收
单元测试覆盖率 > 80%
集成测试通过
无 P0/P1 级别 bug
七、里程碑
时间	里程碑	交付物
Day 1 EOD	Phase 1-2 完成	数据库 + 向量索引
Day 2 EOD	Phase 3-4 完成	混合搜索 + RRR
Day 3 EOD	Phase 5-6 完成	CLI + 验收