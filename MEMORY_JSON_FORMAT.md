# 记忆创建 JSON 格式

## 最简格式

```json
{
  "content": "记忆内容"
}
```

## 完整格式

```json
{
  "content": "陆惊寒喜欢柳轻眉",
  "memory_type": "fact",
  "confidence": 0.9,
  "importance": 0.8,
  "source": "用户对话",
  "entities": ["陆惊寒", "柳轻眉"],
  "relations": ["陆惊寒|LIKES|柳轻眉"],
  "tags": ["情感", "人物关系"],
  "auto_embed": true,
  "skip_lifecycle": false
}
```

---

## 字段说明

### 基础字段

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `content` | string | ✅ | - | 记忆内容 |
| `memory_type` | string | ❌ | "fact" | 记忆类型 |
| `confidence` | float | ❌ | 1.0 | 置信度 0.0-1.0 |
| `importance` | float | ❌ | 0.5 | 重要性 0.0-1.0 |
| `source` | string | ❌ | "" | 来源描述 |
| `auto_embed` | boolean | ❌ | true | 是否自动生成向量 |
| `skip_lifecycle` | boolean | ❌ | false | 是否跳过生命周期检测 |

### 实体字段 (entities)

支持三种格式：

#### 格式1: 简单字符串（兼容）
```json
{
  "entities": ["陆惊寒", "柳轻眉", "破阵营"]
}
```

#### 格式2: 简化关系格式（推荐用于关系）
```json
{
  "entities": [
    {"slug": "陆惊寒", "name": "陆惊寒", "entity_type": "PERSON"},
    {"slug": "柳轻眉", "name": "柳轻眉", "entity_type": "PERSON"}
  ]
}
```

实体对象属性：

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `slug` | string | ✅ | 唯一标识符 |
| `name` | string | ✅ | 显示名称 |
| `entity_type` | string | ❌ | 实体类型，默认 "PERSON" |
| `confidence` | float | ❌ | 提及置信度 0.0-1.0，默认 1.0 |
| `role` | string | ❌ | 实体在记忆中的角色，详见下方说明 |
| `mention_count` | int | ❌ | 提及次数，默认 1 |

### Role（实体角色）定义

实体角色用于描述实体在记忆中的语义角色，帮助理解记忆的上下文关系。

#### 基础角色

| 角色 | 代码 | 说明 | 示例 |
|------|------|------|------|
| 主语 | `subject` | 动作的执行者 | "陆惊寒喜欢柳轻眉" 中的陆惊寒 |
| 宾语 | `object` | 动作的接受者 | "陆惊寒喜欢柳轻眉" 中的柳轻眉 |

#### 领有关系

| 角色 | 代码 | 说明 | 示例 |
|------|------|------|------|
| 领有者 | `possessor` | 拥有者（的） | "陆惊寒的书" 中的陆惊寒 |
| 整体部分 | `part_of` | 属于整体的一部分 | "陆惊寒是破阵营成员" 中的破阵营 |

#### 关系角色

| 角色 | 代码 | 说明 | 示例 |
|------|------|------|------|
| 行动者 | `actor` | 执行动作的人 | "陆惊寒创建了破阵营" 中的陆惊寒 |
| 接受者 | `patient` | 动作的接受者 | "陆惊寒帮助了慕云曦" 中的慕云曦 |
| 受益者 | `beneficiary` | 行动的受益者 | "陆惊寒给慕云曦礼物" 中的慕云曦 |
| 体验者 | `experiencer` | 体验某事的人 | "陆惊寒经历了一次冒险" 中的陆惊寒 |

#### 交际角色

| 角色 | 代码 | 说明 | 示例 |
|------|------|------|------|
| 说话者 | `speaker` | 发言者 | "陆惊寒说：..." 中的陆惊寒 |
| 对话对象 | `addressee` | 对话的对方 | "陆惊寒对柳轻眉说：..." 中的柳轻眉 |
| 观察者 | `observer` | 旁观者 | "陆惊寒看到了..." 中的陆惊寒 |

#### 信息角色

| 角色 | 代码 | 说明 | 示例 |
|------|------|------|------|
| 话题对象 | `topic` | 被讨论的对象 | "讨论陆惊寒" 中的陆惊寒 |
| 被提及 | `mentioned` | 在对话中被提及 | "有人提到了陆惊寒" 中的陆惊寒 |
| 被引用 | `referenced` | 被引用参考 | "参考陆惊寒的观点" 中的陆惊寒 |

#### Role 使用示例

