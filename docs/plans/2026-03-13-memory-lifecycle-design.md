# Memory Bank - 记忆生命周期设计文档

> 设计日期: 2026-03-13
> 设计师: Claude Code
> 状态: 已批准

---

## 1. 架构概述

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    Web API (Flask)                        │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────────┐   │
│  │ /api/facts │ │ /api/search │ │ /api/memories/*      │   │
│  └─────┬─────┘ └─────┬─────┘ └──────────┬───────────┘   │
└────────┼──────────────┼─────────────────┼──────────────────┘
         │              │                 │
         │              │                 │
┌────────▼──────────────▼─────────────────▼──────────────────┐
│              MemoryLifecycleService                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐       │
│  │ Confidence│  │ DecayRate│  │ Contradiction   │       │
│  │ Inference │  │ Inference│  │ Detection       │       │
│  └──────────┘  └──────────┘  └──────────────────┘       │
└─────────┬──────────┬──────────────┬───────────────────────┘
          │          │              │
┌─────────▼──────────▼──────────────▼───────────────────────┐
│           Existing Modules (unchanged core)                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ MemoryCRUD   │  │ MemorySearch │  │ Embedding    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
└────────────────────────────────────────────────────────────┘
```

### 1.2 设计理念

- **职责分离**: 生命周期逻辑独立于数据访问层
- **渐进增强**: 在现有模块基础上扩展，不破坏原有功能
- **用户确认**: 冲突解决需通过 Web UI 确认

---

## 2. 核心模块设计

### 2.1 MemoryLifecycleService（主服务类）

```python
class MemoryLifecycleService:
    """记忆生命周期服务"""

    def __init__(self, crud: MemoryCRUD, searcher: MemorySearch):
        self.crud = crud
        self.searcher = searcher
        self.confidence_inference = ConfidenceInference()
        self.decay_inference = DecayRateInference()
        self.contradiction_detector = ContradictionDetector()
        self.lifecycle_manager = LifecycleManager()

    # 核心方法
    def add_memory(self, content: str, **kwargs) -> Memory:
        """添加记忆（自动推断置信度、衰减率，检测冲突）"""

    def get_memory_with_lifecycle(self, memory_id: str) -> dict:
        """获取记忆（包含有效置信度、生命周期状态）"""

    def search_memories(self, query: str, limit: int = 10) -> list:
        """搜索记忆（基于有效置信度排序）"""

    def resolve_contradiction(self, memory_id: str, resolution: str) -> bool:
        """解决冲突（accept_new|keep_old|merge）"""

    def get_cleanup_candidates(self, limit: int = 100) -> list:
        """获取清理候选（低优先级记忆）"""

    def get_distillation_candidates(self, limit: int = 100) -> list:
        """获取提炼候选（高优先级、高访问次数记忆）"""
```

### 2.2 ConfidenceInference（置信度推断）

```python
class ConfidenceInference:
    """置信度推断（混合关键词 + LLM）"""

    # 关键词映射
    KEYWORD_PATTERNS = {
        0.9: ["", "是", "确实"],  # 明确陈述
        0.7: ["可能", "好像", "我觉得"],
        0.5: ["推测", "猜测", "推断"],
        0.3: ["听说", "据说", "别人说"],
    }

    def infer(self, content: str) -> float:
        """推断置信度"""
        # 1. 关键词匹配
        keyword_score = self._infer_from_keywords(content)

        # 2. 如果关键词匹配结果在 0.4-0.7 之间，使用 LLM 确认
        if 0.4 <= keyword_score <= 0.7:
            llm_score = self._infer_from_llm(content)
            return (keyword_score + llm_score) / 2

        return keyword_score
```

### 2.3 DecayRateInference（衰减率推断）

```python
class DecayRateInference:
    """衰减率推断（基于内容稳定性）"""

    STABILITY_PATTERNS = {
        0.0001: ["永远是", "始终", "永远", "必然", "一定", "真理"],  # 恒定
        0.001: ["我是", "我会", "我的", "相信", "价值观", "性格", "习惯"],  # 长期
        0.01: ["正在", "当前", "现在", "最近", "这个月", "项目"],  # 中期（默认）
        0.05: ["打算", "计划", "下周", "准备", "想要", "将要"],  # 短期
        0.2: ["今天", "此刻", "马上", "现在就"],  # 即时
    }

    def infer(self, content: str) -> float:
        """从内容推断衰减率"""
        for rate, patterns in self.STABILITY_PATTERNS.items():
            for pattern in patterns:
                if pattern in content:
                    return rate
        return 0.01  # 默认中期
```

---

## 3. 相似度和冲突检测

### 3.1 相似度计算（文本 + 向量混合）

```python
class SimilarityCalculator:
    """相似度计算器（文本 + 向量混合）"""

    def __init__(self, text_weight: float = 0.4, vector_weight: float = 0.6):
        self.text_weight = text_weight
        self.vector_weight = vector_weight

    def calculate(self, memory1: Memory, memory2: Memory) -> float:
        """计算两条记忆的相似度"""
        # 1. 文本相似度（BM25）
        text_sim = self._text_similarity(memory1.content, memory2.content)

        # 2. 向量相似度（余弦）
        vector_sim = self._vector_similarity(memory1.vector, memory2.vector)

        # 3. 加权融合
        return self.text_weight * text_sim + self.vector_weight * vector_sim
```

### 3.2 冲突检测器

```python
class ContradictionDetector:
    """冲突检测器"""

    def __init__(self, threshold: float = 0.15):
        self.threshold = threshold
        self.similarity_calculator = SimilarityCalculator()

    def check_new_memory(self, new_memory: Memory) -> dict:
        """检查新记忆与现有记忆的冲突"""
        similar = self._find_similar_memories(new_memory)

        results = []
        for old_memory in similar:
            old_effective = self._effective_confidence(old_memory)
            new_effective = new_memory.confidence

            if abs(old_effective - new_effective) > self.threshold:
                # 检测到潜在冲突
                results.append({
                    "old_id": old_memory.id,
                    "similarity": similar[old_memory.id]["score"],
                    "old_effective": old_effective,
                    "new_effective": new_effective,
                    "resolution": self._suggest_resolution(old_effective, new_effective)
                })

        return {"has_conflicts": len(results) > 0, "conflicts": results}
```

---

## 4. Web API 扩展

### 4.1 新增 API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/api/memories` | 添加记忆（自动应用生命周期逻辑） |
| GET | `/api/memories/<id>/contradictions` | 获取记忆的冲突列表 |
| POST | `/api/memories/<id>/resolve` | 解决记忆冲突 |
| GET | `/api/memories/cleanup-candidates` | 获取清理候选列表 |
| GET | `/api/memories/distillation-candidates` | 获取提炼候选列表 |

### 4.2 UI 界面设计

**冲突确认页面:**
- 显示需要确认的记忆冲突
- 每个冲突显示：旧记忆内容、新记忆内容、有效置信度对比
- 提供"接受新记忆"、"保留旧记忆"、"合并"三个操作按钮

**记忆维护页面:**
- 清理候选列表（低优先级记忆）
- 提炼候选列表（高价值记忆）
- 批量操作功能

**搜索结果增强:**
- 显示有效置信度
- 显示生命周期状态

---

## 5. 数据库 Schema 变更

### 5.1 MEMORIES_SCHEMA 新增字段

```python
# 衰减率（默认 0.01 中期）
pa.field("decay_rate", pa.float32(), nullable=False,
         default=0.01, metadata={"description": "衰减率 0.0001-0.2"}),

# 生命周期状态（默认 ACTIVE）
pa.field("lifecycle_state", pa.string(), nullable=False,
         default="ACTIVE", metadata={"description": "生命周期状态"}),

# 被哪条记忆取代
pa.field("superseded_by", pa.string(), nullable=True,
         metadata={"description": "取代此记忆的记忆 ID"}),

# 访问次数
pa.field("access_count", pa.int32(), nullable=False,
         default=0, metadata={"description": "访问次数"}),

# 最后访问时间
pa.field("last_accessed_at", pa.timestamp("us"), nullable=True,
         metadata={"description": "最后访问时间"}),
```

### 5.2 Lifecycle 状态常量

```python
class LifecycleState:
    ACTIVE = "ACTIVE"           # 活跃，正常检索
    ARCHIVED = "ARCHIVED"       # 已归档，降低检索权重
    SUPERSEDED = "SUPERSEDED"   # 已被取代，仅保留历史
    FORGOTTEN = "FORGOTTEN"     # 已遗忘，标记待删除
```

### 5.3 数据库迁移策略

- 清空现有数据库
- 使用新的 schema 创建表
- 添加数据时自动填充新字段的默认值

---

## 6. 核心算法

### 6.1 有效置信度计算

```python
def effective_confidence(memory: Memory) -> float:
    """
    有效置信度 = 基础置信度 × 时间衰减
    """
    days = (datetime.now() - memory.timestamp).days
    decay = math.exp(-memory.decay_rate * days)
    return memory.confidence * decay
```

### 6.2 检索得分计算

```python
def search_score(relevance: float, effective: float) -> float:
    """
    检索得分 = 相关性 × 有效置信度
    注意：importance 不影响检索得分
    """
    return relevance * effective
```

### 6.3 清理优先级计算

```python
def cleanup_priority(memory: Memory) -> float:
    """
    清理优先级（越高越应该清理）
    = (1 - importance) × (1 - effective) × 天数
    """
    days = (datetime.now() - memory.timestamp).days
    effective = effective_confidence(memory)
    return (1 - memory.importance) * (1 - effective) * days
```

### 6.4 提炼优先级计算

```python
def distill_priority(memory: Memory) -> float:
    """
    提炼优先级（越高越应该提炼成知识）
    = importance × access_count × 天数
    """
    days = (datetime.now() - memory.timestamp).days
    return memory.importance * memory.access_count * days
```

### 6.5 记忆保留判断

```python
def should_keep(memory: Memory) -> bool:
    """
    判断是否应该保留记忆
    """
    effective = effective_confidence(memory)

    # 重要且可信 → 始终保留
    if memory.importance > 0.8 and effective > 0.5:
        return True

    # 不重要且不可信 → 清理
    if memory.importance < 0.3 and effective < 0.3:
        return False

    # 其他情况根据有效置信度判断
    return effective > 0.1
```

---

## 7. 相似度分级策略

### 7.1 相似度分级

| 相似度 | 策略 | 说明 |
|--------|------|------|
| > 0.95 | 覆盖更新 | 内容几乎相同，更新时间戳 |
| 0.85-0.95 | 合并更新 | 内容相关，合并信息 |
| 0.70-0.85 | 关联创建 | 创建新记忆，关联旧记忆 |
| < 0.70 | 独立创建 | 完全不同，独立创建 |

### 7.2 矛盾判断阈值

```
阈值 = 0.15
new_effective > old_effective + 阈值 → 更新
old_effective > new_effective + 阈值 → 保留
否则 → 需要确认
```

---

## 8. 项目结构和实现顺序

### 8.1 新增文件结构

```
memory_bank/
├── lifecycle/                          # 新增生命周期模块
│   ├── __init__.py
│   ├── service.py                      # MemoryLifecycleService（主服务）
│   ├── confidence.py                    # 置信度推断
│   ├── decay_rate.py                   # 衰减率推断
│   ├── similarity.py                   # 相似度计算
│   ├── contradiction.py                # 冲突检测
│   └── manager.py                     # 生命周期状态管理
├── lance_schema.py                     # 修改：添加新字段
├── lance_crud.py                      # 修改：支持新字段
├── lance_search.py                    # 修改：使用有效置信度排序
├── models.py                          # 修改：Memory 类扩展
└── web/
    ├── app.py                          # 修改：新增 API 端点
    └── templates/
        ├── index.html                  # 修改：添加新 UI 页面
        ├── conflicts.html              # 新增：冲突确认页面
        └── maintenance.html          # 新增：记忆维护页面
```

### 8.2 实现顺序

**P0 - 核心功能：**
1. 修改 `lance_schema.py` - 添加新字段
2. 修改 `models.py` - 扩展 Memory 类
3. 创建 `lifecycle/decay_rate.py` - 衰减率推断
4. 创建 `lifecycle/confidence.py` - 置信度推断
5. 实现有效置信度计算函数
6. 修改 `lance_search.py` - 搜索使用有效置信度

**P1 - 冲突检测：**
7. 创建 `lifecycle/similarity.py` - 相似度计算
8. 创建 `lifecycle/contradiction.py` - 冲突检测
9. 实现 `lifecycle/service.py` - add_memory 流程

**P2 - 生命周期管理：**
10. 创建 `lifecycle/manager.py` - 状态管理
11. 创建 `lifecycle/service.py` - 清理/提炼候选
12. 修改 `web/app.py` - 新增 API 端点
13. 创建 `web/templates/conflicts.html` - 冲突确认 UI
14. 创建 `web/templates/maintenance.html` - 记忆维护 UI

---

## 9. 验收标准

- [ ] 有效置信度计算正确
- [ ] 衰减率自动推断准确
- [ ] 相似记忆检测有效
- [ ] 冲突检测并提示用户确认
- [ ] Web UI 可以确认和解决冲突
- [ ] 清理候选列表正确排序
- [ ] 提炼候选列表正确排序
- [ ] 生命周期状态正确流转

---

*文档版本: 1.0*
