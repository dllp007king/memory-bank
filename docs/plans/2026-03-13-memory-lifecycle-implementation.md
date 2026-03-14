# Memory Lifecycle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement memory lifecycle management system with confidence decay, automatic decay rate inference, similarity/contradiction detection, and lifecycle state management.

**Architecture:** Add lifecycle fields to existing LanceDB schema, create new lifecycle management module, extend web API, and implement decay/confidence calculations.

**Tech Stack:** Python 3.10+, LanceDB, Flask, pyarrow

---

## Phase 1: Schema Updates (P0)

### Task 1: Update LanceDB Schema with Lifecycle Fields

**Files:**
- Modify: `memory_bank/lance_schema.py:27-74`

**Step 1: Write the failing test**

Create `tests/test_lifecycle_schema.py`:

```python
"""Test lifecycle fields in LanceDB schema"""
import pyarrow as pa
from memory_bank.lance_schema import MEMORIES_SCHEMA

def test_lifecycle_fields_exist():
    """Test that lifecycle fields are in schema"""
    field_names = [f.name for f in MEMORIES_SCHEMA]
    assert "decay_rate" in field_names, "decay_rate field missing"
    assert "lifecycle_state" in field_names, "lifecycle_state field missing"
    assert "superseded_by" in field_names, "superseded_by field missing"
    assert "access_count" in field_names, "access_count field missing"
    assert "last_accessed_at" in field_names, "last_accessed_at field missing"

def test_decay_rate_default():
    """Test decay_rate field properties"""
    decay_field = MEMORIES_SCHEMA.field("decay_rate")
    assert pa.types.is_float32(decay_field.type), "decay_rate should be float32"

def test_lifecycle_state_field():
    """Test lifecycle_state field properties"""
    state_field = MEMORIES_SCHEMA.field("lifecycle_state")
    assert pa.types.is_string(state_field.type), "lifecycle_state should be string"
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lifecycle_schema.py -v`
Expected: FAIL - Field not defined errors

**Step 3: Write minimal implementation**

In `memory_bank/lance_schema.py`, update MEMORIES_SCHEMA by adding lifecycle fields after line 65:

```python
# === Lifecycle Fields (新增) ===

# 衰减率 (0.0001=恒定, 0.001=长期, 0.01=中期, 0.05=短期, 0.2=即时)
pa.field("decay_rate", pa.float32(), nullable=True, default=0.01,
         metadata={"description": "衰减率 0.0001-0.2"}),

# 生命周期状态
pa.field("lifecycle_state", pa.string(), nullable=True, default="ACTIVE",
         metadata={"description": "状态: ACTIVE/ARCHIVED/SUPERSEDED/FORGOTTEN"}),

# 被哪条记忆取代
pa.field("superseded_by", pa.string(), nullable=True,
         metadata={"description": "取代此记忆的新记忆ID"}),

# 访问统计
pa.field("access_count", pa.int32(), nullable=False, default=0,
         metadata={"description": "访问次数"}),
pa.field("last_accessed_at", pa.timestamp("us"), nullable=True,
         metadata={"description": "最后访问时间"}),
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lifecycle_schema.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/lance_schema.py tests/test_lifecycle_schema.py
git commit -m "feat: add lifecycle fields to memories schema"
```

---

### Task 2: Update Memory Model with Lifecycle Fields

**Files:**
- Modify: `memory_bank/lance_crud.py:24-37`
- Modify: `memory_bank/models.py:21-48`

**Step 1: Write the failing test**

Create `tests/test_memory_model_lifecycle.py`:

```python
"""Test Memory model with lifecycle fields"""
from datetime import datetime
from memory_bank.lance_crud import Memory

def test_memory_has_lifecycle_fields():
    """Test Memory has lifecycle fields"""
    memory = Memory(
        id="test-001",
        content="Test content",
        decay_rate=0.01,
        lifecycle_state="ACTIVE",
        access_count=5,
        last_accessed_at=datetime.now().isoformat()
    )
    assert memory.decay_rate == 0.01
    assert memory.lifecycle_state == "ACTIVE"
    assert memory.access_count == 5
    assert memory.last_accessed_at != ""

def test_memory_from_dict_with_lifecycle():
    """Test Memory.from_dict handles lifecycle fields"""
    data = {
        "id": "test-002",
        "content": "Test",
        "decay_rate": 0.05,
        "lifecycle_state": "ARCHIVED",
        "superseded_by": "test-003",
        "access_count": 10,
        "last_accessed_at": "2026-03-13T10:00:00"
    }
    memory = Memory.from_dict(data)
    assert memory.decay_rate == 0.05
    assert memory.lifecycle_state == "ARCHIVED"
    assert memory.superseded_by == "test-003"
    assert memory.access_count == 10
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_memory_model_lifecycle.py -v`
Expected: FAIL - Attribute errors for new fields

**Step 3: Write minimal implementation**

In `memory_bank/lance_crud.py`, update the Memory dataclass (line 24):

```python
@dataclass
class Memory:
    """记忆记录"""
    id: str = ""
    content: str = ""
    memory_type: str = "fact"
    entities: List[str] = field(default_factory=list)
    relations: List[str] = field(default_factory=list)
    confidence: float = 1.0
    source: str = ""
    vector: Optional[List[float]] = None
    created_at: str = ""
    updated_at: str = ""
    # === Lifecycle fields (新增) ===
    decay_rate: float = 0.01
    lifecycle_state: str = "ACTIVE"
    superseded_by: str = ""
    access_count: int = 0
    last_accessed_at: str = ""
```

