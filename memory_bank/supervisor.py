"""
监督者 - 带重试和错误分析的自动化任务执行器
"""

import logging
import traceback
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any, Optional
import json
import os

# 配置日志
LOG_DIR = "/home/myclaw/.openclaw/workspace/memory-bank/logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/supervisor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Supervisor")


@dataclass
class Result:
    """任务执行结果"""
    success: bool
    data: Any = None
    error: Optional[Exception] = None
    attempts: int = 1
    fix_applied: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": str(self.error) if self.error else None,
            "attempts": self.attempts,
            "fix_applied": self.fix_applied,
        }


class Supervisor:
    """带监督和重试机制的任务执行器"""
    
    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.logger = logger
    
    def execute_with_supervision(self, task: Callable, task_name: str) -> Result:
        """
        执行任务并监督整个过程
        
        流程：执行 → 检查结果 → 失败则分析 → 尝试修复 → 重试（最多3次）→ 最终失败则汇报
        """
        attempt = 0
        last_error = None
        fix_applied = None
        
        while attempt < self.max_retries:
            attempt += 1
            self.logger.info(f"[{task_name}] 第 {attempt}/{self.max_retries} 次尝试")
            
            try:
                # 1. 执行任务
                result = task()
                
                # 2. 检查结果
                if self._is_success(result):
                    self.logger.info(f"[{task_name}] 任务成功")
                    return Result(
                        success=True,
                        data=result,
                        attempts=attempt,
                        fix_applied=fix_applied
                    )
                else:
                    self.logger.warning(f"[{task_name}] 任务返回失败结果: {result}")
                    last_error = Exception(str(result))
                    
            except Exception as e:
                last_error = e
                self.logger.warning(f"[{task_name}] 执行出错: {e}")
            
            # 如果还有重试机会，分析并尝试修复
            if attempt < self.max_retries:
                # 3. 分析错误原因
                analysis = self.analyze_failure(last_error)
                self.logger.info(f"[{task_name}] 错误分析: {analysis}")
                
                # 4. 尝试修复
                fix_applied = self._try_fix(analysis, task_name)
                if fix_applied:
                    self.logger.info(f"[{task_name}] 已应用修复: {fix_applied}")
                else:
                    self.logger.info(f"[{task_name}] 无自动修复方案，将重试")
        
        # 5. 最终失败，汇报给 myclaw
        self.logger.error(f"[{task_name}] 全部 {self.max_retries} 次尝试失败")
        analysis = self.analyze_failure(last_error)
        self.report_to_myclaw(task_name, last_error, analysis)
        
        return Result(
            success=False,
            error=last_error,
            attempts=attempt,
            fix_applied=fix_applied
        )
    
    def _is_success(self, result: Any) -> bool:
        """检查结果是否成功"""
        if isinstance(result, bool):
            return result
        if isinstance(result, dict):
            return result.get("success", False)
        if hasattr(result, "success"):
            return result.success
        # 默认认为非False/None为成功
        return result is not None and result is not False
    
    def analyze_failure(self, error: Exception) -> dict:
        """
        分析错误原因并返回修复建议
        
        Returns:
            dict: {"reason": "...", "fix_suggestion": "..."}
        """
        if error is None:
            return {"reason": "未知错误", "fix_suggestion": "请检查任务逻辑"}
        
        error_type = type(error).__name__
        error_msg = str(error)
        
        # 常见错误模式分析
        if "connection" in error_msg.lower() or "timeout" in error_msg.lower():
            return {
                "reason": f"网络连接问题 ({error_type})",
                "fix_suggestion": "检查网络连接，增加重试延迟"
            }
        elif "database" in error_msg.lower() or "sqlite" in error_msg.lower():
            return {
                "reason": f"数据库错误 ({error_type})",
                "fix_suggestion": "检查数据库文件，验证表结构"
            }
        elif "permission" in error_msg.lower() or "denied" in error_msg.lower():
            return {
                "reason": f"权限问题 ({error_type})",
                "fix_suggestion": "检查文件/目录权限设置"
            }
        elif "not found" in error_msg.lower() or "no such file" in error_msg.lower():
            return {
                "reason": f"文件不存在 ({error_type})",
                "fix_suggestion": "检查路径是否正确，文件是否存在"
            }
        elif "json" in error_msg.lower() or "parse" in error_msg.lower():
            return {
                "reason": f"解析错误 ({error_type})",
                "fix_suggestion": "检查JSON/数据格式是否正确"
            }
        elif "memory" in error_msg.lower() or "oom" in error_msg.lower():
            return {
                "reason": f"内存问题 ({error_type})",
                "fix_suggestion": "减少处理数据量，分批处理"
            }
        else:
            return {
                "reason": f"{error_type}: {error_msg}",
                "fix_suggestion": "查看详细日志获取更多信息"
            }
    
    def _try_fix(self, analysis: dict, task_name: str) -> Optional[str]:
        """根据分析结果尝试自动修复"""
        fix_suggestion = analysis.get("fix_suggestion", "")
        
        # 简单的自动修复策略
        if "重试延迟" in fix_suggestion:
            import time
            time.sleep(1)  # 短暂延迟后重试
            return "添加重试延迟"
        
        # 更多自动修复可以在这里扩展
        return None
    
    def report_to_myclaw(self, task_name: str, error: Exception, analysis: dict):
        """
        汇报给 myclaw
        
        写入日志文件并记录失败信息
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 构建报告内容
        report = {
            "timestamp": timestamp,
            "task_name": task_name,
            "error_type": type(error).__name__ if error else "Unknown",
            "error_message": str(error) if error else "Unknown",
            "analysis": analysis,
            "status": "FAILED"
        }
        
        # 写入失败报告
        report_file = f"{LOG_DIR}/failure_reports.json"
        reports = []
        if os.path.exists(report_file):
            try:
                with open(report_file, 'r') as f:
                    reports = json.load(f)
            except (json.JSONDecodeError, IOError):
                reports = []
        
        reports.append(report)
        
        # 只保留最近100条
        reports = reports[-100:]
        
        with open(report_file, 'w') as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)
        
        # 写入详细日志
        log_file = f"{LOG_DIR}/failure_{task_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, 'w') as f:
            f.write(f"任务失败报告\n")
            f.write(f"=" * 50 + "\n")
            f.write(f"时间: {timestamp}\n")
            f.write(f"任务: {task_name}\n")
            f.write(f"错误类型: {type(error).__name__ if error else 'Unknown'}\n")
            f.write(f"错误信息: {str(error) if error else 'Unknown'}\n")
            f.write(f"\n分析:\n")
            f.write(f"  原因: {analysis.get('reason', 'N/A')}\n")
            f.write(f"  修复建议: {analysis.get('fix_suggestion', 'N/A')}\n")
            f.write(f"\n堆栈跟踪:\n")
            f.write(traceback.format_exc())
        
        self.logger.error(f"[{task_name}] 已生成失败报告: {log_file}")


# 使用示例
if __name__ == "__main__":
    supervisor = Supervisor(max_retries=3)
    
    # 示例任务：模拟可能失败的任务
    def my_task():
        import random
        # 模拟 70% 成功率
        if random.random() < 0.7:
            return {"success": True, "data": "任务完成"}
        else:
            raise Exception("Database connection timeout")
    
    # 执行任务
    result = supervisor.execute_with_supervision(my_task, "向量化任务")
    
    if result.success:
        print(f"✅ 成功: {result.data}")
    else:
        print(f"❌ 失败: {result.error}")
        print(f"   尝试次数: {result.attempts}")
