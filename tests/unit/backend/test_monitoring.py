"""
性能监控模块测试
"""

import pytest
import time
from unittest.mock import Mock, patch
from backend.app.monitoring import PerformanceMonitor, PerformanceMetrics


class TestPerformanceMetrics:
    """测试 PerformanceMetrics 类"""
    
    def test_initialization(self):
        """测试初始化"""
        metrics = PerformanceMetrics()
        assert metrics.tool_calls == 0
        assert metrics.llm_calls == 0
        assert metrics.total_time_ms == 0.0
        assert metrics.tool_breakdown == {}
        assert metrics.llm_breakdown == []
    
    def test_default_values(self):
        """测试默认值"""
        metrics = PerformanceMetrics()
        assert isinstance(metrics.tool_breakdown, dict)
        assert isinstance(metrics.llm_breakdown, list)


class TestPerformanceMonitor:
    """测试 PerformanceMonitor 类"""
    
    def test_initialization(self):
        """测试初始化"""
        monitor = PerformanceMonitor()
        assert monitor.enabled is True
        assert monitor.metrics.tool_calls == 0
        assert monitor._start_time > 0
    
    def test_disabled_monitor(self):
        """测试禁用监控"""
        monitor = PerformanceMonitor(enabled=False)
        assert monitor.enabled is False
        
        # 禁用状态下应该不记录任何数据
        with monitor.track_tool("test_tool"):
            pass
        
        assert monitor.metrics.tool_calls == 0
    
    def test_track_tool_success(self):
        """测试成功跟踪工具"""
        monitor = PerformanceMonitor()
        
        with monitor.track_tool("test_tool"):
            time.sleep(0.01)  # 等待一小段时间
        
        assert monitor.metrics.tool_calls == 1
        assert monitor.metrics.tool_time_ms > 0
        assert "test_tool" in monitor.metrics.tool_breakdown
        assert monitor.metrics.tool_breakdown["test_tool"]["calls"] == 1
    
    def test_track_tool_error(self):
        """测试跟踪工具错误"""
        monitor = PerformanceMonitor()
        
        with pytest.raises(ValueError):
            with monitor.track_tool("error_tool"):
                raise ValueError("测试错误")
        
        assert monitor.metrics.tool_calls == 1
        assert monitor.metrics.tool_errors == 1
        assert monitor.metrics.tool_breakdown["error_tool"]["errors"] == 1
    
    def test_track_llm(self):
        """测试跟踪 LLM 调用"""
        monitor = PerformanceMonitor()
        
        with monitor.track_llm(model="test-model", prompt_tokens=100):
            time.sleep(0.01)
        
        assert monitor.metrics.llm_calls == 1
        assert monitor.metrics.llm_time_ms > 0
        assert monitor.metrics.prompt_tokens == 100
        assert len(monitor.metrics.llm_breakdown) == 1
        assert monitor.metrics.llm_breakdown[0]["model"] == "test-model"
    
    def test_track_subagent(self):
        """测试跟踪子 Agent"""
        monitor = PerformanceMonitor()
        
        with monitor.track_subagent("test_agent"):
            time.sleep(0.01)
        
        assert monitor.metrics.subagent_calls == 1
        assert monitor.metrics.subagent_time_ms > 0
    
    def test_record_tokens(self):
        """测试记录令牌"""
        monitor = PerformanceMonitor()
        
        monitor.record_tokens(prompt_tokens=50, completion_tokens=30)
        
        assert monitor.metrics.prompt_tokens == 50
        assert monitor.metrics.completion_tokens == 30
        assert monitor.metrics.total_tokens == 80
    
    def test_get_report_enabled(self):
        """测试获取报告（启用状态）"""
        monitor = PerformanceMonitor()

        # 记录一些数据
        with monitor.track_tool("tool1"):
            time.sleep(0.001)
        with monitor.track_llm(model="model1", prompt_tokens=100):
            time.sleep(0.001)

        report = monitor.get_report()

        assert report["enabled"] is True
        assert report["total_calls"]["tools"] == 1
        assert report["total_calls"]["llm"] == 1
        assert report["time_stats_ms"]["total"] >= 0
        assert "performance_score" in report
    
    def test_get_report_disabled(self):
        """测试获取报告（禁用状态）"""
        monitor = PerformanceMonitor(enabled=False)
        
        report = monitor.get_report()
        
        assert report["enabled"] is False
        assert "total_calls" not in report
    
    def test_reset(self):
        """测试重置"""
        monitor = PerformanceMonitor()
        
        with monitor.track_tool("test_tool"):
            pass
        
        assert monitor.metrics.tool_calls == 1
        
        monitor.reset()
        
        assert monitor.metrics.tool_calls == 0
        assert monitor._start_time > 0
    
    def test_save_report(self, tmp_path):
        """测试保存报告到文件"""
        monitor = PerformanceMonitor()
        
        with monitor.track_tool("test_tool"):
            pass
        
        filepath = tmp_path / "report.json"
        monitor.save_report(str(filepath))
        
        assert filepath.exists()
        
        # 验证文件内容
        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert data["enabled"] is True
    
    def test_str_representation(self):
        """测试字符串表示"""
        monitor = PerformanceMonitor()
        
        with monitor.track_tool("test_tool"):
            pass
        
        str_repr = str(monitor)
        assert "PerformanceMonitor" in str_repr
        assert "Calls:" in str_repr
        assert "Time:" in str_repr
    
    def test_calculate_scores(self):
        """测试性能评分计算"""
        monitor = PerformanceMonitor()
        
        # 工具效率评分
        tool_score = monitor._calculate_tool_efficiency_score()
        assert 0 <= tool_score <= 100
        
        # LLM 效率评分
        llm_score = monitor._calculate_llm_efficiency_score()
        assert 0 <= llm_score <= 100
        
        # 总体评分
        overall_score = monitor._calculate_overall_score()
        assert 0 <= overall_score <= 100


class TestGlobalMonitor:
    """测试全局监控器"""
    
    def test_get_global_monitor(self):
        """测试获取全局监控器"""
        from backend.app.monitoring import get_global_monitor
        
        monitor1 = get_global_monitor()
        monitor2 = get_global_monitor()
        
        assert monitor1 is monitor2  # 应该是同一个实例
    
    def test_enable_disable_global_monitoring(self):
        """测试启用/禁用全局监控"""
        from backend.app.monitoring import (
            enable_global_monitoring,
            disable_global_monitoring,
            get_global_monitor
        )
        
        # 启用
        enable_global_monitoring(True)
        monitor = get_global_monitor()
        assert monitor.enabled is True
        
        # 禁用
        disable_global_monitoring()
        assert monitor.enabled is False
        
        # 重新启用
        enable_global_monitoring(True)
        assert monitor.enabled is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])