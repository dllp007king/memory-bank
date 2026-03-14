"""
Retain 提取器

从每日日志中提取 Retain 条目并同步到 Memory Bank。
"""

import re
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from . import crud
from .models import Entity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class RetainEntry:
    """Retain 条目"""
    kind: str          # W/B/O/S
    entity: str        # 实体名
    content: str       # 内容（完整，不压缩）
    confidence: float  # 置信度（仅 O 类型）
    source_path: str   # 来源文件
    source_line: int   # 行号


class RetainExtractor:
    """Retain 提取器"""
    
    # Retain 类型映射
    KIND_MAP = {
        "B": "B",  # 经验/传记
        "W": "W",  # 愿望
        "O": "O",  # 意见
        "S": "S",  # 总结
    }
    
    # 解析模式: - K @entity: content 或 - K(c=x) @entity: content
    RETAIN_PATTERN = re.compile(
        r'^\s*-\s*([BWSO])'                              # 类型
        r'(?:\(c=([\d.]+)\))?\s*'                        # 可选置信度
        r'@(\w+):\s*(.+)$',                             # 实体和内容
        re.MULTILINE
    )
    
    def __init__(self, daily_log_dir: Optional[str] = None):
        """
        初始化提取器
        
        Args:
            daily_log_dir: 每日日志目录路径
        """
        if daily_log_dir is None:
            daily_log_dir = Path.home() / ".openclaw" / "workspace" / "memory" / "daily"
        self.daily_log_dir = Path(daily_log_dir)
    
    def parse_retain_block(self, content: str) -> List[RetainEntry]:
        """
        解析 Retain 块内容
        
        Args:
            content: 包含 Retain 条目的文本内容
            
        Returns:
            RetainEntry 列表
        """
        entries = []
        
        for match in self.RETAIN_PATTERN.finditer(content):
            kind = match.group(1)
            confidence_str = match.group(2)
            entity = match.group(3)
            entry_content = match.group(4).strip()
            
            # 解析置信度
            confidence = 1.0
            if confidence_str and kind == "O":
                try:
                    confidence = float(confidence_str)
                except ValueError:
                    logger.warning(f"Invalid confidence: {confidence_str}, using 1.0")
            
            # 跳过空内容
            if not entry_content:
                continue
            
            entries.append(RetainEntry(
                kind=kind,
                entity=entity,
                content=entry_content,
                confidence=confidence,
                source_path="",
                source_line=0,
            ))
        
        logger.info(f"Parsed {len(entries)} retain entries from block")
        return entries
    
    def extract_from_daily_log(self, date: str) -> List[RetainEntry]:
        """
        从指定日期的每日日志提取 Retain 条目
        
        Args:
            date: 日期字符串，格式 YYYY-MM-DD
            
        Returns:
            RetainEntry 列表
        """
        # 解析年月
        year_month = date[:7]  # YYYY-MM
        log_file = self.daily_log_dir / year_month / f"{date}.md"
        
        if not log_file.exists():
            logger.warning(f"Daily log not found: {log_file}")
            return []
        
        # 读取文件
        content = log_file.read_text(encoding="utf-8")
        
        # 查找 Retain 块
        retain_block = self._extract_retain_section(content)
        if not retain_block:
            logger.info(f"No Retain block found in {log_file}")
            return []
        
        # 解析 Retain 条目
        entries = self.parse_retain_block(retain_block)
        
        # 填充来源信息
        for entry in entries:
            entry.source_path = str(log_file)
            entry.source_line = self._find_line_number(content, entry.content)
        
        return entries
    
    def _extract_retain_section(self, content: str) -> Optional[str]:
        """提取 Retain 章节内容"""
        lines = content.split("\n")
        in_retain = False
        retain_lines = []
        
        for line in lines:
            # 检测 Retain 标题
            if re.match(r'^##\s*Retain\s*$', line, re.IGNORECASE):
                in_retain = True
                continue
            
            # 检测新章节（## 开头）
            if in_retain and line.startswith("## "):
                break
            
            if in_retain:
                retain_lines.append(line)
        
        return "\n".join(retain_lines) if retain_lines else None
    
    def _find_line_number(self, content: str, entry_content: str) -> int:
        """查找内容在原文中的行号（1-indexed）"""
        lines = content.split("\n")
        for i, line in enumerate(lines, 1):
            if entry_content in line:
                return i
        return 0
    
    def sync_to_memory_bank(self, entries: List[RetainEntry]) -> int:
        """
        同步 Retain 条目到 Memory Bank
        
        Args:
            entries: RetainEntry 列表
            
        Returns:
            新创建或更新的条目数量
        """
        synced_count = 0
        
        for entry in entries:
            # 1. 检查是否已存在相同内容
            existing = self._find_existing_fact(entry)
            
            if existing:
                # 更新已有事实的 updated_at
                crud.update_fact(existing.id)
                logger.debug(f"Fact already exists: {entry.content[:30]}...")
            else:
                # 2. 确保实体存在
                entity_slug = self._slugify(entry.entity)
                self._ensure_entity(entry.entity, entity_slug)
                
                # 3. 创建新事实
                crud.create_fact(
                    content=entry.content,
                    kind=entry.kind,
                    entities=[entity_slug],
                    confidence=entry.confidence,
                    source_path=entry.source_path,
                    source_line=entry.source_line,
                )
                synced_count += 1
                logger.info(f"Created fact: {entry.content[:50]}...")
        
        return synced_count
    
    def _find_existing_fact(self, entry: RetainEntry) -> Optional[any]:
        """查找是否已存在相同内容的事实"""
        facts = crud.list_facts(kind=entry.kind, limit=1000)
        
        for fact in facts:
            # 完全匹配内容
            if fact.content == entry.content:
                return fact
        
        return None
    
    def _slugify(self, name: str) -> str:
        """将实体名转换为 slug"""
        # 简单实现：转小写，空格转下划线
        return name.lower().replace(" ", "_")
    
    def _ensure_entity(self, name: str, slug: str) -> None:
        """确保实体存在，不存在则创建"""
        existing = crud.get_entity(slug)
        if not existing:
            crud.create_entity(
                slug=slug,
                name=name,
                summary=f"从每日日志自动创建",
            )
            logger.info(f"Created entity: {name} ({slug})")
    
    def extract_and_sync(self, date: str) -> int:
        """
        从指定日期日志提取并同步到 Memory Bank
        
        Args:
            date: 日期字符串，格式 YYYY-MM-DD
            
        Returns:
            新创建或更新的条目数量
        """
        entries = self.extract_from_daily_log(date)
        if not entries:
            logger.info(f"No entries found for {date}")
            return 0
        
        return self.sync_to_memory_bank(entries)


# 便捷函数
def extract_from_date(date: str, daily_log_dir: Optional[str] = None) -> List[RetainEntry]:
    """从指定日期提取 Retain 条目"""
    extractor = RetainExtractor(daily_log_dir)
    return extractor.extract_from_daily_log(date)


def sync_date(date: str, daily_log_dir: Optional[str] = None) -> int:
    """提取并同步指定日期的 Retain 条目"""
    extractor = RetainExtractor(daily_log_dir)
    return extractor.extract_and_sync(date)