```json
{
  "content": "陆惊寒喜欢柳轻眉",
  "entities": [
    {
      "slug": "lu_jinghan",
      "name": "陆惊寒",
      "entity_type": "PERSON",
      "confidence": 1.0,
      "role": "subject",
      "mention_count": 1
    },
    {
      "slug": "liu_qingmei",
      "name": "柳轻眉",
      "entity_type": "PERSON",
      "confidence": 0.9,
      "role": "object",
      "mention_count": 1
    }
  ]
}

{
  "content": "陆惊寒的书",
  "entities": [
    {
      "slug": "lu_jinghan",
      "name": "陆惊寒",
      "entity_type": "PERSON",
      "role": "possessor",
      "mention_count": 5
    }
  ]
}

{
  "content": "陆惊寒帮助了慕云曦",
  "entities": [
    {
      "slug": "lu_jinghan",
      "name": "陆惊寒",
      "entity_type": "PERSON",
      "role": "actor"
    },
    {
      "slug": "mu_yunxi",
      "name": "慕云曦",
      "entity_type": "PERSON",
      "role": "beneficiary"
    }
  ]
}
```

#### Role 常量

```python
from memory_bank import EntityRole

EntityRole.SUBJECT           # 主语
EntityRole.OBJECT            # 宾语
EntityRole.POSSESSOR         # 领有者
EntityRole.PART_OF            # 整体部分
EntityRole.ACTOR             # 行动者
EntityRole.PATIENT            # 接受者
EntityRole.BENEFICIARY       # 受益者
EntityRole.EXPERIENCER      # 体验者
EntityRole.SPEAKER            # 说话者
EntityRole.ADDRESSEE          # 对话对象
EntityRole.OBSERVER           # 观察者
EntityRole.TOPIC             # 话题对象
EntityRole.MENTIONED          # 被提及
EntityRole.REFERENCED         # 被引用
```

### 关系字段 (relations)

支持两种格式：

#### 格式1: 简化字符串格式 "A|关系|B"
```json
{
  "relations": [
    "陆惊寒|LIKES|柳轻眉",
    "陆惊寒|WORKS_ON|破阵营"
  ]
}
```

#### 格式2: 对象格式
```json
{
  "relations": [
    {
      "source": "陆惊寒",
      "relation_type": "LIKES",
      "target": "柳轻眉",
      "description": "喜欢",
      "confidence": 1.0
    }
  ]
}
```

关系对象属性：

| 属性 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source` | string | ✅ | 源实体 slug |
| `target` | string | ✅ | 目标实体 slug |
| `relation_type` | string | ✅ | 关系类型 |
| `description` | string | ❌ | 关系描述 |
| `confidence` | float | ❌ | 置信度 0.0-1.0，默认 1.0 |

**注意**: 对象格式中的 `relation_type` 也支持使用 `rel` 字段作为别名。

---

## 记忆类型 (memory_type)

```json
{
  "fact": "事实信息",
  "experience": "经验/传记",
  "preference": "偏好/喜好",
  "summary": "总结/摘要"
}
```

---

## 置信度推断

```
0.9-1.0: 用户明确陈述、对话中直接获取
0.7-0.9: 带不确定性词（"可能"、"好像"、"我记得"）
0.5-0.7: 从上下文推断
0.3-0.5: 猜测、推测
0.1-0.3: 第三方信息、小道消息
```

---

## 重要性级别

```
0.9-1.0: 关键（项目计划、核心知识、重要决策）
0.7-0.9: 重要（工作任务、技术细节、会议结论）
0.4-0.7: 一般（日常对话、常规信息）
0.2-0.4: 较低（闲聊、八卦、小道消息）
0.0-0.2: 无关紧要（随口一说、临时状态）
```

---

## 实体类型

```python
EntityType.PERSON    # 人物
EntityType.PLACE      # 地点
EntityType.ORG        # 组织
EntityType.EVENT      # 事件
EntityType.TOPIC      # 主题
EntityType.PRODUCT    # 产品
EntityType.CONCEPT    # 概念
```

---

## 关系类型

```python
RelationType.KNOWS           # 认识
RelationType.LIKES           # 喜欢
RelationType.LOVES           # 爱
RelationType.HATES           # 憎恨
RelationType.WORKS_WITH     # 共事
RelationType.WORKS_AT       # 工作于
RelationType.RELATED_TO     # 相关
RelationType.LOCATED_AT     # 位于
RelationType.PART_OF         # 属于
RelationType.MANAGES         # 管理
RelationType.CREATED         # 创建
RelationType.MENTIONS        # 提及
RelationType.REPORTS_TO     # 汇报给
RelationType.WORKS_ON        # 参与项目
RelationType.INVESTED_BY     # 被投资
RelationType.FRIENDS_WITH    # 友好
RelationType.ENEMIES_WITH    # 敌对
RelationType.MANAGED_BY      # 被管理
RelationType.MARRIED_TO      # 结婚
RelationType.ENGAGED_TO      # 订婚
RelationType.FORMERLY_MARRIED  # 曾婚
```

---

## API 使用示例

### 1. 简单格式

```bash
curl -X POST http://localhost:5000/api/memories \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "陆惊寒喜欢柳轻眉",
    "memory_type": "fact",
    "confidence": 0.9,
    "importance": 0.8,
    "entities": ["陆惊寒", "柳轻眉"],
    "relations": ["陆惊寒|LIKES|柳轻眉"]
  }'
