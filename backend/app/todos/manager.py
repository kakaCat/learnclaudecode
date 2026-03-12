class TodoManager:
    def __init__(self):
        self.items = []

    def update(self, items: list) -> str:
        """验证并更新 todo 列表，返回渲染结果。"""
        validated = []
        in_progress_count = 0
        for i, item in enumerate(items):
            content = str(item.get("content", "")).strip()
            status = str(item.get("status", "pending")).lower()
            active_form = str(item.get("activeForm", "") or item.get("active_form", "")).strip() or content
            if not content:
                raise ValueError(f"Item {i}: content required")
            if status not in ("pending", "in_progress", "completed"):
                raise ValueError(f"Item {i}: invalid status '{status}'")
            if status == "in_progress":
                in_progress_count += 1
            validated.append({"content": content, "status": status, "activeForm": active_form})
        if len(validated) > 20:
            raise ValueError("Max 20 todos allowed")
        if in_progress_count > 1:
            raise ValueError("Only one task can be in_progress at a time")
        self.items = validated
        return self.render()

    def render(self) -> str:
        """将 todo 列表渲染为可读文本。

        格式:
            [x] 已完成任务
            [>] 进行中任务 <- 正在做某事...
            [ ] 待开始任务

            (2/3 completed)
        """
        if not self.items:
            return "No todos."
        lines = []
        for item in self.items:
            if item["status"] == "completed":
                lines.append(f"[x] {item['content']}")
            elif item["status"] == "in_progress":
                lines.append(f"[>] {item['content']} <- {item['activeForm']}")
            else:
                lines.append(f"[ ] {item['content']}")
        completed = sum(1 for t in self.items if t["status"] == "completed")
        lines.append(f"\n({completed}/{len(self.items)} completed)")
        return "\n".join(lines)
