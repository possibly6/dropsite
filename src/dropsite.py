"""
🔻 DropSite — The dead drop for your AI agents.

Filesystem-based agent communication protocol.
No APIs. No message queues. No dependencies. Just folders and JSON.
"""

import json
import os
import time
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional, Callable, Any


# ═══════════════════════════════════════════
#  TASK
# ═══════════════════════════════════════════

@dataclass
class Task:
    id: str
    title: str
    created_by: str
    status: str = "pending"
    description: str = ""
    assigned_to: Optional[str] = None
    priority: int = 5
    context: dict = field(default_factory=dict)
    result: Optional[dict] = None
    tags: list = field(default_factory=list)
    parent_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = ""
    updated_at: str = ""
    history: list = field(default_factory=list)

    def __post_init__(self):
        now = datetime.now(timezone.utc).isoformat()
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def log(self, status, **extra):
        entry = {"status": status, "at": datetime.now(timezone.utc).isoformat(), **extra}
        self.history.append(entry)
        self.status = status
        self.updated_at = entry["at"]


# ═══════════════════════════════════════════
#  TASK BUILDER
# ═══════════════════════════════════════════

class TaskBuilder:
    def __init__(self, title: str, created_by: str):
        self._data = {
            "id": uuid.uuid4().hex,
            "title": title,
            "created_by": created_by,
        }

    def describe(self, desc: str):
        self._data["description"] = desc
        return self

    def assign(self, agent: str):
        self._data["assigned_to"] = agent
        return self

    def priority(self, p: int):
        self._data["priority"] = p
        return self

    def context(self, ctx: dict):
        self._data["context"] = ctx
        return self

    def tag(self, *tags: str):
        self._data.setdefault("tags", []).extend(tags)
        return self

    def parent(self, parent_id: str):
        self._data["parent_id"] = parent_id
        return self

    def max_retries(self, n: int):
        self._data["max_retries"] = n
        return self

    def build(self) -> Task:
        task = Task(**self._data)
        task.log("pending")
        return task


# ═══════════════════════════════════════════
#  DROP SITE
# ═══════════════════════════════════════════

