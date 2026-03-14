"""
Memory Bank 配置管理模块

管理记忆生命周期的所有参数，包括：
- 衰减率 (λ)
- 置信度和重要程度的默认值
- 清理和提炼的阈值
"""

import json
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# 配置文件路径
CONFIG_DIR = Path(__file__).parent.parent / "config"
CONFIG_FILE = CONFIG_DIR / "memory_lifecycle.json"


@dataclass
class DecayRateConfig:
    """衰减率配置"""
    permanent: float = 0.0001    # 恒定 - 几乎不变
    long_term: float = 0.001     # 长期 - 年
    medium_term: float = 0.01    # 中期 - 月
    short_term: float = 0.05     # 短期 - 周
    instant: float = 0.2         # 即时 - 天/小时

    description: Dict[str, str] = field(default_factory=lambda: {
        "permanent": "恒定信息（数学真理、身份信息）- 几乎不变",
        "long_term": "长期信息（价值观、技能、关系）- 以年为单位变化",
        "medium_term": "中期信息（项目状态、工作关系）- 以月为单位变化",
        "short_term": "短期信息（计划、意图、任务）- 以周为单位变化",
        "instant": "即时信息（情绪、位置、活动）- 以天/小时为单位变化"
    })


@dataclass
class ConfidenceConfig:
    """置信度配置"""
    # 初始置信度
    user_direct: float = 0.95       # 用户明确陈述
    user_uncertain: float = 0.70    # 带不确定词
    inference: float = 0.60         # AI 推断
    guess: float = 0.40             # AI 猜测
    third_party: float = 0.50       # 第三方信息

    # 矛盾判断阈值
    contradiction_threshold: float = 0.15

    description: Dict[str, str] = field(default_factory=lambda: {
        "user_direct": "用户明确陈述 - 对话中直接获取",
        "user_uncertain": "带不确定词 - '可能'、'好像'、'我记得'",
        "inference": "AI 推断 - 从上下文推断",
        "guess": "AI 猜测 - 推测、猜想",
        "third_party": "第三方信息 - 文档、网页",
        "contradiction_threshold": "矛盾判断阈值 - 新旧信息置信度差异超过此值才更新"
    })


@dataclass
class ImportanceConfig:
    """重要程度配置"""
    # 保留阈值
    keep_importance_threshold: float = 0.8   # 重要程度阈值
    keep_effective_threshold: float = 0.5    # 有效置信度阈值

    # 清理阈值
    cleanup_importance_threshold: float = 0.3
    cleanup_effective_threshold: float = 0.3

    # 默认有效置信度阈值
    default_effective_threshold: float = 0.1

    description: Dict[str, str] = field(default_factory=lambda: {
        "keep_importance_threshold": "保留阈值 - 重要程度 > 此值 且 effective > keep_effective_threshold 则保留",
        "keep_effective_threshold": "保留阈值 - 与 keep_importance_threshold 配合使用",
        "cleanup_importance_threshold": "清理阈值 - 重要程度 < 此值 且 effective < cleanup_effective_threshold 则清理",
        "cleanup_effective_threshold": "清理阈值 - 与 cleanup_importance_threshold 配合使用",
        "default_effective_threshold": "默认阈值 - 其他情况 effective > 此值 则保留"
    })


@dataclass
class LifecycleConfig:
    """记忆生命周期配置"""
    # 生命周期状态
    active_threshold: float = 0.5      # ACTIVE 状态阈值
    fading_threshold: float = 0.2      # FADING 状态阈值
    archived_threshold: float = 0.05   # ARCHIVED 状态阈值

    # 清理配置
    forgotten_after_days: int = 90     # FORGOTTEN 状态保留天数
    archived_after_days: int = 180     # ARCHIVED 状态保留天数
    orphan_after_days: int = 30        # 孤立实体保留天数

    description: Dict[str, str] = field(default_factory=lambda: {
        "active_threshold": "ACTIVE 状态 - effective > 此值",
        "fading_threshold": "FADING 状态 - effective 在此值和 active_threshold 之间",
        "archived_threshold": "ARCHIVED 状态 - effective 在此值和 fading_threshold 之间",
        "forgotten_after_days": "FORGOTTEN 状态保留天数 - 超过此天数后删除",
        "archived_after_days": "ARCHIVED 状态保留天数 - 超过此天数后提炼或删除",
        "orphan_after_days": "孤立实体保留天数 - 无关联的实体保留天数"
    })


