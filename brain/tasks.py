"""
Lucy's task/to-do system.
Local JSON storage. Supports add, list, complete, edit, delete.
"""

import json
import time
from pathlib import Path

TASKS_FILE = Path.home() / "Lucy" / "memory" / "tasks.json"


def _load() -> list:
    try:
        if TASKS_FILE.exists():
            return json.loads(TASKS_FILE.read_text())
    except Exception:
        pass
    return []


def _save(tasks: list):
    TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TASKS_FILE.write_text(json.dumps(tasks, indent=2))


def add_task(description: str, priority: str = "medium", due: str = "") -> str:
    tasks = _load()
    task = {
        "id": len(tasks) + 1,
        "description": description,
        "priority": priority,
        "due": due,
        "status": "pending",
        "created": time.strftime("%Y-%m-%d %H:%M"),
        "completed_at": "",
    }
    tasks.append(task)
    _save(tasks)
    return f"Added task #{task['id']}: {description}"


def list_tasks(show_completed: bool = False) -> str:
    tasks = _load()
    if not tasks:
        return "No tasks yet. Tell me what you need to do."

    pending = [t for t in tasks if t["status"] == "pending"]
    completed = [t for t in tasks if t["status"] == "completed"]

    lines = []
    if pending:
        lines.append("**Pending tasks:**")
        for t in pending:
            priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(t["priority"], "⚪")
            due_str = f" (due: {t['due']})" if t.get("due") else ""
            lines.append(f"- {priority_icon} **#{t['id']}** {t['description']}{due_str}")
    else:
        lines.append("All tasks completed! Nothing pending.")

    if show_completed and completed:
        lines.append("")
        lines.append("**Completed:**")
        for t in completed:
            lines.append(f"- ✅ ~~#{t['id']} {t['description']}~~")

    lines.append(f"\n*{len(pending)} pending, {len(completed)} completed*")
    return "\n".join(lines)


def complete_task(task_id: int = None, description: str = "") -> str:
    tasks = _load()
    target = None

    if task_id:
        target = next((t for t in tasks if t["id"] == task_id), None)
    elif description:
        desc_lower = description.lower()
        target = next((t for t in tasks if desc_lower in t["description"].lower() and t["status"] == "pending"), None)

    if not target:
        return f"Couldn't find that task. Try 'list my tasks' to see task numbers."

    target["status"] = "completed"
    target["completed_at"] = time.strftime("%Y-%m-%d %H:%M")
    _save(tasks)
    return f"Marked task #{target['id']} as done: {target['description']}"


def delete_task(task_id: int = None, description: str = "") -> str:
    tasks = _load()
    target = None

    if task_id:
        target = next((t for t in tasks if t["id"] == task_id), None)
    elif description:
        desc_lower = description.lower()
        target = next((t for t in tasks if desc_lower in t["description"].lower()), None)

    if not target:
        return f"Couldn't find that task. Try 'list my tasks' to see task numbers."

    tasks.remove(target)
    _save(tasks)
    return f"Deleted task #{target['id']}: {target['description']}"


def edit_task(task_id: int, new_description: str = "", new_priority: str = "", new_due: str = "") -> str:
    tasks = _load()
    target = next((t for t in tasks if t["id"] == task_id), None)

    if not target:
        return f"Couldn't find task #{task_id}."

    changes = []
    if new_description:
        target["description"] = new_description
        changes.append("description")
    if new_priority:
        target["priority"] = new_priority
        changes.append("priority")
    if new_due:
        target["due"] = new_due
        changes.append("due date")

    _save(tasks)
    return f"Updated task #{task_id}: changed {', '.join(changes)}"


# --- Detection ---
TASK_TRIGGERS = [
    "add task", "new task", "create task", "todo",
    "my tasks", "list tasks", "pending tasks", "show tasks", "what tasks",
    "complete task", "mark task", "finish task", "done with",
    "delete task", "remove task",
    "edit task", "update task", "change task",
]


def needs_tasks(text: str) -> bool:
    t = text.lower()
    if any(trigger in t for trigger in TASK_TRIGGERS):
        return True
    words = set(t.split())
    if "task" in words or "tasks" in words or "todo" in words:
        return True
    # Catch typos for delete/complete
    if any(w in t for w in ["dlete", "delet", "complet", "complte"]):
        if "task" in t or "#" in t:
            return True
    return False


def handle_task(text: str) -> str:
    t = text.lower()

    # List tasks
    if any(w in t for w in ["list", "show", "pending", "my tasks", "what tasks", "all tasks"]):
        return list_tasks(show_completed="all" in t or "completed" in t)

    # Complete task
    if any(w in t for w in ["complete", "mark", "finish", "done with"]):
        import re
        num = re.search(r'#?(\d+)', text)
        if num:
            return complete_task(task_id=int(num.group(1)))
        desc = t.replace("complete task", "").replace("mark task", "").replace("finish task", "").replace("done with", "").strip()
        return complete_task(description=desc) if desc else "Which task? Give me the task number or description."

    # Delete task
    if any(w in t for w in ["delete", "remove", "dlete", "delet"]):
        import re
        num = re.search(r'#?(\d+)', text)
        if num:
            return delete_task(task_id=int(num.group(1)))
        desc = t.replace("delete task", "").replace("remove task", "").strip()
        return delete_task(description=desc) if desc else "Which task? Give me the task number or description."

    # Edit/update task
    if any(w in t for w in ["edit", "update", "change"]):
        import re
        num = re.search(r'#?(\d+)', text)
        if num:
            task_id = int(num.group(1))
            # Check if they want to delete instead
            if any(w in t for w in ["delete", "remove", "dlete"]):
                return delete_task(task_id=task_id)
            new_desc = re.sub(r'(?:edit|update|change)\s+(?:task\s+)?#?\d+\s*', '', text, flags=re.IGNORECASE).strip()
            if new_desc:
                return edit_task(task_id, new_description=new_desc)
            return f"What should I change about task #{task_id}?"
        return "Which task? Give me the task number."

    # Add task (default)
    desc = text
    for prefix in ["add task", "new task", "create task", "todo", "add a task", "add task:"]:
        if t.startswith(prefix):
            desc = text[len(prefix):].strip()
            break

    priority = "medium"
    if "high priority" in t or "urgent" in t:
        priority = "high"
    elif "low priority" in t:
        priority = "low"

    due = ""
    import re
    due_match = re.search(r'(?:due|by|before)\s+(.+?)(?:\s*$)', t)
    if due_match:
        due = due_match.group(1).strip()
        desc = re.sub(r'(?:due|by|before)\s+.+$', '', desc, flags=re.IGNORECASE).strip()

    if desc:
        return add_task(desc, priority, due)
    return "What's the task? Tell me what you need to do."