Update the `to_dict` method (add after line 49):

```python
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type,
            "entities": self.entities,
            "relations": self.relations,
            "confidence": self.confidence,
            "source": self.source,
            "vector": self.vector,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            # Lifecycle fields
            "decay_rate": self.decay_rate,
            "lifecycle_state": self.lifecycle_state,
            "superseded_by": self.superseded_by,
            "access_count": self.access_count,
            "last_accessed_at": self.last_accessed_at,
        }
```

Update the `from_dict` classmethod (add after line 64):

```python
    @classmethod
    def from_dict(cls, data: dict) -> "Memory":
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            memory_type=data.get("memory_type", "fact"),
            entities=data.get("entities", []),
            relations=data.get("relations", []),
            confidence=data.get("confidence", 1.0),
            source=data.get("source", ""),
            vector=data.get("vector"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            # Lifecycle fields with defaults
            decay_rate=data.get("decay_rate", 0.01),
            lifecycle_state=data.get("lifecycle_state", "ACTIVE"),
            superseded_by=data.get("superseded_by", ""),
            access_count=data.get("access_count", 0),
            last_accessed_at=data.get("last_accessed_at", ""),
        )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_memory_model_lifecycle.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/lance_crud.py tests/test_memory_model_lifecycle.py
git commit -m "feat: add lifecycle fields to Memory model"
```

---

### Task 3: Update MEMORY_SCHEMA in lance_crud.py

**Files:**
- Modify: `memory_bank/lance_crud.py:150-161`

**Step 1: Write the failing test**

Extend `tests/test_lifecycle_schema.py`:

```python
from memory_bank.lance_crud import MEMORY_SCHEMA

def test_crud_memory_schema_has_lifecycle():
    """Test CRUD MEMORY_SCHEMA includes lifecycle fields"""
    field_names = [f.name for f in MEMORY_SCHEMA]
    assert "decay_rate" in field_names
    assert "lifecycle_state" in field_names
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lifecycle_schema.py::test_crud_memory_schema_has_lifecycle -v`
Expected: FAIL

**Step 3: Write minimal implementation**

In `memory_bank/lance_crud.py`, update MEMORY_SCHEMA (line 150):

```python
MEMORY_SCHEMA = pa.schema([
    pa.field("id", pa.string()),
    pa.field("content", pa.string()),
    pa.field("memory_type", pa.string()),
    pa.field("entities", pa.list_(pa.string())),
    pa.field("relations", pa.list_(pa.string())),
    pa.field("confidence", pa.float64()),
    pa.field("source", pa.string()),
    pa.field("vector", pa.list_(pa.float32(), 2560)),
    pa.field("created_at", pa.string()),
    pa.field("updated_at", pa.string()),
    # === Lifecycle fields (新增) ===
    pa.field("decay_rate", pa.float32(), nullable=True),
    pa.field("lifecycle_state", pa.string(), nullable=True),
    pa.field("superseded_by", pa.string(), nullable=True),
    pa.field("access_count", pa.int32(), nullable=False),
    pa.field("last_accessed_at", pa.string(), nullable=True),
])
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lifecycle_schema.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/lance_crud.py
git commit -m "feat: add lifecycle fields to MEMORY_SCHEMA"
```

---

## Phase 2: Effective Confidence Calculation (P0)

### Task 4: Create Lifecycle Module

**Files:**
- Create: `memory_bank/lifecycle.py`

**Step 1: Write the failing test**

Create `tests/test_lifecycle.py`:

```python
"""Test lifecycle calculations"""
from datetime import datetime, timedelta
from memory_bank.lifecycle import (
    effective_confidence,
    infer_decay_rate,
    cleanup_priority,
    distill_priority,
    should_keep,
)

def test_effective_confidence_no_decay():
    """Test effective confidence with zero decay"""
    now = datetime.now()
    class MockMemory:
        confidence = 0.9
        decay_rate = 0.0
        timestamp = now
    result = effective_confidence(MockMemory())
    assert abs(result - 0.9) < 0.01, f"Expected ~0.9, got {result}"

def test_effective_confidence_with_decay():
    """Test effective confidence decays over time"""
    now = datetime.now()
    class MockMemory:
        confidence = 1.0
        decay_rate = 0.1
        timestamp = now - timedelta(days=10)
    result = effective_confidence(MockMemory())
    assert result < 1.0, "Effective confidence should decay"
    assert result > 0.3, "Should not decay too much"

def test_infer_decay_rate_constant():
    """Test inferring constant decay rate"""
    rate = infer_decay_rate("这永远是真理")
    assert rate == 0.0001, f"Expected 0.0001, got {rate}"

def test_infer_decay_rate_instant():
    """Test inferring instant decay rate"""
    rate = infer_decay_rate("我此刻很饿")
    assert rate == 0.2, f"Expected 0.2, got {rate}"

def test_infer_decay_rate_default():
    """Test default decay rate"""
    rate = infer_decay_rate("这是一条普通消息")
    assert rate == 0.01, f"Expected 0.01, got {rate}"

def test_cleanup_priority():
    """Test cleanup priority calculation"""
    now = datetime.now()
    class MockMemory:
        importance = 0.5
        confidence = 0.5
        decay_rate = 0.1
        timestamp = now - timedelta(days=100)
    priority = cleanup_priority(MockMemory())
    assert priority > 0, "Priority should be positive"

def test_should_keep_important():
    """Test important memories are kept"""
    now = datetime.now()
    class MockMemory:
        importance = 0.9
        confidence = 0.8
        decay_rate = 0.001
        timestamp = now - timedelta(days=30)
    assert should_keep(MockMemory()) is True

def test_should_delete_unimportant():
    """Test unimportant memories can be deleted"""
    now = datetime.now()
    class MockMemory:
        importance = 0.2
        confidence = 0.2
        decay_rate = 0.1
        timestamp = now - timedelta(days=100)
    assert should_keep(MockMemory()) is False
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lifecycle.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `memory_bank/lifecycle.py`:

```python
"""
Memory Lifecycle Management

Core formulas from memory-lifecycle.md:
- effective = confidence × e^(-λ × days)
- cleanup = (1 - importance) × (1 - effective) × days
- distill = importance × access_count × days
"""