@dataclass
class MemoryLifecycleConfig:
    """记忆生命周期总配置"""
    decay_rates: DecayRateConfig = field(default_factory=DecayRateConfig)
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    importance: ImportanceConfig = field(default_factory=ImportanceConfig)
    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "decay_rates": asdict(self.decay_rates),
            "confidence": asdict(self.confidence),
            "importance": asdict(self.importance),
            "lifecycle": asdict(self.lifecycle)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryLifecycleConfig":
        """从字典创建"""
        config = cls()

        if "decay_rates" in data:
            for key, value in data["decay_rates"].items():
                if key != "description" and hasattr(config.decay_rates, key):
                    setattr(config.decay_rates, key, value)

        if "confidence" in data:
            for key, value in data["confidence"].items():
                if key != "description" and hasattr(config.confidence, key):
                    setattr(config.confidence, key, value)

        if "importance" in data:
            for key, value in data["importance"].items():
                if key != "description" and hasattr(config.importance, key):
                    setattr(config.importance, key, value)

        if "lifecycle" in data:
            for key, value in data["lifecycle"].items():
                if key != "description" and hasattr(config.lifecycle, key):
                    setattr(config.lifecycle, key, value)

        return config


# 全局配置实例
_config: Optional[MemoryLifecycleConfig] = None


def get_config() -> MemoryLifecycleConfig:
    """获取配置实例"""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config() -> MemoryLifecycleConfig:
    """从文件加载配置"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"加载配置文件: {CONFIG_FILE}")
            return MemoryLifecycleConfig.from_dict(data)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
    return MemoryLifecycleConfig()


def save_config(config: MemoryLifecycleConfig) -> bool:
    """保存配置到文件"""
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
        logger.info(f"保存配置文件: {CONFIG_FILE}")
        return True
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")
        return False


def update_config(section: str, key: str, value: Any) -> bool:
    """更新配置项"""
    config = get_config()

    section_map = {
        "decay_rates": config.decay_rates,
        "confidence": config.confidence,
        "importance": config.importance,
        "lifecycle": config.lifecycle
    }

    if section not in section_map:
        logger.error(f"未知配置段: {section}")
        return False

    section_obj = section_map[section]
    if not hasattr(section_obj, key):
        logger.error(f"未知配置项: {section}.{key}")
        return False

    # 类型转换
    try:
        original_value = getattr(section_obj, key)
        if isinstance(original_value, float):
            value = float(value)
        elif isinstance(original_value, int):
            value = int(value)
    except:
        pass

    setattr(section_obj, key, value)
    global _config
    _config = config
    return save_config(config)


def reset_config() -> MemoryLifecycleConfig:
    """重置配置为默认值"""
    global _config
    _config = MemoryLifecycleConfig()
    save_config(_config)
    return _config


# ============ 辅助函数 ============

def effective_confidence(confidence: float, decay_rate: float, days: float) -> float:
    """
    计算有效置信度

    effective = confidence × e^(-λ × days)
    """
    import math
    return confidence * math.exp(-decay_rate * days)


def cleanup_priority(importance: float, effective: float, days: float) -> float:
    """
    计算清理优先级

    cleanup = (1 - importance) × (1 - effective) × days
    """
    return (1 - importance) * (1 - effective) * days


def distill_priority(importance: float, access_count: int, days: float) -> float:
    """
    计算提炼优先级

    distill = importance × access_count × days
    """
    return importance * access_count * days


def should_keep(importance: float, effective: float) -> bool:
    """
    判断是否应该保留记忆
    """
    config = get_config()

    # 重要且可信 → 始终保留
    if importance > config.importance.keep_importance_threshold and \
       effective > config.importance.keep_effective_threshold:
        return True

    # 不重要且不可信 → 清理
    if importance < config.importance.cleanup_importance_threshold and \
       effective < config.importance.cleanup_effective_threshold:
        return False

    # 其他情况根据有效置信度判断
    return effective > config.importance.default_effective_threshold


def infer_decay_rate(content: str) -> float:
    """
    从内容推断衰减率
    """
    config = get_config()

    # 恒定模式
    permanent_markers = ["永远是", "始终", "永远", "必然", "一定", "真理"]
    for marker in permanent_markers:
        if marker in content:
            return config.decay_rates.permanent

    # 长期模式
    long_term_markers = ["我是", "我会", "我的", "相信", "价值观", "性格", "习惯"]
    for marker in long_term_markers:
        if marker in content:
            return config.decay_rates.long_term

    # 短期模式
    short_term_markers = ["打算", "计划", "下周", "准备", "想要", "将要"]
    for marker in short_term_markers:
        if marker in content:
            return config.decay_rates.short_term

    # 即时模式
    instant_markers = ["今天", "此刻", "正在", "马上", "现在就"]
    for marker in instant_markers:
        if marker in content:
            return config.decay_rates.instant

    # 默认中期
    return config.decay_rates.medium_term


if __name__ == "__main__":
    # 打印默认配置
    config = get_config()
    print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
