"""
大模型 NER 核心逻辑

提供 NER 提示词生成、结果解析、模型降级逻辑。
实际的子代理调用由外部负责（通过 HTTP 调用 Gateway API）。
"""

import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


# NER 子代理任务模板（简化版，强调格式）
NER_PROMPT = """【实体提取任务】

从以下文本提取所有有意义的实体。

文本：
\"\"\"
{content}
\"\"\"

实体类型：
- PERSON: 人物
- ORGANIZATION: 公司、机构、团队
- TOOL: 工具、软件、平台
- PROJECT: 项目、产品
- CONCEPT: 概念、技术、理论
- GAME: 游戏、游戏内元素
- PLACE: 地点、区域
- EVENT: 事件、活动
- SYSTEM: 系统、框架

⚠️ 必须严格按以下 JSON 格式返回，不要有其他文字：

{{"entities": [{{"name": "实体名", "type": "PERSON"}}]}}

只返回 JSON："""


# NER 配置
NER_CONFIG = {
    "max_concurrent": 2,              # 最大并发子代理数
    "batch_size": 10,                 # 每批处理条数
    "batch_interval": 2,              # 批次间隔（秒）
    "timeout_seconds": 30,            # 单次 NER 超时
    "max_retries": 2,                 # 最大重试次数
    "models": [                       # 模型优先级
        "omega/minimax-m2.5",
        "omega/glm-4.7",
    ],
}


def generate_ner_prompt(content: str) -> str:
    """
    生成 NER 提示词
    
    Args:
        content: 待提取实体的文本
        
    Returns:
        完整的提示词
    """
    return NER_PROMPT.format(content=content)


def parse_entities(result: str) -> List[Dict[str, str]]:
    """
    解析 NER 结果
    
    Args:
        result: 子代理返回的 JSON 字符串
        
    Returns:
        实体列表，格式：[{"name": "xxx", "type": "PERSON"}, ...]
    """
    try:
        # 尝试提取 JSON（可能包含额外的文本）
        result = result.strip()
        
        # 查找 JSON 块
        start_idx = result.find('{')
        if start_idx == -1:
            logger.warning("No JSON found in result")
            return []
        
        # 从第一个 { 开始解析
        json_str = result[start_idx:]
        
        # 尝试找到匹配的 }
        brace_count = 0
        end_idx = -1
        for i, char in enumerate(json_str):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i + 1
                    break
        
        if end_idx == -1:
            logger.warning("No matching closing brace found")
            return []
        
        json_str = json_str[:end_idx]
        data = json.loads(json_str)
        
        # 提取实体列表
        entities = data.get('entities', [])
        
        # 验证格式
        valid_entities = []
        for entity in entities:
            if isinstance(entity, dict) and 'name' in entity and 'type' in entity:
                valid_entities.append({
                    'name': entity['name'],
                    'type': entity['type']
                })
        
        logger.info(f"Parsed {len(valid_entities)} entities from result")
        return valid_entities
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error parsing entities: {e}")
        return []


def get_next_model(current_model: str) -> Optional[str]:
    """
    获取下一个备选模型（Fallback 逻辑）
    
    Args:
        current_model: 当前失败的模型
        
    Returns:
        下一个备选模型，如果没有则返回 None
    """
    models = NER_CONFIG['models']
    
    try:
        current_idx = models.index(current_model)
        if current_idx < len(models) - 1:
            return models[current_idx + 1]
    except ValueError:
        pass
    
    return None


def validate_entity_type(entity_type: str) -> bool:
    """
    验证实体类型是否有效
    
    Args:
        entity_type: 实体类型
        
    Returns:
        是否有效
    """
    valid_types = {
        'PERSON', 'ORGANIZATION', 'TOOL', 'PROJECT',
        'CONCEPT', 'GAME', 'PLACE', 'EVENT', 'SYSTEM'
    }
    return entity_type.upper() in valid_types


def normalize_entity_type(entity_type: str) -> str:
    """
    规范化实体类型（转为大写）
    
    Args:
        entity_type: 实体类型
        
    Returns:
        规范化后的类型
    """
    return entity_type.upper()


def create_ner_task(fact_id: str, content: str) -> Dict[str, Any]:
    """
    创建 NER 任务描述（用于传递给外部调用者）
    
    Args:
        fact_id: 事实 ID
        content: 待处理的内容
        
    Returns:
        任务描述字典
    """
    return {
        'fact_id': fact_id,
        'content': content,
        'prompt': generate_ner_prompt(content),
        'models': NER_CONFIG['models'].copy(),
        'timeout': NER_CONFIG['timeout_seconds'],
    }


# 用于测试的简单函数
def test_parse_entities():
    """测试实体解析"""
    test_result = '''
    根据文本分析，提取到的实体如下：
    {
      "entities": [
        {"name": "张三", "type": "PERSON"},
        {"name": "OpenAI", "type": "ORGANIZATION"},
        {"name": "GPT-4", "type": "TOOL"}
      ]
    }
    '''
    
    entities = parse_entities(test_result)
    print(f"Parsed entities: {entities}")
    assert len(entities) == 3
    assert entities[0]['name'] == '张三'
    assert entities[0]['type'] == 'PERSON'
    print("✓ Test passed")


if __name__ == '__main__':
    # 简单测试
    test_parse_entities()
    
    # 测试生成提示词
    content = "张三在使用 OpenAI 的 GPT-4 模型开发新项目"
    prompt = generate_ner_prompt(content)
    print("\nGenerated prompt:")
    print(prompt)
