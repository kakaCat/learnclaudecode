✅ 已加载 46 个工具
# Subagent 可用工具列表

总计: **40** 个工具

## 文件操作 (7)

| 工具名称 | 描述 |
|---------|------|
| `append_file` | Append content to a file. Creates file and parent directories if needed. Use for... |
| `edit_file` | Replace exact text in a file. old_text must match verbatim. |
| `glob` | Find files matching a glob pattern. Examples: '**/*.py', 'src/**/*.ts', '*.md' |
| `grep` | Search for a regex pattern in files. Returns file:line:content matches. |
| `list_dir` | List directory contents with file sizes and types. |
| `read_file` | Read file contents with line numbers. offset=start line (1-based), limit=max lin... |
| `write_file` | Write content to a file. Creates parent directories if needed. Use for new files... |

## 记忆管理 (3)

| 工具名称 | 描述 |
|---------|------|
| `memory_append` | Append content to an existing memory entry (for incremental memory building). |
| `memory_search` | Search stored memories for relevant information, ranked by similarity. |
| `memory_write` | Save an important fact or observation to memory (auto-layered storage). |

## 工作空间 (4)

| 工具名称 | 描述 |
|---------|------|
| `workspace_append` | Append content to a file in the session workspace. Creates file if it doesn't ex... |
| `workspace_list` | List all files in the session workspace. |
| `workspace_read` | Read a file from the session workspace. |
| `workspace_write` | Write a file to the session workspace (for AI intermediate outputs). Path is rel... |

## 执行 (4)

| 工具名称 | 描述 |
|---------|------|
| `background_agent` | Run a subagent task in a background thread. Returns task_id immediately without ... |
| `background_run` | Run a shell command in a background thread. Returns task_id immediately without ... |
| `bash` | Run a shell command. Use for: git, npm, python, running tests. NOT for file expl... |
| `check_background` | Check background task status. Omit task_id to list all tasks. |

## 网络/浏览器 (2)

| 工具名称 | 描述 |
|---------|------|
| `cdp_browser` | Control browser via Chrome DevTools Protocol. |
| `curl` | Execute a curl command to make HTTP requests. |

## 任务管理 (1)

| 工具名称 | 描述 |
|---------|------|
| `TodoWrite` | 更新当前会话的临时任务列表（会话结束后消失）。每个条目需要：content（内容字符串）、status（pending|in_progress|complete... |

## 团队协作 (9)

| 工具名称 | 描述 |
|---------|------|
| `broadcast` | Send a message to all teammates. |
| `check_shutdown_status` | Check the status of a shutdown request by request_id. |
| `claim_task` | Claim a task from the shared board by ID. |
| `idle` | Enter idle state (for lead -- rarely used). |
| `list_teammates` | List all teammates with their name, role, and current status. |
| `plan_approval` | Approve or reject a teammate's submitted plan. Provide request_id and approve=Tr... |
| `read_inbox` | Read and drain the lead's inbox. Returns all pending messages as JSON. |
| `send_message` | Send a message to a teammate's inbox. msg_type: message, broadcast, shutdown_req... |
| `shutdown_request` | Request a teammate to shut down gracefully. Returns a request_id for tracking. |

## Worktree (8)

| 工具名称 | 描述 |
|---------|------|
| `task_bind_worktree` | 将任务绑定到 worktree 名称，可选设置 owner。 |
| `worktree_create` | 创建 git worktree，可选绑定到任务 ID。name 只能包含字母、数字、.、_、-（最多40字符）。 |
| `worktree_events` | 列出最近的 worktree/任务生命周期事件（来自 .worktrees/events.jsonl）。 |
| `worktree_keep` | 将 worktree 标记为 kept 状态（不删除，仅更新生命周期索引）。 |
| `worktree_list` | 列出 .worktrees/index.json 中跟踪的所有 worktree。 |
| `worktree_remove` | 删除 worktree，可选将绑定任务标记为已完成。 |
| `worktree_run` | 在指定 worktree 目录中运行 shell 命令。 |
| `worktree_status` | 显示指定 worktree 的 git status。 |

## 技能 (1)

| 工具名称 | 描述 |
|---------|------|
| `load_skill` | Load specialized knowledge by name. Call this before tackling unfamiliar topics. |

## 系统 (1)

| 工具名称 | 描述 |
|---------|------|
| `compact` | Trigger manual conversation compression to free up context. |