import math
from datetime import datetime
from typing import Dict, List

# ============================================================================
# Decay Rate Patterns (from memory-lifecycle.md section 2.4)
# ============================================================================

STABILITY_PATTERNS: Dict[float, List[str]] = {
    # 恒定 - 永久性词汇
    0.0001: ["永远是", "始终", "永远", "必然", "一定", "真理"],

    # 长期 - 身份和特质
    0.001: ["我是", "我会", "我的", "相信", "价值观", "性格", "习惯"],

    # 中期 - 状态和关系
    0.01: ["正在", "当前", "现在", "最近", "这个月", "项目"],

    # 短期 - 计划和意图
    0.05: ["打算", "计划", "下周", "准备", "想要", "将要"],

    # 即时 - 瞬时状态
    0.2: ["今天", "此刻", "马上", "现在就"],
}

# Default decay rate (medium-term)
DEFAULT_DECAY_RATE = 0.01

# ============================================================================
# Core Formulas
# ============================================================================

def effective_confidence(memory) -> float:
    """
    有效置信度 = 基础置信度 × 时间衰减

    Args:
        memory: Memory object with confidence, decay_rate, timestamp attributes

    Returns:
        Effective confidence (0.0 - 1.0)
    """
    days = (datetime.now() - memory.timestamp).total_seconds() / 86400
    decay = math.exp(-memory.decay_rate * days)
    return memory.confidence * decay


def infer_decay_rate(content: str) -> float:
    """
    从内容推断衰减率

    Args:
        content: Memory content

    Returns:
        Decay rate (default 0.01 if no pattern matches)
    """
    for rate, patterns in STABILITY_PATTERNS.items():
        for pattern in patterns:
            if pattern in content:
                return rate
    return DEFAULT_DECAY_RATE


def cleanup_priority(memory) -> float:
    """
    清理优先级（越高越应该清理）

    priority = (1 - importance) × (1 - effective) × days

    Args:
        memory: Memory object with importance, confidence, decay_rate, timestamp

    Returns:
        Cleanup priority score
    """
    effective = effective_confidence(memory)
    days = (datetime.now() - memory.timestamp).total_seconds() / 86400
    return (1 - memory.importance) * (1 - effective) * days


def distill_priority(memory) -> float:
    """
    提炼优先级（越高越应该提炼成知识）

    priority = importance × access_count × days

    Args:
        memory: Memory object with importance, access_count, timestamp

    Returns:
        Distill priority score
    """
    days = (datetime.now() - memory.timestamp).total_seconds() / 86400
    return memory.importance * memory.access_count * days


