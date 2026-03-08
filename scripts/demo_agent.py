#!/usr/bin/env python3
"""
外部监控演示 - 展示各种监控方案的工作原理
"""

import time
import sys
import random


def simulate_normal_agent():
    """模拟正常运行的 Agent"""
    print("[Agent] 启动成功")
    for i in range(10):
        print(f"[Agent] 正在处理任务 {i+1}/10...")
        time.sleep(2)
    print("[Agent] 正常退出")
    sys.exit(0)


def simulate_crash_agent():
    """模拟崩溃的 Agent"""
    print("[Agent] 启动成功")
    for i in range(3):
        print(f"[Agent] 正在处理任务 {i+1}...")
        time.sleep(1)
    print("[Agent] ❌ 发生致命错误！")
    raise Exception("模拟崩溃")


def simulate_quick_crash():
    """模拟快速崩溃"""
    print("[Agent] 启动失败")
    time.sleep(0.5)
    sys.exit(1)


def simulate_random_behavior():
    """模拟随机行为"""
    behavior = random.choice(['normal', 'crash', 'quick_crash'])

    if behavior == 'normal':
        simulate_normal_agent()
    elif behavior == 'crash':
        simulate_crash_agent()
    else:
        simulate_quick_crash()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else 'normal'

    print(f"[演示] 模式: {mode}")

    if mode == 'normal':
        simulate_normal_agent()
    elif mode == 'crash':
        simulate_crash_agent()
    elif mode == 'quick_crash':
        simulate_quick_crash()
    elif mode == 'random':
        simulate_random_behavior()
    else:
        print(f"未知模式: {mode}")
        sys.exit(1)
