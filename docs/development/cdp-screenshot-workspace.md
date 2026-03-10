# CDP 截图保存到 Session Workspace

## 功能说明

CDP 工具现在会自动将截图保存到当前 session 的 workspace 目录，避免污染项目根目录。

## 实现逻辑

### 路径解析规则

1. **只有文件名**（如 `screenshot.png`）
   - 自动保存到 session workspace
   - 添加时间戳避免覆盖：`screenshot_20260310_020830.png`
   - 路径示例：`.sessions/{session_key}/workspace/screenshot_20260310_020830.png`

2. **相对路径**（如 `./images/screenshot.png`）
   - 使用指定的相对路径
   - 不会自动保存到 workspace

3. **绝对路径**（如 `/tmp/screenshot.png`）
   - 使用指定的绝对路径
   - 不会自动保存到 workspace

### 代码实现

修改文件：`backend/app/tools/implementations/cdp_tool_improved.py`

关键函数：
```python
def _get_screenshot_path(output_path: str) -> str:
    """
    获取截图保存路径

    如果 output_path 是相对路径且没有指定目录，则保存到 session workspace
    否则使用指定的路径
    """
```

## 使用示例

### 1. 默认使用（推荐）

```python
# 只指定文件名，自动保存到 workspace
cdp_browser(action="screenshot", output_path="screenshot.png")
# 保存到: .sessions/{session_key}/workspace/screenshot_20260310_020830.png
```

### 2. 指定相对路径

```python
# 保存到项目根目录的 images 文件夹
cdp_browser(action="screenshot", output_path="./images/screenshot.png")
```

### 3. 指定绝对路径

```python
# 保存到系统临时目录
cdp_browser(action="screenshot", output_path="/tmp/screenshot.png")
```

## Session Workspace 结构

```
.sessions/
├── 20260309_170139/          # Session 目录
│   ├── workspace/            # 工作空间（截图保存在这里）
│   │   ├── screenshot_20260310_020830.png
│   │   └── research/
│   ├── tasks/                # 任务文件
│   ├── team/                 # 团队协作
│   ├── board/                # 看板
│   └── main.jsonl            # 主对话记录
└── sessions.json             # Session 索引
```

## 优势

1. **自动管理**：截图自动保存到 session workspace，不污染项目根目录
2. **避免覆盖**：自动添加时间戳，避免文件覆盖
3. **灵活控制**：仍然支持指定自定义路径
4. **会话隔离**：不同 session 的截图分开存储
5. **易于清理**：删除 session 时自动清理所有相关文件

## 测试

运行测试脚本：
```bash
python test_cdp_workspace.py
```

## 相关文件

- `backend/app/tools/implementations/cdp_tool_improved.py` - CDP 工具实现
- `backend/app/session/session.py` - Session 管理
- `backend/app/session/constants.py` - Session 路径配置
- `test_cdp_workspace.py` - 测试脚本