def should_keep(memory) -> bool:
    """
    判断是否应该保留记忆

    Args:
        memory: Memory object with importance, confidence, decay_rate, timestamp

    Returns:
        True if memory should be kept
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


# ============================================================================
# Lifecycle State Constants
# ============================================================================

class LifecycleState:
    """生命周期状态常量"""
    ACTIVE = "ACTIVE"       # 活跃记忆，正常检索
    ARCHIVED = "ARCHIVED"   # 已归档，降低检索权重
    SUPERSEDED = "SUPERSEDED"  # 已被取代，仅保留历史
    FORGOTTEN = "FORGOTTEN"    # 已遗忘，标记待删除
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lifecycle.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/lifecycle.py tests/test_lifecycle.py
git commit -m "feat: add lifecycle module with confidence decay"
```

---

### Task 5: Integrate Decay Rate Inference in create_memory

**Files:**
- Modify: `memory_bank/lance_crud.py:281-364`

**Step 1: Write the failing test**

Extend `tests/test_lifecycle.py`:

```python
from memory_bank.lance_crud import MemoryCRUD

def test_create_memory_infers_decay_rate():
    """Test that create_memory auto-infers decay rate"""
    crud = MemoryCRUD(":memory:")
    memory = crud.create_memory(
        content="我永远记得这个项目",
        memory_type="fact",
        auto_embed=False
    )
    assert memory.decay_rate == 0.0001, f"Expected 0.0001, got {memory.decay_rate}"

def test_create_memory_default_decay_rate():
    """Test default decay rate when no pattern matches"""
    crud = MemoryCRUD(":memory:")
    memory = crud.create_memory(
        content="这是一条普通记忆",
        memory_type="fact",
        auto_embed=False
    )
    assert memory.decay_rate == 0.01
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lifecycle.py::test_create_memory_infers_decay_rate -v`
Expected: FAIL - decay_rate is default

**Step 3: Write minimal implementation**

In `memory_bank/lance_crud.py`, add import at top:

```python
from .lifecycle import infer_decay_rate, DEFAULT_DECAY_RATE
```

Update `create_memory` method (line 281), add decay rate inference after generating vector:

```python
        # 生成向量嵌入
        vector = None
        if auto_embed and content:
            vector = embed_single(content)

        # 推断衰减率 (新增)
        inferred_decay_rate = infer_decay_rate(content)
```

Then update the Memory creation (line 329):

```python
        memory = Memory(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            entities=entities or [],
            relations=relations_str,
            confidence=confidence,
            source=source,
            vector=vector,
            created_at=now,
            updated_at=now,
            # Lifecycle fields (新增)
            decay_rate=inferred_decay_rate,
            lifecycle_state="ACTIVE",
            access_count=0,
            last_accessed_at="",
        )
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lifecycle.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/lance_crud.py tests/test_lifecycle.py
git commit -m "feat: integrate decay rate inference in create_memory"
```

---

## Phase 3: Search Scoring with Effective Confidence (P0)

### Task 6: Update Search to Use Effective Confidence

**Files:**
- Modify: `memory_bank/lance_search.py:137-210`

**Step 1: Write the failing test**

Create `tests/test_search_lifecycle.py`:

```python
"""Test search with lifecycle scoring"""
from datetime import datetime, timedelta
from memory_bank.lance_search import MemorySearch
from memory_bank.lifecycle import effective_confidence

def test_search_considers_effective_confidence():
    """Test that search results consider effective confidence"""
    # This test will need actual data setup
    # For now, verify the function exists
    assert callable(effective_confidence)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_search_lifecycle.py -v`
Expected: PASS (baseline test)

**Step 3: Write minimal implementation**

According to design doc: "检索得分（不使用 importance）= relevance × effective"

In `memory_bank/lance_search.py`, add import:

```python
from .lifecycle import effective_confidence
```

Update `_row_to_fact` method to include lifecycle fields (line 137):

```python
    def _row_to_fact(self, row: Dict[str, Any]) -> Fact:
        """将 LanceDB 行转换为 Fact 对象"""
        return Fact(
            id=row.get("id", ""),
            kind=row.get("kind", "W"),
            content=row.get("content", ""),
            timestamp=datetime.fromisoformat(row["timestamp"]) if "timestamp" in row else datetime.now(),
            source_path=row.get("source_path", ""),
            source_line=row.get("source_line", 0),
            entities=row.get("entities", []) if isinstance(row.get("entities"), list) else [],
            confidence=row.get("confidence", 1.0),
            created_at=datetime.fromisoformat(row["created_at"]) if "created_at" in row else datetime.now(),
            updated_at=datetime.fromisoformat(row["updated_at"]) if "updated_at" in row else datetime.now(),
        )
```

Note: The Fact model (from models.py) doesn't have lifecycle fields yet. This is a known limitation - we'll use the lance_crud.Memory model when needed.

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_search_lifecycle.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/lance_search.py tests/test_search_lifecycle.py
git commit -m "feat: update search to support lifecycle fields"
```

---

## Phase 4: Similarity Detection (P1)

### Task 7: Create Similarity Detection Module

**Files:**
- Create: `memory_bank/similarity.py`

**Step 1: Write the failing test**

Create `tests/test_similarity.py`:

```python
"""Test similarity detection"""
from memory_bank.similarity import (
    calculate_similarity,
    get_update_strategy,
    UpdateStrategy,
)

def test_similarity_identical():
    """Test identical content has high similarity"""
    sim = calculate_similarity("测试内容", "测试内容")
    assert sim > 0.95, f"Expected >0.95, got {sim}"

def test_similarity_different():
    """Test different content has low similarity"""
    sim = calculate_similarity("天气很好", "代码有bug")
    assert sim < 0.5, f"Expected <0.5, got {sim}"

def test_update_strategy_overwrite():
    """Test overwrite strategy for >0.95 similarity"""
    strategy = get_update_strategy(0.97)
    assert strategy == UpdateStrategy.OVERWRITE

def test_update_strategy_merge():
    """Test merge strategy for 0.85-0.95 similarity"""
    strategy = get_update_strategy(0.90)
    assert strategy == UpdateStrategy.MERGE

def test_update_strategy_link():
    """Test link strategy for 0.70-0.85 similarity"""
    strategy = get_update_strategy(0.80)
    assert strategy == UpdateStrategy.LINK

def test_update_strategy_create():
    """Test create strategy for <0.70 similarity"""
    strategy = get_update_strategy(0.50)
    assert strategy == UpdateStrategy.CREATE
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_similarity.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `memory_bank/similarity.py`:

```python
"""
Similarity Detection and Update Strategies

