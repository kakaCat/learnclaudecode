#!/usr/bin/env python3
"""
setup.py - 兼容性包装文件

注意：现代 Python 项目应该使用 pyproject.toml 进行配置。
这个文件仅为兼容性目的存在。
"""

from setuptools import setup

# 从 pyproject.toml 读取配置
import tomllib
import os

def read_pyproject():
    """从 pyproject.toml 读取配置"""
    with open("pyproject.toml", "rb") as f:
        return tomllib.load(f)

def main():
    """主设置函数"""
    config = read_pyproject()
    project = config["project"]
    
    setup(
        name=project["name"],
        version=project["version"],
        description=project.get("description", ""),
        long_description=project.get("readme", ""),
        author="LearnClaudeCode Project",
        author_email="",
        python_requires=project["requires-python"],
        install_requires=project["dependencies"],
        extras_require=project.get("optional-dependencies", {}),
        packages=["backend", "backend.app"],
        classifiers=[
            "Development Status :: 3 - Alpha",
            "Intended Audience :: Developers",
            "License :: OSI Approved :: MIT License",
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
        ],
    )

if __name__ == "__main__":
    main()