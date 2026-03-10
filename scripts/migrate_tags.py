#!/usr/bin/env python3
"""批量将 agent_scope 属性迁移到 tags 参数"""
import re
from pathlib import Path

def migrate_file(filepath: Path):
    """迁移单个文件"""
    content = filepath.read_text()
    original = content

    # 查找所有 .agent_scope = "xxx" 的行
    scope_pattern = r'(\w+)\.agent_scope = "(both|main|subagent)"'
    scopes = {}
    for match in re.finditer(scope_pattern, content):
        tool_name = match.group(1)
        scope_value = match.group(2)
        scopes[tool_name] = scope_value

    if not scopes:
        return False

    # 替换 @tool 为 @tool(tags=["xxx"])
    for tool_name, scope_value in scopes.items():
        # 查找对应的 @tool 装饰器
        pattern = rf'(@tool)\ndef {tool_name}\('
        replacement = rf'@tool(tags=["{scope_value}"])\ndef {tool_name}('
        content = re.sub(pattern, replacement, content)

    # 删除 .agent_scope = "xxx" 行（包括前面的注释）
    content = re.sub(r'\n# 标记为.*\n\w+\.agent_scope = "(both|main|subagent)"', '', content)
    content = re.sub(r'\n\w+\.agent_scope = "(both|main|subagent)"', '', content)

    if content != original:
        filepath.write_text(content)
        print(f"✅ {filepath.name}: 迁移了 {len(scopes)} 个工具")
        return True
    return False

# 处理所有工具文件
impl_dir = Path("backend/app/tools/implementations")
count = 0
for file in impl_dir.glob("*.py"):
    if migrate_file(file):
        count += 1

print(f"\n总计迁移了 {count} 个文件")