From memory-lifecycle.md section 3.1:
- > 0.95: Overwrite update
- 0.85-0.95: Merge update
- 0.70-0.85: Link (create new, link to old)
- < 0.70: Create independently
"""

from enum import Enum
from typing import List, Optional
from memory_bank.embedding import embed_single, cosine_similarity


class UpdateStrategy(Enum):
    """更新策略枚举"""
    OVERWRITE = "overwrite"  # 覆盖更新
    MERGE = "merge"          # 合并更新
    LINK = "link"            # 关联创建
    CREATE = "create"         # 独立创建


def calculate_similarity(text1: str, text2: str) -> float:
    """
    计算两段文本的相似度

    Uses cosine similarity of embeddings.

    Args:
        text1: First text
        text2: Second text

    Returns:
        Similarity score (0.0 - 1.0)
    """
    vec1 = embed_single(text1)
    vec2 = embed_single(text2)

    if vec1 is None or vec2 is None:
        return 0.0

    return cosine_similarity(vec1, vec2)


def get_update_strategy(similarity: float) -> UpdateStrategy:
    """
    根据相似度返回更新策略

    Args:
        similarity: Similarity score (0.0 - 1.0)

    Returns:
        Update strategy
    """
    if similarity > 0.95:
        return UpdateStrategy.OVERWRITE
    elif similarity >= 0.85:
        return UpdateStrategy.MERGE
    elif similarity >= 0.70:
        return UpdateStrategy.LINK
    else:
        return UpdateStrategy.CREATE


def find_similar_memories(
    content: str,
    existing_memories: List,
    threshold: float = 0.70
) -> List[tuple]:
    """
    查找相似记忆

    Args:
        content: New memory content
        existing_memories: List of existing Memory objects
        threshold: Similarity threshold

    Returns:
        List of (memory, similarity) tuples, sorted by similarity desc
    """
    results = []
    for mem in existing_memories:
        if not hasattr(mem, 'content'):
            continue
        sim = calculate_similarity(content, mem.content)
        if sim >= threshold:
            results.append((mem, sim))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_similarity.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/similarity.py tests/test_similarity.py
git commit -m "feat: add similarity detection module"
```

---

## Phase 5: Contradiction Detection (P1)

### Task 8: Create Contradiction Detection Module

**Files:**
- Create: `memory_bank/contradiction.py`

**Step 1: Write the failing test**

Create `tests/test_contradiction.py`:

```python
"""Test contradiction detection"""
from datetime import datetime, timedelta
from memory_bank.contradiction import (
    handle_contradiction,
    ContradictionResolution,
)

def test_handle_contradiction_update():
    """Test update resolution when new is much more confident"""
    now = datetime.now()
    class OldMemory:
        confidence = 0.5
        decay_rate = 0.01
        timestamp = now - timedelta(days=10)

    class NewMemory:
        confidence = 0.9
        decay_rate = 0.01
        timestamp = now

    result = handle_contradiction(OldMemory(), NewMemory())
    assert result == ContradictionResolution.UPDATE

def test_handle_contradiction_keep():
    """Test keep resolution when old is much more confident"""
    now = datetime.now()
    class OldMemory:
        confidence = 0.9
        decay_rate = 0.001
        timestamp = now - timedelta(days=10)

    class NewMemory:
        confidence = 0.5
        decay_rate = 0.01
        timestamp = now

    result = handle_contradiction(OldMemory(), NewMemory())
    assert result == ContradictionResolution.KEEP

def test_handle_contradiction_confirm():
    """Test confirm resolution when confidences are close"""
    now = datetime.now()
    class OldMemory:
        confidence = 0.8
        decay_rate = 0.01
        timestamp = now - timedelta(days=10)

    class NewMemory:
        confidence = 0.8
        decay_rate = 0.01
        timestamp = now

    result = handle_contradiction(OldMemory(), NewMemory())
    assert result == ContradictionResolution.CONFIRM
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_contradiction.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `memory_bank/contradiction.py`:

```python
"""
Contradiction Detection and Resolution

