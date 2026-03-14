# Memory Bank - 记忆生命周期设计

> 核心设计理念文档，用于指导核心代码实现

## 设计哲学

记忆系统应模拟人类记忆的特性：
- **实时更新** - 当前状态会覆盖旧状态
- **时间衰减** - 长时间不提起的记忆会遗忘
- **知识进化** - 新信息替代旧信息

---

## 一、置信度系统

### 1.1 核心原则

```
置信度 ∈ [0, 1]
置信度随时间衰减
新信息自然有机会更新旧信息
```

### 1.2 有效置信度计算

```python
def effective_confidence(memory: Memory) -> float:
    """
    有效置信度 = 基础置信度 × 时间衰减
    """
    days = (datetime.now() - memory.timestamp).days
    decay = math.exp(-memory.decay_rate * days)
    return memory.confidence * decay
```

### 1.3 置信度的含义

| 置信度 | 来源 |
|--------|------|
| 0.9-1.0 | 用户明确陈述、对话中直接获取 |
| 0.7-0.9 | 带不确定性词（"可能"、"好像"、"我记得"） |
| 0.5-0.7 | 从上下文推断 |
| 0.3-0.5 | 猜测、推测 |
| 0.1-0.3 | 第三方信息、小道消息 |

---

## 二、衰减率分类（普适模型）

### 2.1 信息稳定性光谱

基于**变化的时间尺度**，而非信息类型：

```
恒定 ←————————————————————→ 瞬变
  |                           |
  宇宙规律        日常琐事
  几乎不变        每秒在变
```

### 2.2 五级衰减率

| 级别 | 名称 | λ值 | 时间尺度 | 示例 |
|------|------|-----|----------|------|
| 1 | 恒定 | 0.0001 | 几乎不变 | 数学真理、物理定律、身份信息 |
| 2 | 长期 | 0.001 | 年 | 价值观、核心技能、家庭关系、人格特质 |
| 3 | 中期 | 0.01 | 月 | 项目状态、工作关系、季节偏好、知识更新 |
| 4 | 短期 | 0.05 | 周 | 计划、意图、当前任务、临时偏好 |
| 5 | 即时 | 0.2 | 天/小时 | 情绪、位置、活动、瞬时状态 |

### 2.3 衰减曲线

```
置信度
1.0 ─┬──────────────────────────────
     │  ● 恒定 (λ=0.0001)
0.8 ─┤      ● 长期 (λ=0.001)
     │          ● 中期 (λ=0.01)
0.6 ─┤              ● 短期 (λ=0.05)
     │                  ● 即时 (λ=0.2)
0.4 ─┤                      ●
     │                          ●
0.2 ─┤                              ●
     └─────────────────────────────────→ 天数
     0   30  60  90  120 150 180 210
```

### 2.4 自动推断衰减率

```python
STABILITY_PATTERNS = {
    # 恒定 - 永久性词汇
    0.0001: ["永远是", "始终", "永远", "必然", "一定", "真理"],

    # 长期 - 身份和特质
    0.001: ["我是", "我会", "我的", "相信", "价值观", "性格", "习惯"],

    # 中期 - 状态和关系
    0.01: ["正在", "当前", "现在", "最近", "这个月", "项目"],

    # 短期 - 计划和意图
    0.05: ["打算", "计划", "下周", "准备", "想要", "将要"],

    # 即时 - 瞬时状态
    0.2: ["今天", "此刻", "正在", "马上", "现在就"],
}

def infer_decay_rate(content: str) -> float:
    """从内容推断衰减率"""
    for rate, patterns in STABILITY_PATTERNS.items():
        for pattern in patterns:
            if pattern in content:
                return rate
    return 0.01  # 默认中期
```

---

## 三、更新策略

### 3.1 相似度分级

| 相似度 | 策略 | 说明 |
|--------|------|------|
| > 0.95 | 覆盖更新 | 内容几乎相同，更新时间戳 |
| 0.85-0.95 | 合并更新 | 内容相关，合并信息 |
| 0.70-0.85 | 关联创建 | 创建新记忆，关联旧记忆 |
| < 0.70 | 独立创建 | 完全不同，独立创建 |

### 3.2 矛盾处理

```python
def handle_contradiction(old: Memory, new: Memory) -> str:
    """
    处理矛盾信息

    Returns:
        "update" - 更新旧记忆
        "keep" - 保留旧记忆，标记新记忆
        "confirm" - 需要用户确认
    """
    old_effective = effective_confidence(old)
    new_effective = new.confidence  # 新记忆无衰减

    if new_effective > old_effective + 0.15:
        return "update"
    elif old_effective > new_effective + 0.15:
        return "keep"
    else:
        return "confirm"
```