```

### 2. 实体对象格式

```bash
curl -X POST http://localhost:5000/api/memories \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "慕云曦喜欢陆惊寒",
    "memory_type": "preference",
    "confidence": 0.9,
    "importance": 0.8,
    "entities": [
      {
        "slug": "慕云曦",
        "name": "慕云曦",
        "entity_type": "PERSON",
        "role": "subject",
        "confidence": 1.0
      },
      {
        "slug": "陆惊寒",
        "name": "陆惊寒",
        "entity_type": "PERSON",
        "role": "object",
        "confidence": 0.9
      }
    ]
  }'
```

### 3. 关系对象格式

```bash
curl -X POST http://localhost:5000/api/memories \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "陆惊寒参与破阵营项目",
    "memory_type": "fact",
    "confidence": 0.9,
    "importance": 0.9,
    "entities": ["陆惊寒", "破阵营"],
    "relations": [
      {
        "source": "陆惊寒",
        "relation_type": "WORKS_ON",
        "target": "破阵营",
        "description": "参与项目"
      }
    ]
  }'
```

### 4. Python 代码示例

```python
from memory_bank.lance_crud import get_crud
from memory_bank import EntityRef, RelationRef, EntityType, RelationType

crud = get_crud()

# 简单格式（兼容）
memory = crud.create_memory(
    content="陆惊寒喜欢柳轻眉",
    entities=["陆惊寒", "柳轻眉"],
    relations=["陆惊寒|LIKES|柳轻眉"]
)

# 完整对象格式
memory = crud.create_memory(
    content="慕云曦喜欢陆惊寒",
    memory_type="preference",
    confidence=0.9,
    importance=0.8,
    entities=[
        {
            "slug": "慕云曦",
            "name": "慕云曦",
            "entity_type": "PERSON",
            "role": "subject",
            "confidence": 1.0
        },
        {
            "slug": "陆惊寒",
            "name": "陆惊寒",
            "entity_type": "PERSON",
            "role": "object",
            "confidence": 0.9
        }
    ],
    relations=[
        {
            "source": "慕云曦",
            "relation_type": RelationType.LIKES,
            "target": "陆惊寒",
            "description": "喜欢",
            "confidence": 1.0
        }
    ]
)

# 混合格式
memory = crud.create_memory(
    content="陆惊寒参与破阵营项目",
    entities=["破阵营"],
    relations=[
        "陆惊寒|WORKS_ON|破阵营",
        {
            "source": "陆惊寒",
            "rel": "WORKS_ON",  # 支持别名字段
            "to": "破阵营"
        }
    ]
)

# 搜索记忆（自动使用有效置信度排序）
results = crud.search_memories("陆惊寒喜欢谁", limit=5)

# 获取记忆（自动更新访问计数）
memory = crud.get_memory(memory_id)

# 获取实体对象列表
for entity in memory.get_entity_objects():
    print(f"{entity.name} ({entity.entity_type}): confidence={entity.confidence}")

# 获取关系对象列表
for relation in memory.get_relation_objects():
    print(f"{relation.source} -> {relation.relation_type} -> {relation.target}")
```

---

## 数据存储说明

### 数据库中的存储格式

为了兼容 LanceDB/PyArrow 的 schema 限制：

- **entities**: 存储为 `list[string]`
  - 简单字符串：直接存储
  - 对象格式：序列化为 JSON 字符串后存储在列表中

- **relations**: 存储为 `list[string]`
  - 简化格式 `"A|关系|B"`：直接存储
  - 对象格式：转换为简化格式后存储

### Python 代码中的使用

- `memory.entities` 返回原始数据（字符串或对象）
- `memory.relations` 返回原始数据（简化字符串或对象）
- `memory.get_entity_objects()` 返回 `List[EntityRef]` 对象列表
- `memory.get_relation_objects()` 返回 `List[RelationRef]` 对象列表

---

## 关系简化格式

### 格式规则

```
"源实体|关系类型|目标实体"
```

### 示例

```
"陆惊寒|LIKES|柳轻眉"
"慕云曦|KNOWS|陆惊寒"
"陆惊寒|WORKS_ON|破阵营"
"萧烬瑜|INVESTED_BY|摘星阁"
```

### 完整列表

```
认识:    "A|KNOWS|B"
喜欢:    "A|LIKES|B"
爱:      "A|LOVES|B"
恨:      "A|HATES|B"
共事:    "A|WORKS_WITH|B"
工作于:  "A|WORKS_AT|B"
相关:    "A|RELATED_TO|B"
位于:    "A|LOCATED_AT|B"
属于:    "A|PART_OF|B"
管理:    "A|MANAGES|B"
创建:    "A|CREATED|B"
提及:    "A|MENTIONS|B"
汇报给:  "A|REPORTS_TO|B"
参与:    "A|WORKS_ON|B"
被投资:  "A|INVESTED_BY|B"
友好:    "A|FRIENDS_WITH|B"
敌对:    "A|ENEMIES_WITH|B"
被管理:  "A|MANAGED_BY|B"
结婚:    "A|MARRIED_TO|B"
订婚:    "A|ENGAGED_TO|B"
曾婚:    "A|FORMERLY_MARRIED|B"
```
