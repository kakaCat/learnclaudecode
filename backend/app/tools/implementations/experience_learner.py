"""
经验学习系统 - LLM 增强版

功能：
1. 从 trace.jsonl 中提取成功模式
2. LLM 智能去重和质量评估
3. 写入记忆文件（TOOLS.md, MEMORY.md）
4. 自动生成可复用的 skill
"""

import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import defaultdict, Counter


class ExperienceLearner:
    """经验学习器基类 - 强化学习式的工具使用优化"""

    def __init__(self, session_dir: Path):
        self.session_dir = Path(session_dir)
        self.trace_file = self.session_dir / "trace.jsonl"
        self.memory_dir = Path(__file__).parent.parent.parent.parent / "memory"

        # 学习结果
        self.tool_sequences = []  # 成功的工具调用序列
        self.tool_patterns = defaultdict(list)  # 工具使用模式
        self.error_patterns = []  # 错误模式（需要避免）
        self.skill_candidates = []  # 可以生成 skill 的模式

    def analyze_session(self) -> Dict[str, Any]:
        """分析整个 session 的执行轨迹"""
        if not self.trace_file.exists():
            return {"error": "trace.jsonl not found"}

        # 读取所有事件
        events = []
        with open(self.trace_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # 提取关键信息
        task_prompt = self._extract_task_prompt(events)
        tool_calls = self._extract_tool_calls(events)
        success = self._is_task_successful(events)

        # 分析工具使用模式
        if success:
            self._analyze_successful_patterns(tool_calls, task_prompt)
        else:
            self._analyze_failed_patterns(tool_calls, task_prompt)

        # 识别可生成 skill 的模式
        self._identify_skill_candidates()

        return {
            "task": task_prompt,
            "success": success,
            "tool_calls": len(tool_calls),
            "patterns_found": len(self.tool_patterns),
            "skill_candidates": len(self.skill_candidates)
        }

    def _extract_task_prompt(self, events: List[Dict]) -> str:
        """提取任务描述"""
        for event in events:
            if event.get("event") == "main_agent.start":
                return event.get("prompt", "")
        return ""

    def _extract_tool_calls(self, events: List[Dict]) -> List[Dict]:
        """提取所有工具调用"""
        tool_calls = []

        for event in events:
            # 直接从 tool_start 事件提取工具调用
            if event.get("event") == "main.tool_start":
                tool_name = event.get("tool", "unknown")
                inputs = event.get("inputs", {})

                tool_calls.append({
                    "tool": tool_name,
                    "timestamp": event.get("ts"),
                    "inputs": inputs,
                    "run_id": event.get("run_id")
                })

        return tool_calls

    def _is_task_successful(self, events: List[Dict]) -> bool:
        """判断任务是否成功"""
        # 检查是否有成功标志
        for event in reversed(events):
            if event.get("event") == "main_agent.end":
                return True
            elif event.get("event") == "main_agent.error":
                return False

        # 检查最后的 LLM 输出
        for event in reversed(events):
            if event.get("event") == "main.llm_end":
                output = event.get("output_preview", "")
                if any(kw in output for kw in ["已完成", "成功", "✅", "完成了"]):
                    return True
                break

        return False

    def _analyze_successful_patterns(self, tool_calls: List[Dict], task: str):
        """分析成功的模式"""
        if not tool_calls:
            return

        # 提取工具序列
        tool_sequence = [call["tool"] for call in tool_calls]

        # 分类任务类型
        task_type = self._classify_task(task)

        # 记录模式
        self.tool_patterns[task_type].append({
            "tool_sequence": tool_sequence,
            "task_keywords": self._extract_keywords(task),
            "success": True
        })

        self.tool_sequences.append(tool_sequence)

    def _analyze_failed_patterns(self, tool_calls: List[Dict], task: str):
        """分析失败的模式"""
        if not tool_calls:
            return

        tool_sequence = [call["tool"] for call in tool_calls]

        self.error_patterns.append({
            "tool_sequence": tool_sequence,
            "task": task,
            "reason": "任务失败"
        })

    def _classify_task(self, task: str) -> str:
        """分类任务类型"""
        task_lower = task.lower()

        if any(kw in task_lower for kw in ["机票", "航班", "酒店", "预订"]):
            return "web_query"
        elif any(kw in task_lower for kw in ["网页", "html", "展示"]):
            return "content_generation"
        elif any(kw in task_lower for kw in ["开发", "实现", "构建", "系统"]):
            return "system_development"
        elif any(kw in task_lower for kw in ["查询", "搜索", "什么是"]):
            return "information_search"
        else:
            return "general"

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词"""
        keywords = []
        for word in ["机票", "航班", "酒店", "网页", "查询", "开发", "实现"]:
            if word in text:
                keywords.append(word)
        return keywords

    def _identify_skill_candidates(self):
        """识别可以生成 skill 的模式"""
        for task_type, patterns in self.tool_patterns.items():
            if not patterns:
                continue

            # 策略1: 重复出现的模式（至少2次）
            if len(patterns) >= 2:
                sequences = [tuple(p["tool_sequence"]) for p in patterns]
                most_common = Counter(sequences).most_common(1)

                if most_common and most_common[0][1] >= 2:
                    self.skill_candidates.append({
                        "task_type": task_type,
                        "tool_sequence": list(most_common[0][0]),
                        "frequency": most_common[0][1],
                        "patterns": patterns,
                        "reason": "重复模式"
                    })

            # 策略2: 单次但复杂的成功模式（工具调用 >= 3 次）
            elif len(patterns) == 1:
                pattern = patterns[0]
                if len(pattern["tool_sequence"]) >= 3:
                    if "spawn_subagent" in pattern["tool_sequence"]:
                        self.skill_candidates.append({
                            "task_type": task_type,
                            "tool_sequence": pattern["tool_sequence"],
                            "frequency": 1,
                            "patterns": patterns,
                            "reason": "复杂单次成功"
                        })

    def write_to_memory(self):
        """将学习结果写入记忆文件"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._update_tools_memory(timestamp)
        self._update_general_memory(timestamp)

    def _update_tools_memory(self, timestamp: str):
        """更新 TOOLS.md"""
        tools_file = self.memory_dir / "TOOLS.md"
        if not tools_file.exists():
            return

        content = tools_file.read_text(encoding='utf-8')
        new_entries = []

        for task_type, patterns in self.tool_patterns.items():
            if not patterns:
                continue

            sequences = [tuple(p["tool_sequence"]) for p in patterns]
            most_common = Counter(sequences).most_common(1)

            if most_common:
                tool_seq = " → ".join(most_common[0][0])
                keywords = patterns[0].get("task_keywords", [])

                entry = f"\n### {task_type.replace('_', ' ').title()} 任务\n\n"
                entry += f"**关键词**: {', '.join(keywords)}\n\n"
                entry += f"**推荐工具序列**: {tool_seq}\n\n"
                entry += f"**成功次数**: {most_common[0][1]}\n\n"

                new_entries.append(entry)

        if new_entries:
            section = f"\n\n## 强化学习经验 ({timestamp})\n\n"
            section += "".join(new_entries)
            content += section
            tools_file.write_text(content, encoding='utf-8')

    def _update_general_memory(self, timestamp: str):
        """更新 MEMORY.md"""
        memory_file = self.memory_dir / "MEMORY.md"
        if not memory_file.exists():
            return

        content = memory_file.read_text(encoding='utf-8')

        summary = f"\n## {timestamp}\n\n"
        summary += f"**本次学习**: 分析了 {len(self.tool_sequences)} 个工具调用序列\n\n"

        if self.tool_patterns:
            summary += "**成功模式**:\n"
            for task_type, patterns in self.tool_patterns.items():
                summary += f"- {task_type}: {len(patterns)} 次成功\n"

        if self.skill_candidates:
            summary += f"\n**可生成技能**: {len(self.skill_candidates)} 个候选\n"

        content += summary
        memory_file.write_text(content, encoding='utf-8')

    def _generate_skills(self) -> List[str]:
        """生成 skill 文件"""
        skills_dir = Path(__file__).parent.parent.parent.parent.parent / ".skills"
        skills_dir.mkdir(exist_ok=True)

        generated = []
        for candidate in self.skill_candidates:
            # TODO: 实现 skill 生成逻辑
            pass

        return generated


class LLMEnhancedExperienceLearner(ExperienceLearner):
    """LLM 增强的经验学习器"""

    def __init__(self, session_dir: Path, llm_client=None):
        super().__init__(session_dir)
        self.llm_client = llm_client

    def _evaluate_pattern_quality(self, pattern: Dict) -> Dict:
        """评估模式质量"""
        if not self.llm_client:
            return {
                "should_record": len(pattern["tool_sequence"]) >= 2,
                "reason": "工具调用数量足够",
                "summary": f"{pattern.get('task_type', 'unknown')} 任务模式",
                "optimization_hints": []
            }

        prompt = f"""分析这个工具使用模式的价值：

任务类型: {pattern.get('task_type', 'unknown')}
任务描述: {pattern.get('task_keywords', [])}
工具序列: {' → '.join(pattern['tool_sequence'])}
成功: {pattern.get('success', False)}

评估标准：
1. 通用性：这个模式是否可以应用到类似任务？
2. 效率：工具使用是否合理，有无冗余？
3. 价值：是否值得记录到记忆中？

请只返回 JSON，不要有任何其他文字：
{{
    "should_record": true,
    "reason": "评估原因",
    "summary": "一句话总结这个模式",
    "optimization_hints": ["优化建议1", "优化建议2"]
}}"""

        try:
            response = self.llm_client.generate(prompt)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
            elif '```' in response:
                response = response.replace('```json', '').replace('```', '').strip()

            return json.loads(response)
        except Exception as e:
            print(f"LLM 评估失败: {e}")
            return {"should_record": True, "reason": "LLM 评估失败，默认记录"}

    def _check_duplicate_in_memory(self, pattern: Dict) -> Optional[str]:
        """检查记忆中是否已有类似模式"""
        if not self.llm_client:
            return None

        tools_file = self.memory_dir / "TOOLS.md"
        if not tools_file.exists():
            return None

        content = tools_file.read_text(encoding='utf-8')
        recent_entries = self._extract_recent_entries(content, limit=10)

        if not recent_entries:
            return None

        prompt = f"""判断新模式是否与已有记录重复：

新模式：
- 任务类型: {pattern.get('task_type', 'unknown')}
- 工具序列: {' → '.join(pattern['tool_sequence'])}
- 关键词: {pattern.get('task_keywords', [])}

已有记录：
{recent_entries}

判断：
1. 是否重复？（工具序列相同或高度相似）
2. 如果重复，应该如何处理？

请只返回 JSON，不要有任何其他文字：
{{
    "is_duplicate": true,
    "action": "skip",
    "reason": "判断理由"
}}"""

        try:
            response = self.llm_client.generate(prompt)
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                response = json_match.group(1)
            elif '```' in response:
                response = response.replace('```json', '').replace('```', '').strip()

            result = json.loads(response)
            return result.get("action", "append")
        except Exception as e:
            print(f"去重检查失败: {e}")
            return "append"

    def _extract_recent_entries(self, content: str, limit: int = 10) -> str:
        """提取最近的经验记录"""
        lines = content.split('\n')
        entries = []
        current_entry = []

        for line in lines:
            if line.startswith('## 强化学习经验'):
                if current_entry:
                    entries.append('\n'.join(current_entry))
                current_entry = [line]
            elif current_entry:
                current_entry.append(line)

        if current_entry:
            entries.append('\n'.join(current_entry))

        return '\n\n'.join(entries[-limit:])

    def _generate_memory_summary(self, patterns: List[Dict]) -> str:
        """生成记忆总结"""
        if not self.llm_client:
            return self._generate_template_summary(patterns)

        prompt = f"""基于这些成功案例，生成一条记忆条目：

案例数量: {len(patterns)}
案例详情:
{json.dumps(patterns, ensure_ascii=False, indent=2)}

要求：
1. 提炼共同的成功要素
2. 给出具体、可操作的建议
3. 标注适用场景和限制条件
4. 使用 Markdown 格式

格式示例：
### 场景名称

**适用场景**: 描述什么情况下使用

**推荐做法**:
1. 步骤1
2. 步骤2

**注意事项**:
- 注意点1
- 注意点2

**成功案例**: X 次
"""

        try:
            response = self.llm_client.generate(prompt)
            return response
        except Exception as e:
            print(f"LLM 总结失败: {e}")
            return self._generate_template_summary(patterns)

    def _generate_template_summary(self, patterns: List[Dict]) -> str:
        """模板生成（降级方案）"""
        if not patterns:
            return ""

        pattern = patterns[0]
        task_type = pattern.get('task_type', 'unknown').replace('_', ' ').title()
        keywords = ', '.join(pattern.get('task_keywords', []))
        tool_seq = ' → '.join(pattern['tool_sequence'])

        return f"""### {task_type} 任务

**关键词**: {keywords}

**推荐工具序列**: {tool_seq}

**成功次数**: {len(patterns)}
"""

    def write_to_memory(self):
        """智能写入记忆（带质量评估和去重）"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 评估每个模式的质量
        valuable_patterns = {}
        for task_type, patterns in self.tool_patterns.items():
            for pattern in patterns:
                pattern['task_type'] = task_type
                evaluation = self._evaluate_pattern_quality(pattern)

                if evaluation.get("should_record", True):
                    action = self._check_duplicate_in_memory(pattern)

                    if action == "skip":
                        print(f"  跳过重复模式: {task_type}")
                        continue

                    if task_type not in valuable_patterns:
                        valuable_patterns[task_type] = []
                    valuable_patterns[task_type].append({
                        **pattern,
                        "evaluation": evaluation
                    })

        # 只写入有价值的模式
        if valuable_patterns:
            self._update_tools_memory_smart(timestamp, valuable_patterns)
            self._update_general_memory(timestamp)
            print(f"  记录了 {len(valuable_patterns)} 个有价值的模式")
        else:
            print("  没有发现值得记录的新模式")

    def _update_tools_memory_smart(self, timestamp: str, patterns: Dict):
        """智能更新 TOOLS.md"""
        tools_file = self.memory_dir / "TOOLS.md"

        if not tools_file.exists():
            return

        content = tools_file.read_text(encoding='utf-8')

        # 生成新条目
        summary = self._generate_memory_summary(list(patterns.values())[0])
        section = f"\n\n## 强化学习经验 ({timestamp})\n\n{summary}\n"

        content += section
        tools_file.write_text(content, encoding='utf-8')
