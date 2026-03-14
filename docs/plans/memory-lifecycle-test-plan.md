# Memory Bank - 记忆生命周期测试计划

> 测试文档：验证记忆生命周期设计的各项功能

## 测试目标

验证记忆生命周期的核心功能：
1. 置信度计算和时间衰减
2. 衰减率自动推断
3. 记忆更新策略（覆盖、合并、关联）
4. 矛盾检测和处理
5. 生命周期状态管理
6. importance 的三个作用（清理优先级、提炼优先级、保留阈值）

---

## 一、测试环境准备

### 1.1 测试数据集

```python
# 测试记忆样本
TEST_MEMORIES = [
    # 恒定信息（λ=0.0001）
    {"content": "2+2=4", "confidence": 0.95, "importance": 0.9},
    {"content": "我是Claude助手", "confidence": 1.0, "importance": 0.8},

    # 长期信息（λ=0.001）
    {"content": "我喜欢编程", "confidence": 0.9, "importance": 0.7},
    {"content": "我住在北京", "confidence": 0.8, "importance": 0.6},

    # 中期信息（λ=0.01）
    {"content": "我正在学习Python", "confidence": 0.8, "importance": 0.8},
    {"content": "项目名称是memory-bank", "confidence": 0.9, "importance": 0.9},

    # 短期信息（λ=0.05）
    {"content": "我打算明天开会", "confidence": 0.7, "importance": 0.5},
    {"content": "我正在写文档", "confidence": 0.8, "importance": 0.6},

    # 即时信息（λ=0.2）
    {"content": "我现在在喝咖啡", "confidence": 0.6, "importance": 0.3},
    {"content": "现在心情很好", "confidence": 0.7, "importance": 0.4},
]
```

### 1.2 测试工具

```python
# 测试工具函数
def create_memory(content, confidence=0.8, importance=0.5, decay_rate=None):
    """创建测试记忆"""
    if decay_rate is None:
        decay_rate = infer_decay_rate(content)

    return {
        "content": content,
        "confidence": confidence,
        "importance": importance,
        "decay_rate": decay_rate,
        "timestamp": datetime.now(),
        "id": str(uuid.uuid4())
    }

def get_effective_confidence(memory, days_ago=0):
    """计算有效置信度"""
    test_time = datetime.now() - timedelta(days=days_ago)
    actual_days = (test_time - memory["timestamp"]).days

    decay = math.exp(-memory["decay_rate"] * actual_days)
    return memory["confidence"] * decay
```

---

## 二、功能测试用例

### 2.1 置信度衰减测试

#### 测试场景1：不同衰减率的效果

```python
def test_confidence_decay():
    """测试不同衰减率下的置信度衰减"""

    # 创建不同衰减率的记忆
    memories = [
        create_memory("数学真理", 0.9, 0.8, 0.0001),  # 恒定
        create_memory("习惯", 0.8, 0.7, 0.001),     # 长期
        create_memory("项目状态", 0.8, 0.6, 0.01),    # 中期
        create_memory("计划", 0.7, 0.5, 0.05),       # 短期
        create_memory("情绪", 0.6, 0.3, 0.2),        # 即时
    ]

    # 测试不同时间点的有效置信度
    days_list = [0, 30, 90, 180, 365]

    for memory in memories:
        for days in days_list:
            effective = get_effective_confidence(memory, days)
            print(f"{memory['content']} (λ={memory['decay_rate']}) "
                  f"{days}天后有效置信度: {effective:.4f}")

    # 验证：恒定信息100天后衰减很小，即时信息衰减很大
    assert get_effective_confidence(memories[0], 100) > 0.89  # 几乎不变
    assert get_effective_confidence(memories[-1], 1) < 0.5     # 显著衰减
```

#### 测试场景2：置信度级别验证

```python
def test_confidence_levels():
    """验证不同置信度级别"""

    test_cases = [
        ("我爱吃苹果", 0.95),  # 用户明确陈述
        ("我好像喜欢编程", 0.75),  # 带不确定性词
        ("他可能是我朋友", 0.5),   # 从上下文推断
        ("我觉得这个方案不错", 0.3), # 猜测
        ("听说项目要延期", 0.15),  # 第三方信息
    ]

    for content, expected_confidence in test_cases:
        # 这里需要实现从内容推断置信度的逻辑
        actual_confidence = infer_confidence(content)  # 需要实现
        assert abs(actual_confidence - expected_confidence) < 0.1
```

