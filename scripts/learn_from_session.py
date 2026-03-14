#!/usr/bin/env python3
"""
经验学习脚本（LLM 增强版）

用法:
    python scripts/learn_from_session.py .sessions/20260313_165928
    python scripts/learn_from_session.py --latest
    python scripts/learn_from_session.py --all
"""

import sys
import argparse
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.app.llm import get_llm
from backend.app.tools.implementations.experience_learner import LLMEnhancedExperienceLearner


def find_latest_session() -> Path:
    """找到最新的 session 目录"""
    sessions_dir = project_root / ".sessions"
    if not sessions_dir.exists():
        raise FileNotFoundError("未找到 .sessions 目录")

    sessions = sorted(sessions_dir.glob("*"), key=lambda p: p.name, reverse=True)
    if not sessions:
        raise FileNotFoundError("未找到任何 session")

    return sessions[0]


def find_all_sessions() -> list[Path]:
    """找到所有 session 目录"""
    sessions_dir = project_root / ".sessions"
    if not sessions_dir.exists():
        return []

    return sorted(sessions_dir.glob("*"), key=lambda p: p.name, reverse=True)


class SimpleLLMClient:
    """简单的 LLM 客户端包装"""

    def __init__(self):
        self.llm = get_llm(temperature=0.3)

    def generate(self, prompt: str) -> str:
        """生成响应"""
        try:
            response = self.llm.invoke(prompt)
            return response.content
        except Exception as e:
            print(f"⚠️  LLM 调用失败: {e}")
            return ""


def main():
    parser = argparse.ArgumentParser(description="从 session 中学习经验（LLM 增强版）")
    parser.add_argument("session_dir", nargs="?", help="session 目录路径")
    parser.add_argument("--latest", action="store_true", help="分析最新的 session")
    parser.add_argument("--all", action="store_true", help="分析所有 session")
    parser.add_argument("--dry-run", action="store_true", help="只分析不写入")
    parser.add_argument("--no-llm", action="store_true", help="禁用 LLM（降级到规则系统）")

    args = parser.parse_args()

    # 初始化 LLM 客户端
    llm_client = None
    if not args.no_llm:
        print("🤖 初始化 LLM 客户端...")
        try:
            llm_client = SimpleLLMClient()
            print("✅ LLM 客户端就绪")
        except Exception as e:
            print(f"⚠️  LLM 初始化失败: {e}")
            print("⚠️  降级到纯规则系统")

    # 确定要分析的 session
    sessions_to_analyze = []

    if args.all:
        sessions_to_analyze = find_all_sessions()
        print(f"📚 找到 {len(sessions_to_analyze)} 个 session")
    elif args.latest:
        sessions_to_analyze = [find_latest_session()]
        print(f"📂 分析最新 session: {sessions_to_analyze[0].name}")
    elif args.session_dir:
        session_path = Path(args.session_dir)
        if not session_path.is_absolute():
            session_path = project_root / session_path
        sessions_to_analyze = [session_path]
        print(f"📂 分析指定 session: {session_path.name}")
    else:
        parser.print_help()
        return

    # 分析每个 session
    total_patterns = 0
    total_skills = 0
    llm_calls = 0

    for session_dir in sessions_to_analyze:
        print(f"\n{'='*60}")
        print(f"📊 分析 session: {session_dir.name}")
        print(f"{'='*60}")

        learner = LLMEnhancedExperienceLearner(session_dir, llm_client=llm_client)

        # 分析
        result = learner.analyze_session()

        if "error" in result:
            print(f"❌ {result['error']}")
            continue

        print(f"\n任务: {result['task'][:80]}...")
        print(f"状态: {'✅ 成功' if result['success'] else '❌ 失败'}")
        print(f"工具调用: {result['tool_calls']} 次")
        print(f"发现模式: {result['patterns_found']} 个")
        print(f"Skill 候选: {result['skill_candidates']} 个")

        # 写入记忆
        if not args.dry_run:
            print("\n💾 写入记忆文件...")
            learner.write_to_memory()
            print("✅ 已更新记忆文件")

            # 生成 skill
            if result['skill_candidates'] > 0:
                print("\n🎯 生成 Skill...")
                skills_generated = learner._generate_skills()
                print(f"✅ 生成了 {len(skills_generated)} 个 skill")
                total_skills += len(skills_generated)

        total_patterns += result['patterns_found']

    # 总结
    print(f"\n{'='*60}")
    print(f"📈 学习总结")
    print(f"{'='*60}")
    print(f"分析 session 数: {len(sessions_to_analyze)}")
    print(f"提取模式数: {total_patterns}")
    print(f"生成 skill 数: {total_skills}")

    if llm_client:
        print(f"🤖 LLM 调用次数: ~{llm_calls} 次")

    if args.dry_run:
        print("\n⚠️  Dry-run 模式，未写入任何文件")


if __name__ == "__main__":
    main()
