"""
会话钩子系统 - Session Hook
"""

import os
import sys
import time
import threading
import signal
from datetime import datetime
from typing import Optional, Callable, List
from pathlib import Path
from dataclasses import dataclass

from .logger import get_logger, MemoryLogger


@dataclass
class SessionState:
    """会话状态"""
    is_running: bool = False
    is_monitoring: bool = False
    last_activity: datetime = None
    idle_seconds: int = 0
    total_triggers: int = 0


class SessionHook:
    """
    会话钩子 - 监控会话空闲超时
    
    功能:
    - 监控会话空闲时间
    - 超时时触发回调（Retain 提取、会话整理、日志记录）
    - 支持后台线程监控
    """
    
    def __init__(self, idle_timeout: int = 600):
        """
        初始化会话钩子
        
        Args:
            idle_timeout: 空闲超时时间（秒），默认 600 秒（10分钟）
        """
        self.idle_timeout = idle_timeout
        self.logger: MemoryLogger = get_logger()
        
        # 会话状态
        self._state = SessionState()
        self._state_lock = threading.Lock()
        
        # 监控线程
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # 回调函数
        self._callbacks: List[Callable] = []
        
        # Graceful shutdown
        self._is_shutting_down = False
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理退出信号"""
        self.logger.info("session_hook", "收到退出信号，正在优雅关闭...")
        self.stop_monitor()
        sys.exit(0)
    
    @property
    def state(self) -> SessionState:
        """获取当前状态"""
        with self._state_lock:
            return SessionState(
                is_running=self._state.is_running,
                is_monitoring=self._state.is_monitoring,
                last_activity=self._state.last_activity,
                idle_seconds=self._state.idle_seconds,
                total_triggers=self._state.total_triggers,
            )
    
    def add_callback(self, callback: Callable):
        """
        添加空闲超时回调
        
        Args:
            callback: 回调函数，会在超时时调用
        """
        self._callbacks.append(callback)
    
    def on_message(self):
        """
        收到消息时调用，重置计时器
        
        应该在每次收到用户消息时调用此方法
        """
        with self._state_lock:
            self._state.last_activity = datetime.now()
            self._state.idle_seconds = 0
        
        self.logger.debug("session_hook", "收到消息，重置空闲计时器")
    
    def start_monitor(self):
        """
        开始监控会话空闲时间
        
        启动后台线程监控空闲超时
        """
        if self._state.is_monitoring:
            self.logger.warning("session_hook", "监控已在运行中")
            return
        
        with self._state_lock:
            self._state.is_monitoring = True
            self._state.is_running = True
            self._state.last_activity = datetime.now()
            self._state.idle_seconds = 0
        
        self._stop_event.clear()
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            name="SessionHook-Monitor",
            daemon=True
        )
        self._monitor_thread.start()
        
        self.logger.info("session_hook", f"开始监控会话空闲时间 (超时: {self.idle_timeout}秒)")
    
    def stop_monitor(self):
        """
        停止监控
        
        等待当前操作完成后优雅退出
        """
        if not self._state.is_monitoring:
            return
        
        self.logger.info("session_hook", "正在停止监控...")
        self._is_shutting_down = True
        self._stop_event.set()
        
        # 等待监控线程结束
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=5)
        
        with self._state_lock:
            self._state.is_monitoring = False
            self._state.is_running = False
        
        self.logger.info("session_hook", "监控已停止")
    
    def _monitor_loop(self):
        """监控循环"""
        check_interval = 5  # 每 5 秒检查一次
        
        while not self._stop_event.is_set():
            try:
                # 计算空闲时间
                with self._state_lock:
                    if self._state.last_activity:
                        idle_time = (datetime.now() - self._state.last_activity).total_seconds()
                        self._state.idle_seconds = int(idle_time)
                
                # 检查是否超时
                if self._state.idle_seconds >= self.idle_timeout:
                    self.logger.info(
                        "session_hook", 
                        f"检测到空闲超时 ({self._state.idle_seconds}秒)",
                        {"timeout": self.idle_timeout}
                    )
                    self._trigger_idle_timeout()
                    
                    # 重置计时器（避免连续触发）
                    with self._state_lock:
                        self._state.last_activity = datetime.now()
                        self._state.idle_seconds = 0
                
                # 等待下次检查
                self._stop_event.wait(check_interval)
                
            except Exception as e:
                self.logger.error("session_hook", f"监控循环异常: {e}")
                self._stop_event.wait(check_interval)
    
    def _trigger_idle_timeout(self):
        """
        触发空闲超时回调
        
        执行:
        1. 触发 Retain 提取
        2. 整理当前会话
        3. 记录日志
        """
        self.logger.info("session_hook", "开始执行空闲超时处理")
        
        # 更新触发计数
        with self._state_lock:
            self._state.total_triggers += 1
        
        # 调用所有回调
        for callback in self._callbacks:
            try:
                callback(self)
            except Exception as e:
                self.logger.error(
                    "session_hook", 
                    f"回调执行失败: {e}",
                    {"callback": callback.__name__ if hasattr(callback, '__name__') else str(callback)}
                )
        
        self.logger.info("session_hook", "空闲超时处理完成")
    
    def on_idle_timeout(self):
        """
        空闲超时回调（可重写）
        
        默认实现执行:
        1. 触发 Retain 提取
        2. 整理当前会话
        3. 记录日志
        """
        self.logger.info("session_hook", "执行默认空闲超时处理")

        # 待实现: 调用 retain_extractor.RetainExtractor 提取 Retain 条目
        # 待实现: 整理当前会话的记忆，去重和压缩

        self.logger.info("session_hook", "默认空闲超时处理完成")
    
    def trigger(self):
        """
        手动触发一次整理
        
        相当于手动调用 on_idle_timeout
        """
        self.logger.info("session_hook", "手动触发会话整理")
        self._trigger_idle_timeout()
    
    def get_status(self) -> dict:
        """
        获取当前状态
        
        Returns:
            状态字典
        """
        with self._state_lock:
            return {
                "is_running": self._state.is_running,
                "is_monitoring": self._state.is_monitoring,
                "last_activity": self._state.last_activity.isoformat() if self._state.last_activity else None,
                "idle_seconds": self._state.idle_seconds,
                "idle_timeout": self.idle_timeout,
                "total_triggers": self._state.total_triggers,
                "callbacks_count": len(self._callbacks),
            }


# 全局会话钩子实例
_session_hook: Optional[SessionHook] = None
_session_hook_lock = threading.Lock()


def get_session_hook() -> SessionHook:
    """获取全局会话钩子实例"""
    global _session_hook
    if _session_hook is None:
        with _session_hook_lock:
            if _session_hook is None:
                _session_hook = SessionHook()
    return _session_hook


# === CLI 集成 ===

def cli_hook_start(args):
    """CLI: 开始监控"""
    hook = get_session_hook()
    hook.add_callback(SessionHook.on_idle_timeout)
    hook.start_monitor()
    print(f"✅ 会话钩子已启动 (超时: {hook.idle_timeout}秒)")
    print(f"   状态: {hook.get_status()}")


def cli_hook_status(args):
    """CLI: 查看状态"""
    hook = get_session_hook()
    status = hook.get_status()
    
    print("📊 Session Hook 状态:")
    print(f"   运行中: {status['is_running']}")
    print(f"   监控中: {status['is_monitoring']}")
    print(f"   上次活动: {status['last_activity']}")
    print(f"   空闲时间: {status['idle_seconds']}秒")
    print(f"   超时设置: {status['idle_timeout']}秒")
    print(f"   总触发次数: {status['total_triggers']}")
    print(f"   回调数量: {status['callbacks_count']}")


def cli_hook_trigger(args):
    """CLI: 手动触发"""
    hook = get_session_hook()
    hook.trigger()
    print("✅ 手动触发完成")


def register_cli_commands(cli):
    """注册 CLI 命令"""
    hook_parser = cli.add_parser("hook", help="会话钩子管理")
    hook_subparsers = hook_parser.add_subparsers()
    
    # hook start
    start_parser = hook_subparsers.add_parser("start", help="开始监控")
    start_parser.set_defaults(func=cli_hook_start)
    
    # hook status
    status_parser = hook_subparsers.add_parser("status", help="查看状态")
    status_parser.set_defaults(func=cli_hook_status)
    
    # hook trigger
    trigger_parser = hook_subparsers.add_parser("trigger", help="手动触发")
    trigger_parser.set_defaults(func=cli_hook_trigger)


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Session Hook CLI")
    register_cli_commands(parser)
    
    args = parser.parse_args()
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()
