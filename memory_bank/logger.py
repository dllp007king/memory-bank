"""
日志系统 - Memory Logger
"""

import os
import json
import threading
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List
from pathlib import Path

from .models import Fact


@dataclass
class LogEntry:
    """日志条目"""
    timestamp: datetime
    level: str
    module: str
    message: str
    data: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "level": self.level,
            "module": self.module,
            "message": self.message,
            "data": self.data,
        }


class MemoryLogger:
    """内存银行日志系统"""
    
    # 日志级别
    LEVELS = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    
    def __init__(self, log_dir: str = "logs"):
        """
        初始化日志系统
        
        Args:
            log_dir: 日志目录路径（相对于 memory-bank 目录）
        """
        # 获取 memory-bank 根目录
        self.base_dir = Path(__file__).parent.parent
        self.log_dir = self.base_dir / log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 内存缓冲（最近日志）
        self._buffer: List[LogEntry] = []
        self._buffer_lock = threading.Lock()
        self._buffer_size = 1000
        
        # 数据库连接（用于写入 Memory Bank）
        self._db = None
    
    def _get_db(self):
        """延迟加载数据库连接"""
        if self._db is None:
            try:
                from .crud import get_db
                self._db = get_db()
            except Exception as e:
                print(f"[Logger] Failed to get database: {e}")
                return None
        return self._db
    
    def _get_log_filename(self, date: datetime = None) -> Path:
        """获取指定日期的日志文件名"""
        if date is None:
            date = datetime.now()
        return self.log_dir / f"{date.strftime('%Y-%m-%d')}.log"
    
    def _format_log(self, entry: LogEntry) -> str:
        """格式化日志条目"""
        timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        data_str = f" | {json.dumps(entry.data, ensure_ascii=False)}" if entry.data else ""
        return f"[{timestamp}] [{entry.level:8s}] [{entry.module}] {entry.message}{data_str}\n"
    
    def log(self, level: str, module: str, message: str, data: dict = None):
        """
        记录日志
        
        Args:
            level: 日志级别 (DEBUG/INFO/WARNING/ERROR/CRITICAL)
            module: 模块名称
            message: 日志消息
            data: 附加数据
        """
        if level.upper() not in self.LEVELS:
            level = "INFO"
        else:
            level = level.upper()
        
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            module=module,
            message=message,
            data=data,
        )
        
        # 写入文件
        self._write_to_file(entry)
        
        # 添加到缓冲
        with self._buffer_lock:
            self._buffer.append(entry)
            if len(self._buffer) > self._buffer_size:
                self._buffer = self._buffer[-self._buffer_size:]
        
        # 写入 Memory Bank (kind="L")
        self._write_to_memory_bank(entry)
    
    def _write_to_file(self, entry: LogEntry):
        """写入日志文件"""
        try:
            log_file = self._get_log_filename(entry.timestamp)
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(self._format_log(entry))
        except Exception as e:
            # 日志写入失败不应中断程序
            print(f"[Logger] Failed to write log file: {e}")
    
    def _write_to_memory_bank(self, entry: LogEntry):
        """写入 Memory Bank 数据库"""
        try:
            from .crud import create_fact
            # 使用 kind="L" 标记为日志类型
            create_fact(
                content=f"[{entry.level}] {entry.module}: {entry.message}",
                kind="L",
                entities=[entry.level, entry.module],
                source_path=str(self._get_log_filename(entry.timestamp)),
                confidence=1.0,
            )
        except Exception as e:
            # 日志写入失败不应中断程序
            pass  # 静默失败，避免干扰
    
    def info(self, module: str, message: str, data: dict = None):
        """记录 INFO 日志"""
        self.log("INFO", module, message, data)
    
    def warning(self, module: str, message: str, data: dict = None):
        """记录 WARNING 日志"""
        self.log("WARNING", module, message, data)
    
    def error(self, module: str, message: str, data: dict = None):
        """记录 ERROR 日志"""
        self.log("ERROR", module, message, data)
    
    def debug(self, module: str, message: str, data: dict = None):
        """记录 DEBUG 日志"""
        self.log("DEBUG", module, message, data)
    
    def critical(self, module: str, message: str, data: dict = None):
        """记录 CRITICAL 日志"""
        self.log("CRITICAL", module, message, data)
    
    def get_logs(
        self, 
        module: str = None, 
        level: str = None, 
        limit: int = 100,
        date: datetime = None
    ) -> List[LogEntry]:
        """
        获取日志条目
        
        Args:
            module: 按模块过滤
            level: 按级别过滤
            limit: 返回数量限制
            date: 指定日期（默认今天）
        
        Returns:
            日志条目列表
        """
        # 首先尝试从缓冲获取
        with self._buffer_lock:
            logs = list(self._buffer)
        
        # 如果缓冲为空，从文件读取
        if not logs and date is None:
            date = datetime.now()
        
        if date:
            try:
                log_file = self._get_log_filename(date)
                if log_file.exists():
                    logs = self._read_from_file(log_file)
            except Exception as e:
                print(f"[Logger] Failed to read log file: {e}")
        
        # 过滤
        if module:
            logs = [l for l in logs if l.module == module]
        if level:
            logs = [l for l in logs if l.level == level.upper()]
        
        # 排序并限制
        logs = sorted(logs, key=lambda x: x.timestamp, reverse=True)
        return logs[:limit]
    
    def _read_from_file(self, log_file: Path) -> List[LogEntry]:
        """从日志文件读取"""
        logs = []
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    entry = self._parse_log_line(line)
                    if entry:
                        logs.append(entry)
        except Exception as e:
            print(f"[Logger] Failed to parse log file: {e}")
        return logs
    
    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        """解析日志行"""
        import re
        # 格式: [2026-03-04 03:10:15] [INFO] [embedding] 开始向量化 | {"texts": 5}
        pattern = r'\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[(\w+)\] \[(\w+)\] (.+?)(?: \| (.+))?$'
        match = re.match(pattern, line)
        if match:
            timestamp_str, level, module, message, data_str = match.groups()
            data = json.loads(data_str) if data_str else None
            return LogEntry(
                timestamp=datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S"),
                level=level,
                module=module,
                message=message,
                data=data,
            )
        return None
    
    def rotate_logs(self, max_days: int = 30):
        """
        清理旧日志
        
        Args:
            max_days: 保留天数
        """
        cutoff_date = datetime.now() - timedelta(days=max_days)
        removed_count = 0
        
        try:
            for log_file in self.log_dir.glob("*.log"):
                # 从文件名提取日期
                date_str = log_file.stem
                try:
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if file_date < cutoff_date:
                        log_file.unlink()
                        removed_count += 1
                except ValueError:
                    continue
            
            self.info("logger", f"日志轮转完成，删除 {removed_count} 个旧日志文件", {"max_days": max_days})
        except Exception as e:
            self.error("logger", f"日志轮转失败: {e}")
        
        return removed_count


# 全局日志实例
_logger: Optional[MemoryLogger] = None
_logger_lock = threading.Lock()


def get_logger() -> MemoryLogger:
    """获取全局日志实例"""
    global _logger
    if _logger is None:
        with _logger_lock:
            if _logger is None:
                _logger = MemoryLogger()
    return _logger