### 2.2 衰减率推断测试

```python
def test_decay_rate_inference():
    """测试衰减率自动推断"""

    test_cases = [
        ("永远是正确的", 0.0001),  # 恒定词汇
        ("我相信这个方案", 0.001),  # 价值观相关
        ("我现在正在工作", 0.01),   # 中期状态
        ("我打算下周完成", 0.05),   # 短期计划
        ("我现在很忙", 0.2),       # 即时状态
        ("随便说的一句话", 0.01),   # 默认中期
    ]

    for content, expected_rate in test_cases:
        inferred_rate = infer_decay_rate(content)
        print(f"'{content}' -> 推断λ: {inferred_rate:.4f} (期望: {expected_rate:.4f})")
        assert inferred_rate == expected_rate
```

### 2.3 更新策略测试

#### 测试场景1：高相似度更新

```python
def test_high_similarity_update():
    """测试高相似度记忆更新"""

    old = create_memory("我正在学习Python", 0.8, 0.8)

    # 等待一天，然后收到相似信息
    old["timestamp"] = datetime.now() - timedelta(days=1)

    new = create_memory("我现在正在学习Python", 0.9, 0.8)

    similarity = calculate_similarity(old["content"], new["content"])
    assert similarity > 0.95  # 高相似度

    # 应该更新时间戳
    updated = update_memory(old, new)
    assert updated["timestamp"] > old["timestamp"]
    assert updated["confidence"] == 0.9  # 更新置信度
```

#### 测试场景2：矛盾检测

```python
def test_contradiction_detection():
    """测试矛盾信息处理"""

    old = create_memory("我喜欢吃苹果", 0.9, 0.7)

    # 等待100天，旧记忆衰减
    old["timestamp"] = datetime.now() - timedelta(days=100)
    old_effective = get_effective_confidence(old)

    new = create_memory("我不喜欢吃苹果", 0.8, 0.6)
    new_effective = new["confidence"]  # 新记忆无衰减

    action = handle_contradiction(old, new)

    if new_effective > old_effective + 0.15:
        assert action == "update"
    elif old_effective > new_effective + 0.15:
        assert action == "keep"
    else:
        assert action == "confirm"
```

### 2.4 生命周期测试

```python
def test_lifecycle_states():
    """测试生命周期状态流转"""

    memory = create_memory("测试记忆", 0.8, 0.5)

    # 初始状态
    assert memory["lifecycle_state"] == "ACTIVE"

    # 标记为归档
    archive_memory(memory)
    assert memory["lifecycle_state"] == "ARCHIVED"

    # 被新记忆取代
    new_memory = create_memory("更新的记忆", 0.9, 0.6)
    supersede_memory(memory, new_memory)
    assert memory["lifecycle_state"] == "SUPERSEDED"

    # 长期未访问，标记为遗忘
    memory["last_accessed_at"] = datetime.now() - timedelta(days=365)
    forget_memory(memory)
    assert memory["lifecycle_state"] == "FORGOTTEN"
```

### 2.5 Importance 作用测试

#### 测试场景1：清理优先级

```python
def test_cleanup_priority():
    """测试清理优先级计算"""

    # 高重要性、高有效置信度的记忆 - 清理优先级低
    important_memory = create_memory("重要知识", 0.9, 0.9, 0.001)
    important_memory["timestamp"] = datetime.now() - timedelta(days=10)
    priority1 = cleanup_priority(important_memory)

    # 低重要性、低有效置信度的记忆 - 清理优先级高
    unimportant_memory = create_memory("闲聊内容", 0.3, 0.1, 0.05)
    unimportant_memory["timestamp"] = datetime.now() - timedelta(days=100)
    priority2 = cleanup_priority(unimportant_memory)

    assert priority2 > priority1  # 低重要性记忆优先清理
```

#### 测试场景2：提炼优先级