class DropSite:
    """Filesystem-based agent communication hub."""

    TASK_DIRS = ["inbox", "active", "done", "failed", "blocked", "feedback"]
    META_DIRS = ["agents"]
    DIRS = TASK_DIRS + META_DIRS

    def __init__(self, workspace: str):
        self.workspace = Path(workspace)
        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in self.DIRS:
            (self.workspace / d).mkdir(parents=True, exist_ok=True)

    def _path(self, folder: str, task_id: str) -> Path:
        return self.workspace / folder / f"{task_id}.json"

    def _write(self, folder: str, task: Task):
        path = self._path(folder, task.id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(task.to_dict(), indent=2, default=str))
        tmp.rename(path)  # atomic on POSIX

    def _read(self, path: Path) -> Task:
        return Task.from_dict(json.loads(path.read_text()))

    def _move(self, task: Task, from_dir: str, to_dir: str):
        """Atomically move a task between folders.
        
        Updates the task JSON in the source file, then uses replace()
        for a single-syscall move. If the process dies at any point,
        the task exists in exactly one folder.
        """
        src = self._path(from_dir, task.id)
        dst = self._path(to_dir, task.id)
        # Update source file in place with new task state
        tmp = src.with_suffix(".tmp")
        tmp.write_text(json.dumps(task.to_dict(), indent=2, default=str))
        tmp.replace(src)  # atomic update in place
        src.replace(dst)  # atomic move — single syscall, no two-folder window

    # ── Submit ──

    def submit(self, task: Task):
        """Drop a task into the inbox."""
        task.log("inbox")
        self._write("inbox", task)
        return task.id

    # ── Claim ──

    def claim(self, agent_name: str, task_id: str) -> Optional[Task]:
        """Atomically claim a task from inbox → active.
        
        Uses os.rename as the atomic primitive. The first agent to
        successfully rename the file wins. All others get FileNotFoundError.
        """
        src = self._path("inbox", task_id)
        dst = self._path("active", task_id)
        try:
            src.rename(dst)  # atomic on POSIX — first caller wins
        except FileNotFoundError:
            return None  # another agent got it first
        # We won the claim — now update metadata in place
        task = self._read(dst)
        task.log("active", claimed_by=agent_name)
        task.assigned_to = agent_name
        self._write("active", task)  # overwrites with updated metadata
        return task

    # ── Complete ──

    def complete(self, task: Task, result: dict):
        """Mark a task as done with results."""
        task.result = result
        task.log("done")
        self._move(task, "active", "done")

    # ── Fail ──

    def fail(self, task: Task, error: str):
        """Mark a task as failed. Auto-retries if retries remain."""
        task.retry_count += 1
        if task.retry_count <= task.max_retries:
            task.log("retry", error=error, attempt=task.retry_count)
            self._move(task, "active", "inbox")
        else:
            task.log("failed", error=error)
            self._move(task, "active", "failed")

    # ── Feedback (human-in-the-loop) ──

    def request_feedback(self, task: Task, question: dict):
        """Move task to feedback/ for human review."""
        task.context["_feedback_request"] = question
        task.log("feedback")
        self._move(task, "active", "feedback")

    def respond_feedback(self, task_id: str, response: Any):
        """Human responds to feedback, task goes back to inbox."""
        path = self._path("feedback", task_id)
        task = self._read(path)
        task.context["_feedback_response"] = response
        task.log("inbox", feedback_received=True)
        self._move(task, "feedback", "inbox")

    # ── Block ──

    def block(self, task: Task, reason: str):
        """Move task to blocked/ (waiting on dependency)."""
        task.log("blocked", reason=reason)
        self._move(task, "active", "blocked")

    def unblock(self, task_id: str):
        """Move blocked task back to inbox."""
        path = self._path("blocked", task_id)
        task = self._read(path)
        task.log("inbox", unblocked=True)
        self._move(task, "blocked", "inbox")

    # ── Query ──

    def list_tasks(self, folder: str, agent: Optional[str] = None, tags: Optional[list] = None) -> list:
        """List tasks in a folder, optionally filtered."""
        tasks = []
        folder_path = self.workspace / folder
        for f in sorted(folder_path.glob("*.json")):
            try:
                task = self._read(f)
                if agent and task.assigned_to and task.assigned_to != agent:
                    continue
                if tags and not any(t in task.tags for t in tags):
                    continue
                tasks.append(task)
            except (json.JSONDecodeError, KeyError):
                continue
        tasks.sort(key=lambda t: (t.priority, t.created_at))
        return tasks

    def get_task(self, task_id: str) -> Optional[Task]:
        """Find a task in any folder."""
        for d in self.DIRS:
            path = self._path(d, task_id)
            if path.exists():
                return self._read(path)
        return None

    # ── Agent registry ──

    def register_agent(self, name: str, role: str = "worker", **meta):
        """Register an agent in the workspace."""
        agent_file = self.workspace / "agents" / f"{name}.json"
        data = {
            "name": name,
            "role": role,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "last_seen": datetime.now(timezone.utc).isoformat(),
            **meta,
        }
        agent_file.write_text(json.dumps(data, indent=2))

    def heartbeat(self, name: str):
        """Update agent's last_seen timestamp."""
        path = self.workspace / "agents" / f"{name}.json"
        if path.exists():
            data = json.loads(path.read_text())
            data["last_seen"] = datetime.now(timezone.utc).isoformat()
            path.write_text(json.dumps(data, indent=2))

    # ── Stats ──

    def stats(self) -> dict:
        """Quick workspace stats (task folders only)."""
        return {d: len(list((self.workspace / d).glob("*.json"))) for d in self.TASK_DIRS}

    # ── Reaper ──

    def reap_stale(self, timeout_seconds: float = 300) -> list:
        """Move stale active/ tasks back to inbox for retry.
        
        A task is considered stale if it's been in active/ longer than
        timeout_seconds without completing. This handles crashed agents
        that orphan work. Returns list of reaped task IDs.
        """
        reaped = []
        now = datetime.now(timezone.utc)
        for f in (self.workspace / "active").glob("*.json"):
            try:
                task = self._read(f)
                # Find when task was claimed (last 'active' entry in history)
                claimed_at = None
                for entry in reversed(task.history):
                    if entry.get("status") == "active":
                        claimed_at = datetime.fromisoformat(entry["at"])
                        break
                if claimed_at and (now - claimed_at).total_seconds() > timeout_seconds:
                    task.log("inbox", reaped=True, reason="stale_timeout")
                    self._move(task, "active", "inbox")
                    reaped.append(task.id)
            except (json.JSONDecodeError, KeyError, ValueError):
                continue
        return reaped

    # ── Aliases (backward compat with README examples) ──

    drop_task = submit
    claim_task = claim
    complete_task = complete
    check_inbox = lambda self, agent=None, **kw: self.list_tasks("inbox", agent=agent, **kw)
    get_completed = lambda self, agent=None: self.list_tasks("done", agent=agent)


# ═══════════════════════════════════════════
#  AGENT LOOP
# ═══════════════════════════════════════════

class AgentLoop:
    """Polling loop that turns a function into a DropSite agent."""

    def __init__(
        self,
        ds: DropSite,
        name: str,
        handler: Callable[[Task], dict],
        filter_tags: Optional[list] = None,
        poll_interval: float = 1.0,
    ):
        self.ds = ds
        self.name = name
        self.handler = handler
        self.filter_tags = filter_tags
        self.poll_interval = poll_interval
        self.ds.register_agent(name)

    def run(self, once: bool = False):
        """Start the agent loop. Set once=True for single pass."""
        print(f"🔻 Agent '{self.name}' watching the drop site...")
        while True:
            self.ds.heartbeat(self.name)
            tasks = self.ds.list_tasks("inbox", tags=self.filter_tags)

            for task_data in tasks:
                # Skip tasks assigned to other agents
                if task_data.assigned_to and task_data.assigned_to != self.name:
                    continue

                task = self.ds.claim(self.name, task_data.id)
                if not task:
                    continue  # another agent claimed it

                print(f"  ← Claimed: {task.title} [{task.id}]")
                try:
                    result = self.handler(task)
                    self.ds.complete(task, result or {})
                    print(f"  → Done: {task.title} [{task.id}]")
                except Exception as e:
                    print(f"  ✗ Failed: {task.title} — {e}")
                    self.ds.fail(task, str(e))

            if once:
                break
            time.sleep(self.poll_interval)