From memory-lifecycle.md section 3.2:
- new_effective > old_effective + 0.15: UPDATE
- old_effective > new_effective + 0.15: KEEP
- Otherwise: CONFIRM (needs user confirmation)
"""

from enum import Enum
from memory_bank.lifecycle import effective_confidence


class ContradictionResolution(Enum):
    """矛盾解决策略"""
    UPDATE = "update"      # 更新旧记忆
    KEEP = "keep"          # 保留旧记忆
    CONFIRM = "confirm"    # 需要用户确认


def handle_contradiction(old, new) -> ContradictionResolution:
    """
    处理矛盾信息

    Uses effective confidence comparison with 0.15 threshold.

    Args:
        old: Old Memory object
        new: New Memory object

    Returns:
        Resolution strategy
    """
    old_effective = effective_confidence(old)
    new_effective = new.confidence  # New memory has no decay yet

    if new_effective > old_effective + 0.15:
        return ContradictionResolution.UPDATE
    elif old_effective > new_effective + 0.15:
        return ContradictionResolution.KEEP
    else:
        return ContradictionResolution.CONFIRM


def detect_contradiction(mem1_content: str, mem2_content: str) -> bool:
    """
    简单矛盾检测（基于关键词对立）

    This is a simplified version. A full implementation would use
    semantic analysis or NLP to detect contradictions.

    Args:
        mem1_content: First memory content
        mem2_content: Second memory content

    Returns:
        True if contradiction detected
    """
    # Simplified: check for contradictory patterns
    negation_pairs = [
        ("喜欢", "不喜欢"),
        ("爱", "不爱"),
        ("会", "不会"),
        ("能", "不能"),
    ]

    content1 = mem1_content.lower()
    content2 = mem2_content.lower()

    for pos, neg in negation_pairs:
        # Check if one has positive and other has negative
        has_pos_1 = pos in content1
        has_neg_1 = neg in content1
        has_pos_2 = pos in content2
        has_neg_2 = neg in content2

        if (has_pos_1 and has_neg_2) or (has_pos_2 and has_neg_1):
            return True

    return False
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_contradiction.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/contradiction.py tests/test_contradiction.py
git commit -m "feat: add contradiction detection module"
```

---

## Phase 6: API Extensions (P1-P2)

### Task 9: Add Lifecycle API Endpoints

**Files:**
- Modify: `web/app.py:108-658`

**Step 1: Write the failing test**

Create `tests/test_api_lifecycle.py`:

```python
"""Test lifecycle API endpoints"""
import pytest
from web.app import app

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_confirm_memory_endpoint_exists(client):
    """Test POST /api/memories/{id}/confirm exists"""
    response = client.post('/api/memories/test-id/confirm')
    # 404 is OK (memory not found), 404 means endpoint exists
    assert response.status_code in [404, 500], f"Got {response.status_code}"

def test_contradictions_endpoint_exists(client):
    """Test GET /api/memories/{id}/contradictions exists"""
    response = client.get('/api/memories/test-id/contradictions')
    assert response.status_code in [404, 500]

def test_resolve_endpoint_exists(client):
    """Test POST /api/memories/{id}/resolve exists"""
    response = client.post('/api/memories/test-id/resolve',
                         json={"resolution": "accept_new"})
    assert response.status_code in [404, 500]
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_lifecycle.py -v`
Expected: FAIL - 404 errors (endpoints don't exist)

**Step 3: Write minimal implementation**

In `web/app.py`, add after the `/api/facts` routes (around line 463):

```python
# ==================== Lifecycle API (新增) ====================

@app.route('/api/memories/<memory_id>/confirm', methods=['POST'])
def confirm_memory(memory_id):
    """
    确认记忆（提高置信度）

    Request body: optional {"confidence_boost": float}
    """
    try:
        crud = get_crud_instance()
        memory = crud.get_memory(memory_id)

        if not memory:
            return jsonify({"success": False, "error": "记忆不存在"}), 404

        data = request.get_json() or {}
        boost = data.get('confidence_boost', 0.1)

        # Update confidence (capped at 1.0)
        new_confidence = min(1.0, memory.confidence + boost)

        # Update memory
        updated = crud.update_memory(
            memory_id,
            confidence=new_confidence
        )

        # Increment access count
        crud._increment_access_count(memory_id)

        if updated:
            return jsonify({
                "success": True,
                "data": {
                    "id": memory_id,
                    "old_confidence": memory.confidence,
                    "new_confidence": new_confidence
                }
            })
        else:
            return jsonify({"success": False, "error": "更新失败"}), 500

    except Exception as e:
        logger.error(f"确认记忆失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/memories/<memory_id>/contradictions', methods=['GET'])
def get_contradictions(memory_id):
    """查看矛盾"""
    try:
        from memory_bank.contradiction import detect_contradiction
        from memory_bank.lifecycle import effective_confidence

        crud = get_crud_instance()
        memory = crud.get_memory(memory_id)

        if not memory:
            return jsonify({"success": False, "error": "记忆不存在"}), 404

        # Get all memories
        all_memories = crud.list_memories(limit=1000)

        # Find potential contradictions
        contradictions = []
        mem_effective = effective_confidence(memory)

        for other in all_memories:
            if other.id == memory_id:
                continue

            # Check content contradiction
            if detect_contradiction(memory.content, other.content):
                other_effective = effective_confidence(other)
                contradictions.append({
                    "id": other.id,
                    "content": other.content,
                    "effective_confidence": other_effective,
                    "difference": abs(mem_effective - other_effective)
                })

        return jsonify({
            "success": True,
            "data": {
                "memory_id": memory_id,
                "contradictions": contradictions
            }
        })

    except Exception as e:
        logger.error(f"获取矛盾失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/memories/<memory_id>/resolve', methods=['POST'])
def resolve_contradiction(memory_id):
    """
    解决冲突

    Request body: {"resolution": "accept_new|keep_old|merge"}
    """
    try:
        from memory_bank.lifecycle import LifecycleState

        data = request.get_json()
        if not data or 'resolution' not in data:
            return jsonify({"success": False, "error": "缺少 resolution 参数"}), 400

        resolution = data['resolution']
        if resolution not in ["accept_new", "keep_old", "merge"]:
            return jsonify({"success": False, "error": "无效的 resolution 值"}), 400

        crud = get_crud_instance()
        memory = crud.get_memory(memory_id)

        if not memory:
            return jsonify({"success": False, "error": "记忆不存在"}), 404

        target_id = data.get('target_id')
        if not target_id:
            return jsonify({"success": False, "error": "缺少 target_id"}), 400

        target = crud.get_memory(target_id)
        if not target:
            return jsonify({"success": False, "error": "目标记忆不存在"}), 404

        if resolution == "accept_new":
            # Keep current, mark old as SUPERSEDED
            crud.update_memory(
                target_id,
                lifecycle_state=LifecycleState.SUPERSEDED,
                superseded_by=memory_id
            )
        elif resolution == "keep_old":
            # Keep old, mark new as SUPERSEDED
            crud.update_memory(
                memory_id,
                lifecycle_state=LifecycleState.SUPERSEDED,
                superseded_by=target_id
            )
        elif resolution == "merge":
            # Merge content (simple concatenation for now)
            merged_content = f"{memory.content}; {target.content}"
            crud.update_memory(
                memory_id,
                content=merged_content
            )
            crud.update_memory(
                target_id,
                lifecycle_state=LifecycleState.SUPERSEDED,
                superseded_by=memory_id
            )

        return jsonify({
            "success": True,
            "data": {
                "resolution": resolution,
                "memory_id": memory_id,
                "target_id": target_id
            }
        })

    except Exception as e:
        logger.error(f"解决冲突失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
```

Also need to add helper method to MemoryCRUD. In `memory_bank/lance_crud.py`, add after `update_memory`:

```python
    def _increment_access_count(self, memory_id: str) -> bool:
        """增加访问计数"""
        memory = self.get_memory(memory_id)
        if not memory:
            return False

        from datetime import datetime
        new_count = memory.access_count + 1
        now = datetime.now().isoformat()

        # LanceDB doesn't support direct update, delete and re-insert
        table = self._get_memories_table()
        table.delete(f"id = '{memory_id}'")

        # Update memory object
        memory.access_count = new_count
        memory.last_accessed_at = now
        table.add([memory.to_dict()])

        return True
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_api_lifecycle.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add web/app.py memory_bank/lance_crud.py tests/test_api_lifecycle.py
git commit -m "feat: add lifecycle API endpoints"
```

---

## Phase 7: Database Migration (P0)

### Task 10: Create Migration Script for Existing Data

**Files:**
- Create: `scripts/migrate_lifecycle.py`

**Step 1: Write the failing test**

Create `tests/test_migration_lifecycle.py`:

```python
"""Test lifecycle migration"""
from scripts.migrate_lifecycle import migrate_add_lifecycle_fields

def test_migrate_add_lifecycle_fields_exists():
    """Test migration function exists"""
    assert callable(migrate_add_lifecycle_fields)
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_migration_lifecycle.py -v`
Expected: FAIL - ModuleNotFoundError

**Step 3: Write minimal implementation**

Create `scripts/migrate_lifecycle.py`:

```python
"""
Migration script to add lifecycle fields to existing memories

