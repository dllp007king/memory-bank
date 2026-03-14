# 记忆生命周期修复总结

## 修复内容

### 1. `memory_bank/lance_crud.py` - create_memory() 方法
- 添加 `skip_lifecycle` 参数用于批量导入
- 集成相似度检测 (`find_similar_memories`)
- 集成矛盾检测 (`detect_contradiction`)
- 集成矛盾处理 (`handle_contradiction`)
- 实现相似度策略 (`get_update_strategy`)
  - OVERWRITE: 删除旧记忆
  - MERGE: 标记旧记忆为 SUPERSEDED
  - LINK: 创建新记忆并关联
  - CREATE: 独立创建

### 2. `memory_bank/lance_crud.py` - get_memory() 方法
- 添加 `update_access` 参数
- 调用 `_increment_access_count()` 更新访问计数

### 3. `memory_bank/lance_crud.py` - list_memories() 方法
- 添加 `lifecycle_state` 参数过滤状态
- 添加 `include_inactive` 参数
- 默认只返回 ACTIVE 状态

### 4. `memory_bank/lance_crud.py` - _increment_access_count() 方法
- 修复无限循环问题（直接查询数据库而不是调用 get_memory）

### 5. `memory_bank/lance_crud.py` - search_memories() 方法
- 添加 `use_effective_confidence` 参数
- 添加 `update_access` 参数
- 使用有效置信度重新排序
- 过滤只返回 ACTIVE 状态

### 6. `memory_bank/lance_search.py` - vector_search() 方法
- 添加 `use_effective_confidence` 参数
- 添加 `lifecycle_state = 'ACTIVE'` 过滤
- 计算有效置信度
- 最终得分 = 相关性 × 有效置信度

---

## 完整的记忆创建 JSON 格式

### 基础格式

```json
{
  "content": "记忆内容",
  "memory_type": "fact",
  "confidence": 1.0,
  "importance": 0.5,
  "source": "",
  "entities": [],
  "relations": [],
  "tags": []
}
```

### 完整字段说明

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `content` | string | 是 | - | 记忆内容 |
| `memory_type` | string | 否 | "fact" | 记忆类型: fact, experience, preference, summary |
| `confidence` | float | 否 | 1.0 | 置信度 0.0-1.0 |
| `importance` | float | 否 | 0.5 | 重要性 0.0-1.0 |
| `source` | string | 否 | "" | 来源描述 |
| `entities` | array | 否 | [] | 关联实体 slug 列表 |
| `relations` | array | 否 | [] | 关系列表 [{"from": "A", "rel": "类型", "to": "B"}] |
| `tags` | array | 否 | [] | 标签列表 |
| `auto_embed` | boolean | 否 | true | 是否自动生成向量 |
| `skip_lifecycle` | boolean | 否 | false | 是否跳过生命周期检测 |

### 记忆类型 (memory_type)

| 类型 | 说明 | 示例 |
|------|------|------|
| `fact` | 事实信息 | "地球是圆的" |
| `experience` | 经验/传记 | "我学会了游泳" |
| `preference` | 意见/偏好 | "我喜欢吃辣的食物" |
| `summary` | 总结/概要 | "今天的会议讨论了三个主题" |

### 置信度 (confidence) 指导

| 置信度 | 来源 |
|--------|------|
| 0.9-1.0 | 用户明确陈述、对话中直接获取 |
| 0.7-0.9 | 带不确定性词（"可能"、"好像"、"我记得"） |
| 0.5-0.7 | 从上下文推断 |
| 0.3-0.5 | 猜测、推测 |
| 0.1-0.3 | 第三方信息、小道消息 |

### 重要性 (importance) 指导

| 级别 | 范围 | 示例 |
|------|------|------|
| 关键 | 0.9-1.0 | 项目计划、核心知识、重要决策 |
| 重要 | 0.7-0.9 | 工作任务、技术细节、会议结论 |
| 一般 | 0.4-0.7 | 日常对话、常规信息 |
| 较低 | 0.2-0.4 | 闲聊、八卦、小道消息 |
| 无关紧要 | 0.0-0.2 | 随口一说、临时状态 |

### 关系格式 (relations)

```json
{
  "relations": [
    {
      "from": "实体A",
      "rel": "WORKS_WITH",
      "to": "实体B"
    },
    {
      "from": "实体C",
      "rel": "LIKES",
      "to": "实体D"
    }
  ]
}
```

### 关系类型 (rel)

- `KNOWS` - 认识
- `WORKS_WITH` - 共事
- `RELATED_TO` - 相关
- `LOCATED_AT` - 位于
- `PART_OF` - 属于
- `MANAGES` - 管理
- `CREATED` - 创建
- `MENTIONS` - 提及
- `WORKS_AT` - 工作于
- `REPORTS_TO` - 汇报给
- `WORKS_ON` - 参与项目
- `INVESTED_BY` - 被投资
- `FRIENDS_WITH` - 友好关系
- `ENEMIES_WITH` - 敌对关系
- `MANAGED_BY` - 被管理

---

## 使用示例

### API 调用示例

```bash
# 创建记忆
curl -X POST http://localhost:5000/api/memories \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "陆惊寒喜欢柳轻眉",
    "memory_type": "fact",
    "confidence": 0.9,
    "importance": 0.8,
    "entities": ["陆惊寒", "柳轻眉"],
    "relations": [
      {"from": "陆惊寒", "rel": "LIKES", "to": "柳轻眉"}
    ]
  }'
```

### Python 代码示例

```python
from memory_bank.lance_crud import get_crud

crud = get_crud()

# 创建记忆
memory = crud.create_memory(
    content="陆惊寒喜欢柳轻眉",
    memory_type="fact",
    confidence=0.9,
    importance=0.8,
    entities=["陆惊寒", "柳轻眉"],
    relations=[{"from": "陆惊寒", "rel": "LIKES", "to": "柳轻眉"}]
)

# 搜索记忆（自动使用有效置信度排序）
results = crud.search_memories("陆惊寒喜欢谁", limit=5)

# 获取记忆（自动更新访问计数）
memory = crud.get_memory(memory_id)
```

---

## 生命周期状态流转

```
创建记忆 (ACTIVE)
    ↓
检测相似记忆
    ↓
    ├─ 相似度 > 0.95 → 覆盖更新（删除旧）
    ├─ 0.85-0.95 → 合并更新（旧→SUPERSEDED）
    ├─ 0.70-0.85 → 关联创建
    └─ < 0.70 → 独立创建
```

### 矛盾处理

```
检测到矛盾
    ↓
比较有效置信度
    ↓
    ├─ new > old + 0.15 → UPDATE（旧→SUPERSEDED）
    ├─ old > new + 0.15 → KEEP（不创建新记忆）
    └─ 否则 → CONFIRM（两者都保留，需用户确认）
```

---

## 搜索排序公式

```
有效置信度 = confidence × e^(-decay_rate × days)

搜索得分 = 相关性 × 有效置信度
```

**注意**：importance 不影响搜索得分，只影响：
- 清理优先级
- 提炼优先级
- 记忆保留判断
