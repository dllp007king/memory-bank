# Embedding 模块集成说明

## 概述

已成功集成 50 并发限制的嵌入客户端到 `memory_bank/embedding.py` 模块。

## 新增功能

### 1. get_embed_client() 函数

获取全局并发嵌入客户端（单例模式）：

```python
from memory_bank.embedding import get_embed_client

# 获取客户端（默认 50 并发）
client = get_embed_client()

# 自定义配置
client = get_embed_client(
    base_url="http://localhost:8080/v1/embeddings",
    max_concurrent=50,
    timeout=60
)

# 使用客户端
embedding = client.embed("测试文本")
embeddings = client.embed_batch(["文本1", "文本2", "文本3"])
```

### 2. embed() 函数增强

新增 `use_concurrent` 参数：

```python
from memory_bank.embedding import embed

# 使用并发客户端（50 并发限制）
embeddings = embed(texts, use_concurrent=True)

# 传统方式（服务器/CLI）
embeddings = embed(texts, use_concurrent=False)
```

### 3. embed_batch() 函数（推荐）

批量嵌入，默认使用并发客户端：

```python
from memory_bank.embedding import embed_batch

# 批量嵌入（自动使用 50 并发限制）
embeddings = embed_batch(["文本1", "文本2", ..., "文本100"])

# 单个失败不影响其他
for i, emb in enumerate(embeddings):
    if emb is None:
        print(f"文本 {i} 嵌入失败")
    else:
        print(f"文本 {i} 嵌入成功，维度: {len(emb)}")
```

### 4. EmbeddingManager 类增强

支持并发模式：

```python
from memory_bank.embedding import EmbeddingManager

# 创建管理器（默认使用并发）
manager = EmbeddingManager(use_concurrent=True)

# 批量嵌入（自动缓存 + 并发限制）
embeddings = manager.embed_batch(texts)

# 获取统计信息
stats = manager.get_stats()
print(stats)
# 输出: {'total_requests': 100, 'success': 98, 'failed': 2, 'rejected': 0}
```

## 核心特性

### 50 并发限制

- **自动排队**：超过 50 并发时，新请求自动排队等待
- **线程安全**：使用信号量（Semaphore）控制并发
- **超时保护**：等待超时后抛出 `TimeoutError`

```python
# 示例：100 个请求会自动排队
texts = [f"文本 {i}" for i in range(100)]
embeddings = embed_batch(texts)  # 不会超过 50 并发
```

### 接口兼容性

所有旧接口仍然可用：

```python
# 旧接口（完全兼容）
from memory_bank.embedding import (
    get_config,
    set_config,
    EmbeddingConfig,
    check_server_health,
    embed_single,
    cosine_similarity,
    vector_to_blob,
    blob_to_vector,
)

# 新接口
from memory_bank.embedding import (
    get_embed_client,    # 新增
    embed_batch,         # 新增
    get_stats,           # 新增
)
```

## 统计信息

查看并发客户端统计：

```python
from memory_bank.embedding import get_stats

stats = get_stats()
print(stats)
# {
#     'total_requests': 150,
#     'success': 148,
#     'failed': 2,
#     'rejected': 0
# }
```

## 使用建议

1. **批量操作**：优先使用 `embed_batch()` 而不是循环调用 `embed()`
2. **管理器模式**：使用 `EmbeddingManager` 获得缓存优化
3. **监控统计**：定期检查 `get_stats()` 了解服务状态

## 文件位置

- 主模块：`memory-bank/memory_bank/embedding.py`
- 并发客户端：`memory-bank/embedding/concurrent_client.py`
- 测试脚本：`memory-bank/test_embedding_integration.py`

## 代码规范

- ✓ 添加中文注释
- ✓ 确保 50 并发限制生效
- ✓ 保持接口兼容
- ✓ 线程安全实现