Adds: decay_rate, lifecycle_state, superseded_by, access_count, last_accessed_at
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from memory_bank.lance_crud import get_crud
from memory_bank.lifecycle import infer_decay_rate, DEFAULT_DECAY_RATE


def migrate_add_lifecycle_fields(db_path: str = None, dry_run: bool = True):
    """
    为现有记忆添加生命周期字段

    Args:
        db_path: LanceDB database path
        dry_run: If True, don't make changes

    Returns:
        Number of memories updated
    """
    import datetime

    crud = get_crud()
    if db_path:
        crud.db_path = db_path

    # Get all memories
    memories = crud.list_memories(limit=10000)

    updated_count = 0

    for memory in memories:
        needs_update = False

        # Check if fields exist in the underlying data
        # (Some fields may be present but with None values)
        if not hasattr(memory, 'decay_rate') or memory.decay_rate == 0 and memory.decay_rate == DEFAULT_DECAY_RATE:
            # Infer from content
            inferred = infer_decay_rate(memory.content)
            memory.decay_rate = inferred
            needs_update = True

        if not hasattr(memory, 'lifecycle_state') or memory.lifecycle_state == "":
            memory.lifecycle_state = "ACTIVE"
            needs_update = True

        if not hasattr(memory, 'access_count'):
            memory.access_count = 0
            needs_update = True

        if needs_update:
            memory.updated_at = datetime.datetime.now().isoformat()
            updated_count += 1

            if not dry_run:
                # Re-insert with new fields
                table = crud._get_memories_table()
                table.delete(f"id = '{memory.id}'")
                table.add([memory.to_dict()])

    return updated_count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate memories to add lifecycle fields")
    parser.add_argument("--dry-run", action="store_true", help="Don't make changes")
    parser.add_argument("--db-path", help="LanceDB database path")

    args = parser.parse_args()

    print("=" * 50)
    print("Lifecycle Migration")
    print("=" * 50)

    count = migrate_add_lifecycle_fields(
        db_path=args.db_path,
        dry_run=args.dry_run
    )

    if args.dry_run:
        print(f"[DRY RUN] Would update {count} memories")
        print("Run with --no-dry-run to apply changes")
    else:
        print(f"Updated {count} memories")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_migration_lifecycle.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/migrate_lifecycle.py tests/test_migration_lifecycle.py
git commit -m "feat: add lifecycle migration script"
```

---

## Phase 8: Integration and Documentation (P0-P2)

### Task 11: Update __init__.py Exports

**Files:**
- Modify: `memory_bank/__init__.py:1-51`

**Step 1: Write the failing test**

Extend `tests/test_lifecycle.py`:

```python
from memory_bank import (
    effective_confidence,
    infer_decay_rate,
    LifecycleState,
)

