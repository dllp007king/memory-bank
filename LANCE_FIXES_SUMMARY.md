# LanceDB 代码修复总结

## 修复的问题

### 1. Schema 定义问题
**问题**：原代码使用 `lancedb.vector()` 定义向量列，但该函数返回的不是 `pa.Field` 类型，导致错误。

**修复**：
- 将向量列定义为固定大小的列表类型：`pa.list_(pa.float32(), list_size=2560)`
- 向量维度设置为 2560（与 Qwen3-Embedding-4B 模型一致）

**修复文件**：`memory-bank/memory_bank/lance_crud.py`

```python
# 修复前
pa.field("vector", pa.list_(pa.float32()))

# 修复后
pa.field("vector", pa.list_(pa.float32(), list_size=2560))
```

### 2. 向量搜索问题
**问题**：原代码使用 `table.search().vector("vector")` 进行向量搜索，这不是 LanceDB 的正确用法。

**修复**：
- 使用 `table.search(query_vector)` 进行向量搜索
- LanceDB 会自动识别向量列并执行向量搜索

**修复文件**：
- `memory-bank/memory_bank/lance_crud.py` - `search_memories()` 方法
- `memory-bank/memory_bank/lance_search.py` - `vector_search()` 方法

```python
# 修复前
results = table.search().vector("vector").limit(limit).to_list()

# 修复后
results = table.search(query_vector).limit(limit).to_list()
```

### 3. 对象访问问题
**问题**：
1. `to_list()` 返回的是列表，不是 DataFrame，所以不能使用 `.empty` 属性
2. `resultresults[0]` 拼写错误，应该是 `result[0]`
3. 列表元素已经是字典，不需要额外的 `.to_dict()` 调用

**修复**：
- 使用 `if not result:` 检查空列表
- 使用 `result[0]` 直接访问列表元素
- 直接使用字典，不需要转换

**修复文件**：`memory-bank/memory_bank/lance_crud.py`

```python
# 修复前
if result.empty:
    return None
return Memory.from_dict(resultresults[0])

# 修复后
if not result:
    return None
return Memory.from_dict(result[0])
```

### 4. 导入问题
**问题**：`lance_search.py` 中错误地导入了 `lance` 而不是 `lancedb`。

**修复**：将所有 `lance` 导入改为 `lancedb`

**修复文件**：`memory-bank/memory_bank/lance_search.py`

```python
# 修复前
import lance
db = lance.connect(config.db_path)

# 修复后
import lancedb
db = lancedb.connect(config.db_path)
```

### 5. 过滤方法问题
**问题**：`LanceEmptyQueryBuilder` 对象没有 `filter` 属性。

**修复**：使用 `.where()` 方法代替 `.filter()` 进行过滤

**修复文件**：`memory-bank/memory_bank/lance_search.py`

```python
# 修复前
results = self.table.search().filter(filter_str).limit(limit).to_list()

# 修复后
results = self.table.search().where(filter_str).limit(limit).to_list()
```

## 测试验证

所有修复已通过以下测试：

1. ✅ 模块导入测试
2. ✅ Schema 定义验证（固定大小向量列：2560 维）
3. ✅ CRUD 操作测试（创建、获取、列出、更新、删除）
4. ✅ 向量搜索测试
5. ✅ 对象访问方式验证（to_list() 返回字典列表）

## 注意事项

1. **全文搜索（FTS）**：需要创建 INVERTED 索引才能使用，否则会报错。当前代码已处理该异常。
2. **向量维度**：Schema 中的向量维度必须与嵌入模型输出一致（当前为 2560 维）。
3. **LanceDB API**：
   - 使用 `.search(query_vector)` 进行向量搜索
   - 使用 `.where(condition)` 进行过滤
   - `.to_list()` 返回字典列表，不是 DataFrame

## 修改的文件

1. `memory-bank/memory_bank/lance_crud.py` - CRUD 操作和 Schema 定义
2. `memory-bank/memory_bank/lance_search.py` - 搜索功能

## 测试脚本

- `memory-bank/test_lance_fixes.py` - CRUD 功能测试
- `memory-bank/test_lance_search.py` - 搜索功能测试
- `memory-bank/verify_lance_fixes.py` - 完整验证脚本