```python
def test_distill_priority():
    """测试提炼优先级计算"""

    # 高访问次数的记忆 - 提炼优先级高
    frequent_memory = create_memory("常用知识", 0.8, 0.8, 0.01)
    frequent_memory["access_count"] = 100

    # 低访问次数的记忆 - 提炼优先级低
    rare_memory = create_memory("偶尔用到的", 0.7, 0.6, 0.01)
    rare_memory["access_count"] = 5

    priority1 = distill_priority(frequent_memory)
    priority2 = distill_priority(rare_memory)

    assert priority1 > priority2  # 高访问次数优先提炼
```

#### 测试场景3：保留阈值

```python
def test_retention_threshold():
    """测试记忆保留阈值"""

    # 重要且可信 - 应该保留
    important_good = create_memory("重要知识", 0.9, 0.9, 0.001)
    assert should_keep(important_good) == True

    # 不重要且不可信 - 应该清理
    unimportant_bad = create_memory("闲聊内容", 0.2, 0.1, 0.2)
    assert should_keep(unimportant_bad) == False

    # 中等情况 - 根据有效置信度判断
    medium = create_memory("中等记忆", 0.5, 0.4, 0.01)
    assert should_keep(medium) == True  # 有效置信度 > 0.1
```

---

## 三、集成测试

### 3.1 端到端场景测试

```python
def test_end_to_end_scenario():
    """端到端测试：用户偏好变化"""

    # 1. 用户最初喜欢咖啡
    coffee_preference = create_memory("我爱喝咖啡", 0.9, 0.6, 0.001)

    # 2. 一年后，用户表示不爱喝咖啡了
    coffee_preference["timestamp"] = datetime.now() - timedelta(days=365)
    coffee_effective = get_effective_confidence(coffee_preference)

    new_coffee = create_memory("我不爱喝咖啡了", 0.8, 0.6, 0.001)

    # 3. 处理矛盾
    action = handle_contradiction(coffee_preference, new_coffee)

    if action == "update":
        # 更新旧记忆，标记为历史偏好
        coffee_preference["lifecycle_state"] = "SUPERSEDED"
        coffee_preference["superseded_by"] = new_coffee["id"]
        new_coffee["lifecycle_state"] = "ACTIVE"
    elif action == "confirm":
        # 需要用户确认
        assert new_coffee["lifecycle_state"] == "NEEDS_CONFIRMATION"
```

### 3.2 性能测试

```python
def test_performance():
    """测试性能"""
    import time

    # 创建大量测试记忆
    memories = []
    for i in range(1000):
        content = f"测试记忆 {i}"
        memory = create_memory(content, 0.8, 0.5)
        memories.append(memory)

    # 测试衰减率推断性能
    start = time.time()
    for memory in memories:
        infer_decay_rate(memory["content"])
    infer_time = time.time() - start

    # 测试相似度计算性能
    start = time.time()
    for i, memory1 in enumerate(memories):
        for j, memory2 in enumerate(memories[i+1:], i+1):
            calculate_similarity(memory1["content"], memory2["content"])
    similarity_time = time.time() - start

    print(f"衰减率推断1000次耗时: {infer_time:.4f}s")
    print(f"相似度计算1000次耗时: {similarity_time:.4f}s")

    # 性能要求
    assert infer_time < 1.0  # 1000次 < 1秒
    assert similarity_time < 10.0  # 1000次 < 10秒
```

---

## 四、测试报告模板

### 4.1 单元测试报告

```python
class TestReport:
    def __init__(self):
        self.total_tests = 0
        self.passed_tests = 0
        self.failed_tests = 0
        self.details = []

    def add_test(self, name, passed, details=""):
        self.total_tests += 1
        if passed:
            self.passed_tests += 1
        else:
            self.failed_tests += 1
        self.details.append({
            "name": name,
            "passed": passed,
            "details": details
        })

    def print_report(self):
        print(f"\n测试报告:")
        print(f"总测试数: {self.total_tests}")
        print(f"通过: {self.passed_tests}")
        print(f"失败: {self.failed_tests}")
        print(f"通过率: {self.passed_tests/self.total_tests*100:.2f}%")

        if self.failed_tests > 0:
            print("\n失败测试详情:")
            for test in self.details:
                if not test["passed"]:
                    print(f"- {test['name']}: {test['details']}")
```