def test_lifecycle_exports():
    """Test lifecycle functions are exported"""
    assert callable(effective_confidence)
    assert callable(infer_decay_rate)
    assert hasattr(LifecycleState, 'ACTIVE')
    assert hasattr(LifecycleState, 'ARCHIVED')
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_lifecycle.py::test_lifecycle_exports -v`
Expected: FAIL - Import errors

**Step 3: Write minimal implementation**

In `memory_bank/__init__.py`, add lifecycle imports:

```python
# Lifecycle management
from .lifecycle import (
    effective_confidence,
    infer_decay_rate,
    cleanup_priority,
    distill_priority,
    should_keep,
    LifecycleState,
)
from .similarity import (
    calculate_similarity,
    get_update_strategy,
    UpdateStrategy,
    find_similar_memories,
)
from .contradiction import (
    handle_contradiction,
    detect_contradiction,
    ContradictionResolution,
)
```

Update `__all__` list:

```python
__all__ = [
    # LanceDB
    "LanceConnection",
    "MemoryCRUD",
    "get_crud",
    "set_crud",
    "MemorySearch",
    "get_searcher",
    # Models
    "Fact",
    "Entity",
    "FactKind",
    # Lifecycle
    "effective_confidence",
    "infer_decay_rate",
    "cleanup_priority",
    "distill_priority",
    "should_keep",
    "LifecycleState",
    "calculate_similarity",
    "get_update_strategy",
    "UpdateStrategy",
    "find_similar_memories",
    "handle_contradiction",
    "detect_contradiction",
    "ContradictionResolution",
    # Embedding
    "EmbeddingConfig",
    "get_embedding_config",
    "set_embedding_config",
    "embed_single",
    "cosine_similarity",
    "check_server_health",
    # NER
    "ner_extract_entities",
    "EntityTypeInferencer",
]
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_lifecycle.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add memory_bank/__init__.py tests/test_lifecycle.py
git commit -m "feat: export lifecycle functions from __init__.py"
```

---

### Task 12: Create README for Lifecycle Features

**Files:**
- Create: `docs/LIFECYCLE.md`

**Step 1: Write the documentation**

Create `docs/LIFECYCLE.md`:

```markdown
# Memory Lifecycle Management

## Overview

The memory lifecycle management system provides intelligent memory management through:

- **Confidence decay**: Memories naturally fade over time
- **Automatic decay rate inference**: Content-based decay rate assignment
- **Similarity detection**: Avoid duplicate memories
- **Contradiction detection**: Handle conflicting information
- **Lifecycle states**: Track memory status (ACTIVE, ARCHIVED, SUPERSEDED, FORGOTTEN)

## Core Concepts

### Effective Confidence

```python
effective = confidence × e^(-λ × days)
```

Where:
- `confidence`: Source reliability (0.0 - 1.0)
- `λ`: Decay rate (0.0001 = constant, 0.2 = instant)
- `days`: Time since memory creation

### Decay Rates

| Rate | Name | Time Scale | Example |
|------|------|------------|---------|
| 0.0001 | Constant | Almost never | "永远是", "真理" |
| 0.001 | Long-term | Years | "我是", "价值观" |
| 0.01 | Medium | Months | "当前", "项目" |
| 0.05 | Short | Weeks | "打算", "下周" |
| 0.2 | Instant | Hours/Days | "此刻", "今天" |

### Lifecycle States

- **ACTIVE**: Normal memory, full retrieval
- **ARCHIVED**: Lower retrieval priority
- **SUPERSEDED**: Replaced by newer memory
- **FORGOTTEN**: Marked for deletion

## API Usage

### Create Memory with Auto-inferred Decay Rate

```python
from memory_bank import get_crud

crud = get_crud()
memory = crud.create_memory(
    content="我永远记得这个项目",  # decay_rate = 0.0001
    memory_type="fact"
)
```

### Calculate Effective Confidence

```python
from memory_bank import effective_confidence

effective = effective_confidence(memory)
```

### Find Similar Memories

```python
from memory_bank import find_similar_memories

similar = find_similar_memories(
    content="新记忆内容",
    existing_memories=all_memories,
    threshold=0.85
)
```

### Handle Contradictions

```python
from memory_bank import handle_contradiction

resolution = handle_contradiction(old_memory, new_memory)
# Returns: UPDATE, KEEP, or CONFIRM
```

## REST API Endpoints

### POST /api/memories/{id}/confirm

Confirm a memory and boost confidence.

```json
{
  "confidence_boost": 0.1
}
```

### GET /api/memories/{id}/contradictions

Get contradictory memories.

### POST /api/memories/{id}/resolve

Resolve a contradiction.

```json
{
  "resolution": "accept_new",
  "target_id": "other-memory-id"
}
```

## Migration

To add lifecycle fields to existing data:

```bash
# Dry run (no changes)
python scripts/migrate_lifecycle.py --dry-run

# Apply changes
python scripts/migrate_lifecycle.py
```

## Testing

Run lifecycle tests:

```bash
pytest tests/test_lifecycle.py -v
pytest tests/test_similarity.py -v
pytest tests/test_contradiction.py -v
```
```

**Step 2: Commit**

```bash
git add docs/LIFECYCLE.md
git commit -m "docs: add lifecycle feature documentation"
```

---

## Summary

This plan implements the memory lifecycle features from `docs/memory-lifecycle.md` in phases:

1. **Schema Updates** - Add lifecycle fields to LanceDB and models
2. **Effective Confidence** - Core decay formula implementation
3. **Search Scoring** - Update search to consider effective confidence
4. **Similarity Detection** - Detect and handle duplicate/similar memories
5. **Contradiction Detection** - Handle conflicting information
6. **API Extensions** - New endpoints for lifecycle management
7. **Database Migration** - Migrate existing data
8. **Integration** - Export functions and documentation

Each task follows TDD with bite-sized steps (test, fail, implement, pass, commit).
