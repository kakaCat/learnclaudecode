"""
增强工具系统 (tools_enhanced.py)

提供工具版本管理、依赖跟踪、性能分析和装饰器增强功能。
这是一个可选模块，不影响现有工具系统。

功能：
1. 工具装饰器增强（版本、分类、依赖）
2. 工具性能分析
3. 工具依赖关系跟踪
4. 工具注册表管理
5. 工具使用统计

使用示例：
    @tool_with_metadata(
        name="read_file",
        version="2.0.0",
        category="file_operations",
        dependencies=["os", "pathlib"]
    )
    def read_file(path: str) -> str:
        ...
"""

import time
import inspect
import functools
from typing import Dict, Any, Optional, List, Callable, Type, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from collections import defaultdict


class ToolCategory(str, Enum):
    """工具分类枚举"""
    FILE_OPERATIONS = "file_operations"
    NETWORK = "network"
    SYSTEM = "system"
    DATA_PROCESSING = "data_processing"
    AI_ML = "ai_ml"
    UTILITY = "utility"
    DEBUGGING = "debugging"
    TESTING = "testing"


@dataclass
class ToolMetadata:
    """工具元数据"""
    
    name: str
    version: str = "1.0.0"
    description: str = ""
    category: ToolCategory = ToolCategory.UTILITY
    dependencies: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    last_modified: datetime = field(default_factory=datetime.now)
    author: str = "system"
    
    # 性能指标
    call_count: int = 0
    total_execution_time: float = 0.0
    error_count: int = 0
    last_called: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "category": self.category.value,
            "dependencies": self.dependencies,
            "created_at": self.created_at.isoformat(),
            "last_modified": self.last_modified.isoformat(),
            "author": self.author,
            "stats": {
                "call_count": self.call_count,
                "total_execution_time": round(self.total_execution_time, 4),
                "avg_execution_time": round(
                    self.total_execution_time / self.call_count if self.call_count > 0 else 0, 4
                ),
                "error_count": self.error_count,
                "error_rate": round(
                    self.error_count / self.call_count * 100 if self.call_count > 0 else 0, 2
                ),
                "last_called": self.last_called.isoformat() if self.last_called else None
            }
        }


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self._tools: Dict[str, ToolMetadata] = {}
        self._tool_functions: Dict[str, Callable] = {}
        self._category_index: Dict[ToolCategory, List[str]] = defaultdict(list)
        self._dependency_graph: Dict[str, List[str]] = defaultdict(list)
        
    def register(self, func: Callable, metadata: ToolMetadata) -> Callable:
        """注册工具"""
        tool_name = metadata.name
        
        if tool_name in self._tools:
            # 更新现有工具
            existing = self._tools[tool_name]
            if existing.version != metadata.version:
                existing.version = metadata.version
                existing.last_modified = datetime.now()
                existing.description = metadata.description or existing.description
                existing.category = metadata.category or existing.category
                existing.dependencies = metadata.dependencies or existing.dependencies
        else:
            # 注册新工具
            self._tools[tool_name] = metadata
        
        # 更新索引
        self._category_index[metadata.category].append(tool_name)
        
        # 更新依赖图
        for dep in metadata.dependencies:
            self._dependency_graph[tool_name].append(dep)
        
        # 存储函数引用
        self._tool_functions[tool_name] = func
        
        return func
    
    def get_tool(self, name: str) -> Optional[Callable]:
        """获取工具函数"""
        return self._tool_functions.get(name)
    
    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        """获取工具元数据"""
        return self._tools.get(name)
    
    def list_tools(self, category: Optional[ToolCategory] = None) -> List[Dict[str, Any]]:
        """列出工具"""
        if category:
            tool_names = self._category_index.get(category, [])
        else:
            tool_names = list(self._tools.keys())
        
        return [
            self._tools[name].to_dict()
            for name in sorted(tool_names)
        ]
    
    def record_call(self, tool_name: str, execution_time: float, success: bool = True):
        """记录工具调用"""
        if tool_name in self._tools:
            metadata = self._tools[tool_name]
            metadata.call_count += 1
            metadata.total_execution_time += execution_time
            metadata.last_called = datetime.now()
            if not success:
                metadata.error_count += 1
    
    def get_dependencies(self, tool_name: str) -> List[str]:
        """获取工具依赖"""
        return self._dependency_graph.get(tool_name, [])
    
    def get_dependents(self, tool_name: str) -> List[str]:
        """获取依赖此工具的其他工具"""
        dependents = []
        for tool, deps in self._dependency_graph.items():
            if tool_name in deps:
                dependents.append(tool)
        return dependents
    
    def validate_dependencies(self, tool_name: str) -> tuple[bool, List[str]]:
        """验证工具依赖是否满足"""
        missing = []
        for dep in self.get_dependencies(tool_name):
            if dep not in self._tools:
                missing.append(dep)
        return len(missing) == 0, missing
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total_calls = sum(t.call_count for t in self._tools.values())
        total_errors = sum(t.error_count for t in self._tools.values())
        total_time = sum(t.total_execution_time for t in self._tools.values())
        
        # 按分类统计
        category_stats = {}
        for category in ToolCategory:
            tools_in_category = [
                t for t in self._tools.values() 
                if t.category == category
            ]
            if tools_in_category:
                category_stats[category.value] = {
                    "count": len(tools_in_category),
                    "calls": sum(t.call_count for t in tools_in_category),
                    "errors": sum(t.error_count for t in tools_in_category),
                    "total_time": sum(t.total_execution_time for t in tools_in_category)
                }
        
        # 最常用工具
        most_used = sorted(
            self._tools.values(),
            key=lambda t: t.call_count,
            reverse=True
        )[:5]
        
        # 最慢工具
        slowest = sorted(
            [
                t for t in self._tools.values() 
                if t.call_count > 0
            ],
            key=lambda t: t.total_execution_time / t.call_count,
            reverse=True
        )[:5]
        
        return {
            "total_tools": len(self._tools),
            "total_calls": total_calls,
            "total_errors": total_errors,
            "total_execution_time": round(total_time, 4),
            "error_rate": round(total_errors / total_calls * 100 if total_calls > 0 else 0, 2),
            "avg_call_time": round(total_time / total_calls if total_calls > 0 else 0, 4),
            "categories": category_stats,
            "most_used": [t.to_dict() for t in most_used],
            "slowest": [t.to_dict() for t in slowest]
        }
    
    def save_registry(self, filepath: str):
        """保存注册表到文件"""
        data = {
            "tools": {name: metadata.to_dict() for name, metadata in self._tools.items()},
            "statistics": self.get_statistics(),
            "exported_at": datetime.now().isoformat()
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_registry(self, filepath: str):
        """从文件加载注册表"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 注意：这只会加载元数据，不会重新注册函数
            for name, metadata_dict in data.get("tools", {}).items():
                metadata = ToolMetadata(
                    name=name,
                    version=metadata_dict.get("version", "1.0.0"),
                    description=metadata_dict.get("description", ""),
                    category=ToolCategory(metadata_dict.get("category", "utility")),
                    dependencies=metadata_dict.get("dependencies", []),
                    created_at=datetime.fromisoformat(metadata_dict.get("created_at")),
                    last_modified=datetime.fromisoformat(metadata_dict.get("last_modified")),
                    author=metadata_dict.get("author", "system"),
                    call_count=metadata_dict.get("stats", {}).get("call_count", 0),
                    total_execution_time=metadata_dict.get("stats", {}).get("total_execution_time", 0.0),
                    error_count=metadata_dict.get("stats", {}).get("error_count", 0),
                    last_called=(
                        datetime.fromisoformat(metadata_dict.get("stats", {}).get("last_called"))
                        if metadata_dict.get("stats", {}).get("last_called")
                        else None
                    )
                )
                self._tools[name] = metadata
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"加载注册表失败: {e}")


# 全局注册表实例
_registry = ToolRegistry()


def tool_with_metadata(
    name: str,
    version: str = "1.0.0",
    description: str = "",
    category: ToolCategory = ToolCategory.UTILITY,
    dependencies: Optional[List[str]] = None,
    author: str = "system"
):
    """
    工具装饰器增强版
    
    使用示例:
        @tool_with_metadata(
            name="read_file",
            version="2.0.0",
            description="读取文件内容",
            category=ToolCategory.FILE_OPERATIONS,
            dependencies=["os", "pathlib"]
        )
        def read_file(path: str) -> str:
            ...
    """
    def decorator(func: Callable):
        # 创建元数据
        metadata = ToolMetadata(
            name=name,
            version=version,
            description=description or func.__doc__ or "",
            category=category,
            dependencies=dependencies or [],
            author=author
        )
        
        # 注册工具
        _registry.register(func, metadata)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                # 验证依赖
                deps_ok, missing = _registry.validate_dependencies(name)
                if not deps_ok:
                    raise ImportError(f"工具 '{name}' 缺少依赖: {missing}")
                
                # 执行函数
                result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                success = False
                raise
            finally:
                # 记录调用
                execution_time = time.time() - start_time
                _registry.record_call(name, execution_time, success)
        
        return wrapper
    
    return decorator


def track_tool_performance(func: Callable):
    """
    性能跟踪装饰器（简化版）
    
    只跟踪性能，不处理元数据
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            execution_time = time.time() - start_time
            # 这里可以记录到监控系统
            print(f"工具 {func.__name__} 执行时间: {execution_time:.4f}秒")
    
    return wrapper


def get_tool_registry() -> ToolRegistry:
    """获取工具注册表"""
    return _registry


def list_all_tools() -> List[Dict[str, Any]]:
    """列出所有工具"""
    return _registry.list_tools()


def get_tool_statistics() -> Dict[str, Any]:
    """获取工具统计信息"""
    return _registry.get_statistics()


def validate_tool_dependencies() -> Dict[str, List[str]]:
    """验证所有工具的依赖"""
    results = {}
    for tool_name in _registry._tools.keys():
        deps_ok, missing = _registry.validate_dependencies(tool_name)
        if not deps_ok:
            results[tool_name] = missing
    return results


# 示例工具定义（演示用法）
if __name__ == "__main__":
    # 示例工具 1
    @tool_with_metadata(
        name="calculate_sum",
        version="1.0.0",
        description="计算数字列表的总和",
        category=ToolCategory.DATA_PROCESSING,
        dependencies=["math"]
    )
    def calculate_sum(numbers: List[float]) -> float:
        """计算数字列表的总和"""
        return sum(numbers)
    
    # 示例工具 2
    @tool_with_metadata(
        name="format_text",
        version="1.1.0",
        description="格式化文本",
        category=ToolCategory.UTILITY,
        dependencies=["re", "string"]
    )
    def format_text(text: str, uppercase: bool = False) -> str:
        """格式化文本"""
        result = text.strip()
        if uppercase:
            result = result.upper()
        return result
    
    # 测试工具调用
    print("测试工具调用...")
    result1 = calculate_sum([1, 2, 3, 4, 5])
    print(f"calculate_sum([1,2,3,4,5]) = {result1}")
    
    result2 = format_text("  hello world  ", uppercase=True)
    print(f"format_text('  hello world  ', uppercase=True) = {result2}")
    
    # 显示统计信息
    print("\n工具统计信息:")
    stats = get_tool_statistics()
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    # 列出所有工具
    print("\n所有工具:")
    tools = list_all_tools()
    for tool in tools:
        print(f"  - {tool['name']} v{tool['version']} ({tool['category']})")