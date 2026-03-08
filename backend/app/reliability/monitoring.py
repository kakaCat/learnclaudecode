"""
性能监控模块

提供 Agent 性能监控和指标收集功能。
这是一个可选模块，不影响核心功能。
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import datetime
import json
from collections import defaultdict


@dataclass
class PerformanceMetrics:
    """性能指标数据类"""
    
    # 调用统计
    tool_calls: int = 0
    llm_calls: int = 0
    subagent_calls: int = 0
    
    # 时间统计（毫秒）
    total_time_ms: float = 0.0
    tool_time_ms: float = 0.0
    llm_time_ms: float = 0.0
    subagent_time_ms: float = 0.0
    
    # 令牌统计
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # 错误统计
    tool_errors: int = 0
    llm_errors: int = 0
    
    # 详细记录
    tool_breakdown: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    llm_breakdown: List[Dict[str, Any]] = field(default_factory=list)


class PerformanceMonitor:
    """
    性能监控器
    
    使用示例:
        monitor = PerformanceMonitor()
        
        # 监控工具调用
        with monitor.track_tool("read_file"):
            result = read_file("test.txt")
            
        # 监控 LLM 调用
        with monitor.track_llm(model="deepseek-chat"):
            response = llm.invoke(prompt)
            
        # 获取报告
        report = monitor.get_report()
    """
    
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.metrics = PerformanceMetrics()
        self._start_time = time.time()
        self._current_tool: Optional[str] = None
        self._tool_start_time: Optional[float] = None
        
    @contextmanager
    def track_tool(self, tool_name: str, **kwargs):
        """
        跟踪工具执行时间
        
        Args:
            tool_name: 工具名称
            **kwargs: 工具参数（用于记录）
        """
        if not self.enabled:
            yield
            return
            
        start_time = time.time()
        error = None
        
        try:
            yield
        except Exception as e:
            error = e
            self.metrics.tool_errors += 1
            raise
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            
            # 更新指标
            self.metrics.tool_calls += 1
            self.metrics.tool_time_ms += elapsed_ms
            self.metrics.total_time_ms += elapsed_ms
            
            # 记录详细数据
            if tool_name not in self.metrics.tool_breakdown:
                self.metrics.tool_breakdown[tool_name] = {
                    "calls": 0,
                    "total_time_ms": 0.0,
                    "avg_time_ms": 0.0,
                    "errors": 0,
                    "last_call": None
                }
            
            tool_stats = self.metrics.tool_breakdown[tool_name]
            tool_stats["calls"] += 1
            tool_stats["total_time_ms"] += elapsed_ms
            tool_stats["avg_time_ms"] = tool_stats["total_time_ms"] / tool_stats["calls"]
            tool_stats["last_call"] = datetime.now().isoformat()
            
            if error:
                tool_stats["errors"] += 1
    
    @contextmanager
    def track_llm(self, model: str, prompt_tokens: int = 0):
        """
        跟踪 LLM 调用
        
        Args:
            model: 模型名称
            prompt_tokens: 提示令牌数
        """
        if not self.enabled:
            yield
            return
            
        start_time = time.time()
        error = None
        completion_tokens = 0
        
        try:
            yield
        except Exception as e:
            error = e
            self.metrics.llm_errors += 1
            raise
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            
            # 更新指标
            self.metrics.llm_calls += 1
            self.metrics.llm_time_ms += elapsed_ms
            self.metrics.total_time_ms += elapsed_ms
            self.metrics.prompt_tokens += prompt_tokens
            self.metrics.completion_tokens += completion_tokens
            self.metrics.total_tokens += prompt_tokens + completion_tokens
            
            # 记录详细数据
            self.metrics.llm_breakdown.append({
                "model": model,
                "timestamp": datetime.now().isoformat(),
                "time_ms": elapsed_ms,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "error": str(error) if error else None
            })
    
    @contextmanager
    def track_subagent(self, agent_type: str):
        """
        跟踪子 Agent 调用
        """
        if not self.enabled:
            yield
            return
            
        start_time = time.time()
        
        try:
            yield
        finally:
            elapsed_ms = (time.time() - start_time) * 1000
            
            self.metrics.subagent_calls += 1
            self.metrics.subagent_time_ms += elapsed_ms
            self.metrics.total_time_ms += elapsed_ms
    
    def record_tokens(self, prompt_tokens: int, completion_tokens: int):
        """记录令牌使用"""
        if self.enabled:
            self.metrics.prompt_tokens += prompt_tokens
            self.metrics.completion_tokens += completion_tokens
            self.metrics.total_tokens += prompt_tokens + completion_tokens
    
    def get_report(self) -> Dict[str, Any]:
        """生成性能报告"""
        if not self.enabled:
            return {"enabled": False}
        
        total_seconds = time.time() - self._start_time
        
        # 计算平均值
        avg_tool_time = (
            self.metrics.tool_time_ms / self.metrics.tool_calls 
            if self.metrics.tool_calls > 0 else 0
        )
        
        avg_llm_time = (
            self.metrics.llm_time_ms / self.metrics.llm_calls 
            if self.metrics.llm_calls > 0 else 0
        )
        
        avg_subagent_time = (
            self.metrics.subagent_time_ms / self.metrics.subagent_calls 
            if self.metrics.subagent_calls > 0 else 0
        )
        
        # 工具调用频率排序
        tool_frequency = sorted(
            self.metrics.tool_breakdown.items(),
            key=lambda x: x[1]["calls"],
            reverse=True
        )[:10]  # 只显示前10个
        
        return {
            "enabled": True,
            "session_duration_seconds": round(total_seconds, 2),
            
            # 调用统计
            "total_calls": {
                "tools": self.metrics.tool_calls,
                "llm": self.metrics.llm_calls,
                "subagents": self.metrics.subagent_calls,
                "total": self.metrics.tool_calls + self.metrics.llm_calls + self.metrics.subagent_calls
            },
            
            # 时间统计（毫秒）
            "time_stats_ms": {
                "total": round(self.metrics.total_time_ms, 2),
                "tools": round(self.metrics.tool_time_ms, 2),
                "llm": round(self.metrics.llm_time_ms, 2),
                "subagents": round(self.metrics.subagent_time_ms, 2),
                "average": {
                    "tool": round(avg_tool_time, 2),
                    "llm": round(avg_llm_time, 2),
                    "subagent": round(avg_subagent_time, 2)
                }
            },
            
            # 令牌统计
            "token_stats": {
                "prompt": self.metrics.prompt_tokens,
                "completion": self.metrics.completion_tokens,
                "total": self.metrics.total_tokens,
                "avg_per_llm_call": round(
                    self.metrics.total_tokens / self.metrics.llm_calls 
                    if self.metrics.llm_calls > 0 else 0, 2
                )
            },
            
            # 错误统计
            "error_stats": {
                "tools": self.metrics.tool_errors,
                "llm": self.metrics.llm_errors,
                "total": self.metrics.tool_errors + self.metrics.llm_errors,
                "error_rate": round(
                    (self.metrics.tool_errors + self.metrics.llm_errors) / 
                    (self.metrics.tool_calls + self.metrics.llm_calls) * 100 
                    if (self.metrics.tool_calls + self.metrics.llm_calls) > 0 else 0, 2
                )
            },
            
            # 详细分析
            "tool_analysis": {
                "most_frequent": [
                    {"tool": name, "calls": stats["calls"], "avg_time_ms": round(stats["avg_time_ms"], 2)}
                    for name, stats in tool_frequency
                ],
                "slowest_tools": sorted(
                    [
                        {"tool": name, "avg_time_ms": round(stats["avg_time_ms"], 2)}
                        for name, stats in self.metrics.tool_breakdown.items()
                    ],
                    key=lambda x: x["avg_time_ms"],
                    reverse=True
                )[:5]
            },
            
            # 性能评分（简单启发式）
            "performance_score": {
                "tool_efficiency": self._calculate_tool_efficiency_score(),
                "llm_efficiency": self._calculate_llm_efficiency_score(),
                "overall": self._calculate_overall_score()
            }
        }
    
    def _calculate_tool_efficiency_score(self) -> float:
        """计算工具效率评分（0-100）"""
        if self.metrics.tool_calls == 0:
            return 100.0
        
        # 基于平均工具时间和错误率
        avg_time = self.metrics.tool_time_ms / self.metrics.tool_calls
        error_rate = self.metrics.tool_errors / self.metrics.tool_calls
        
        # 启发式评分
        time_score = max(0, 100 - (avg_time / 10))  # 每10ms扣1分
        error_score = max(0, 100 - (error_rate * 1000))  # 每个错误率百分点扣1分
        
        return round((time_score * 0.7 + error_score * 0.3), 2)
    
    def _calculate_llm_efficiency_score(self) -> float:
        """计算 LLM 效率评分（0-100）"""
        if self.metrics.llm_calls == 0:
            return 100.0
        
        # 基于令牌使用和错误率
        avg_tokens = self.metrics.total_tokens / self.metrics.llm_calls
        error_rate = self.metrics.llm_errors / self.metrics.llm_calls
        
        token_score = max(0, 100 - (avg_tokens / 100))  # 每100令牌扣1分
        error_score = max(0, 100 - (error_rate * 1000))
        
        return round((token_score * 0.6 + error_score * 0.4), 2)
    
    def _calculate_overall_score(self) -> float:
        """计算总体性能评分"""
        tool_score = self._calculate_tool_efficiency_score()
        llm_score = self._calculate_llm_efficiency_score()
        
        # 加权平均
        total_calls = self.metrics.tool_calls + self.metrics.llm_calls
        if total_calls == 0:
            return 100.0
        
        tool_weight = self.metrics.tool_calls / total_calls
        llm_weight = self.metrics.llm_calls / total_calls
        
        return round((tool_score * tool_weight + llm_score * llm_weight), 2)
    
    def reset(self):
        """重置监控器"""
        self.metrics = PerformanceMetrics()
        self._start_time = time.time()
    
    def save_report(self, filepath: str):
        """保存报告到文件"""
        report = self.get_report()
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    
    def __str__(self) -> str:
        """字符串表示"""
        report = self.get_report()
        if not report["enabled"]:
            return "PerformanceMonitor (disabled)"
        
        return f"""PerformanceMonitor:
  Duration: {report['session_duration_seconds']}s
  Calls: {report['total_calls']['total']} (Tools: {report['total_calls']['tools']}, LLM: {report['total_calls']['llm']})
  Time: {report['time_stats_ms']['total']}ms
  Tokens: {report['token_stats']['total']}
  Score: {report['performance_score']['overall']}/100
"""


# 全局监控器实例（可选使用）
_global_monitor: Optional[PerformanceMonitor] = None

def get_global_monitor() -> PerformanceMonitor:
    """获取全局监控器实例"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor(enabled=True)
    return _global_monitor

def enable_global_monitoring(enable: bool = True):
    """启用或禁用全局监控"""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor(enabled=enable)
    else:
        _global_monitor.enabled = enable

def disable_global_monitoring():
    """禁用全局监控"""
    enable_global_monitoring(False)