### 4.2 测试执行脚本

```python
def run_all_tests():
    """运行所有测试"""
    report = TestReport()

    # 运行各个测试
    test_functions = [
        test_confidence_decay,
        test_confidence_levels,
        test_decay_rate_inference,
        test_high_similarity_update,
        test_contradiction_detection,
        test_lifecycle_states,
        test_cleanup_priority,
        test_distill_priority,
        test_retention_threshold,
        test_end_to_end_scenario,
        test_performance
    ]

    for test_func in test_functions:
        try:
            test_func()
            report.add_test(test_func.__name__, True)
        except Exception as e:
            report.add_test(test_func.__name__, False, str(e))

    report.print_report()
    return report
```

---

## 五、测试数据验证

### 5.1 关键数据验证

```python
def validate_test_data():
    """验证测试数据的合理性"""

    # 验证衰减率
    assert 0.0001 <= 0.0001 <= 0.2  # 恒定
    assert 0.001 <= 0.001 <= 0.2   # 长期
    assert 0.01 <= 0.01 <= 0.2    # 中期
    assert 0.05 <= 0.05 <= 0.2    # 短期
    assert 0.2 <= 0.2 <= 0.2     # 即时

    # 验证置信度
    for memory in TEST_MEMORIES:
        assert 0 <= memory["confidence"] <= 1
        assert 0 <= memory["importance"] <= 1

    # 验证时间戳
    now = datetime.now()
    for memory in TEST_MEMORIES:
        assert memory["timestamp"] <= now
```

---

## 六、测试计划执行

### 6.1 执行步骤

1. **环境准备**
   - 初始化测试数据库
   - 加载测试数据集

2. **功能测试**
   - 按顺序执行各功能测试
   - 记录测试结果

3. **集成测试**
   - 执行端到端场景测试
   - 验证整体流程

4. **性能测试**
   - 执行性能基准测试
   - 检查是否达标

5. **生成报告**
   - 输出详细测试报告
   - 标记失败的测试

### 6.2 测试结果评估

```python
def evaluate_test_results(report):
    """评估测试结果"""

    success_rate = report.passed_tests / report.total_tests

    if success_rate >= 0.95:
        print("✅ 测试通过，系统稳定")
    elif success_rate >= 0.8:
        print("⚠️  测试基本通过，需要修复少量问题")
    else:
        print("❌ 测试失败较多，需要大量修复")

    return success_rate
```

---

## 七、测试用例扩展

### 7.1 边界情况测试

```python
def test_edge_cases():
    """测试边界情况"""

    # 空内容
    empty_memory = create_memory("", 0.5, 0.5)
    assert infer_decay_rate("") == 0.01  # 默认值

    # 极端置信度
    assert create_memory("测试", 0.0, 0.5)["confidence"] == 0.0
    assert create_memory("测试", 1.0, 0.5)["confidence"] == 1.0

    # 极端重要性
    assert create_memory("测试", 0.5, 0.0)["importance"] == 0.0
    assert create_memory("测试", 0.5, 1.0)["importance"] == 1.0

    # 远期时间
    old_memory = create_memory("旧记忆", 0.8, 0.6)
    old_memory["timestamp"] = datetime.now() - timedelta(days=365*10)  # 10年前
    assert get_effective_confidence(old_memory) < 0.01  # 基本遗忘
```

### 7.2 异常处理测试

```python
def test_error_handling():
    """测试异常处理"""

    # 无效输入
    try:
        infer_decay_rate(None)
        assert False, "应该抛出异常"
    except:
        pass

    # 类型错误
    try:
        handle_contradiction(None, None)
        assert False, "应该抛出异常"
    except:
        pass

    # 数据库错误
    try:
        # 模拟数据库连接失败
        raise ConnectionError("数据库连接失败")
    except ConnectionError as e:
        print(f"数据库错误处理: {e}")
```

---

*测试计划版本: 1.0*
*最后更新: 2026-03-13*
*创建者: 测试团队*