### 3.3 偏好变化处理

```
旧: "我爱吃冰激凌" → 标记"历史偏好"，存档
新: "我不爱吃冰激凌" → 标记"当前偏好"，生效
```

---

## 四、数据库字段扩展

### 4.1 新增字段

```python
# memories 表
pa.field("decay_rate", pa.float32(), default=0.01),      # 衰减率
pa.field("lifecycle_state", pa.string(), default="ACTIVE"),  # 生命周期状态
pa.field("superseded_by", pa.string()),                  # 被哪条记忆取代
pa.field("access_count", pa.int32(), default=0),         # 访问次数
pa.field("last_accessed_at", pa.timestamp("us")),        # 最后访问时间
```

### 4.2 生命周期状态

| 状态 | 说明 |
|------|------|
| ACTIVE | 活跃记忆，正常检索 |
| ARCHIVED | 已归档，降低检索权重 |
| SUPERSEDED | 已被取代，仅保留历史 |
| FORGOTTEN | 已遗忘，标记待删除 |

---

## 五、API 扩展

### 5.1 确认记忆

```bash
POST /api/memories/{id}/confirm
```

### 5.2 查看矛盾

```bash
GET /api/memories/{id}/contradictions
```

### 5.3 解决冲突

```bash
POST /api/memories/{id}/resolve
{
    "resolution": "accept_new|keep_old|merge"
}
```

---

## 六、重要程度 (importance) 的作用

### 6.1 importance vs confidence

| 属性 | 含义 | 影响什么 |
|------|------|----------|
| confidence | 来源可靠性 | 信息是否可信、是否被更新 |
| importance | 事实重要性 | 检索排名、清理优先级、提炼顺序 |

### 6.2 importance 的三个作用

> **注意**：importance 不影响检索得分，检索仅基于相关性和有效置信度

#### 1) 清理优先级

```python
def cleanup_priority(memory: Memory) -> float:
    """
    清理优先级（越高越应该清理）
    = (1 - importance) × (1 - effective) × 天数

    其中 effective = effective_confidence = confidence × e^(-λ × days)
    """
    days = (datetime.now() - memory.timestamp).days
    effective = effective_confidence(memory)  # 有效置信度
    return (1 - memory.importance) * (1 - effective) * days
```

#### 2) 提炼优先级

```python
def distill_priority(memory: Memory) -> float:
    """
    提炼优先级（越高越应该提炼成知识）
    = importance × access_count × 天数
    """
    days = (datetime.now() - memory.timestamp).days
    return memory.importance * memory.access_count * days
```

#### 3) 记忆保留阈值

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

### 6.3 importance 的重要性级别

| 级别 | 范围 | 示例 |
|------|------|------|
| 关键 | 0.9-1.0 | 项目计划、核心知识、重要决策 |
| 重要 | 0.7-0.9 | 工作任务、技术细节、会议结论 |
| 一般 | 0.4-0.7 | 日常对话、常规信息 |
| 较低 | 0.2-0.4 | 闲聊、八卦、小道消息 |
| 无关紧要 | 0.0-0.2 | 随口一说、临时状态 |

---

## 七、核心公式总结

### 有效置信度 (effective)
```
effective = confidence × e^(-λ × days)

其中：
- confidence: 基础置信度（0-1）
- λ: 衰减率（根据内容稳定性自动推断）
- days: 距离创建的天数
```

### 检索得分（不使用 importance）
```
score = relevance × effective
```

### 清理优先级
```
cleanup = (1 - importance) × (1 - effective) × days
```

### 提炼优先级
```
distill = importance × access_count × days
```

### 衰减率选择
```
λ = infer_decay_rate(content)
默认 λ = 0.01（中期）
```

### 矛盾判断阈值
```
阈值 = 0.15
new_effective > old_effective + 阈值 → 更新
old_effective > new_effective + 阈值 → 保留
否则 → 需要确认
```

---

## 七、实现优先级

| 优先级 | 功能 | 说明 |
|--------|------|------|
| P0 | 有效置信度计算 | 核心逻辑 |
| P0 | 衰减率自动推断 | 从内容推断 λ |
| P1 | 相似记忆检测 | 避免重复存储 |
| P1 | 矛盾检测 | 检测冲突信息 |
| P2 | 偏好变化处理 | 标记历史偏好 |
| P2 | 生命周期管理 | 状态流转 |

---

*文档版本: 1.0*
*最后更新: 2026-03-13*
