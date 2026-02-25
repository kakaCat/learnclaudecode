from backend.app.tools.file_tool import bash, read_file, write_file, edit_file
from backend.app.tools.explore_tool import glob, grep, list_dir
from backend.app.tools.skill_tool import load_skill
from backend.app.tools.compact_tool import compact
from backend.app.tools.task_tool import task_create, task_get, task_update, task_list
from backend.app.tools.background_tool import background_run, background_agent, check_background
from backend.app.tools.team_tool import (spawn_teammate, list_teammates, send_message, read_inbox,
                                          broadcast, shutdown_request, check_shutdown_status, plan_approval,
                                          idle, claim_task)
from backend.app.tools.workspace_tool import workspace_write, workspace_read, workspace_list
from backend.app.tools.todo_tool import TodoWrite
from backend.app.tools.worktree_tool import (task_bind_worktree, worktree_create, worktree_list,
                                              worktree_status, worktree_run, worktree_remove,
                                              worktree_keep, worktree_events)
from backend.app.tools_manager import tools_manager

tools_manager.register(
    bash, read_file, write_file, edit_file,
    glob, grep, list_dir,
    load_skill, compact, TodoWrite,
    task_create, task_get, task_update, task_list, task_bind_worktree,
    background_run, background_agent, check_background,
    spawn_teammate, list_teammates, send_message, read_inbox, broadcast,
    shutdown_request, check_shutdown_status, plan_approval, idle, claim_task,
    workspace_write, workspace_read, workspace_list,
    worktree_create, worktree_list, worktree_status, worktree_run,
    worktree_remove, worktree_keep, worktree_events,
).build_task_tool()

# 向后兼容
TOOLS = tools_manager.get_tools()
TOOLS_MAP = tools_manager.tools_map
