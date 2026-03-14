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
