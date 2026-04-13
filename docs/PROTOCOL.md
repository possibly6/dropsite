# 🔻 DropSite Protocol Specification

**Version:** 0.2.0  
**Status:** Stable, production-tested  

---

## Overview

DropSite is a filesystem-based communication protocol for AI agents running on the same machine or network share. Agents communicate by reading and writing JSON files in a shared directory structure.

## Directory Structure

```
workspace/
├── inbox/       Tasks waiting to be claimed
├── active/      Tasks currently being worked on
├── done/        Completed tasks with results
├── failed/      Tasks that exhausted all retries
├── blocked/     Tasks waiting on external dependencies
├── feedback/    Tasks awaiting human review
└── agents/      Agent registration files
```

## Task Lifecycle

```
PENDING → INBOX → ACTIVE → DONE
                         → FAILED (if retries exhausted)
                         → FEEDBACK (human-in-the-loop)
                         → BLOCKED (external dependency)

FAILED → INBOX (if retries remain)
FEEDBACK → INBOX (when human responds)
BLOCKED → INBOX (when unblocked)
```

## Task Schema

```json
{
  "id": "string (8-char hex)",
  "title": "string",
  "description": "string",
  "created_by": "string (agent name)",
  "assigned_to": "string | null",
  "status": "pending | inbox | active | done | failed | blocked | feedback",
  "priority": "integer (1=highest, 10=lowest, default=5)",
  "context": "object (arbitrary payload)",
  "result": "object | null",
  "tags": ["string"],
  "parent_id": "string | null",
  "retry_count": "integer",
  "max_retries": "integer (default=3)",
  "created_at": "ISO 8601 datetime",
  "updated_at": "ISO 8601 datetime",
  "history": [
    {
      "status": "string",
      "at": "ISO 8601 datetime",
      "...extra_fields": "any"
    }
  ]
}
```

## Operations

### Submit
Write a task JSON file to `inbox/{task_id}.json`.

### Claim
Atomically move a task from `inbox/` to `active/` using `os.rename()`. The first agent to successfully rename the file "wins" the claim. Competing agents receive a `FileNotFoundError`, which is the concurrency primitive.

### Complete
Write the result into the task, then move from `active/` to `done/`.

### Fail
Increment `retry_count`. If under `max_retries`, move back to `inbox/` for retry. Otherwise, move to `failed/`.

### Feedback
Move from `active/` to `feedback/` with a feedback request in the context. A human (or another agent) reads the file, adds a response, and moves it back to `inbox/`.

### Block / Unblock
Move to `blocked/` when waiting on an external dependency. Move back to `inbox/` when resolved.

## Agent Registration

Agents register by writing a JSON file to `agents/{name}.json`:

```json
{
  "name": "string",
  "role": "string",
  "registered_at": "ISO 8601 datetime",
  "last_seen": "ISO 8601 datetime"
}
```

Agents update `last_seen` via heartbeat during their polling loop.

## Concurrency Model

DropSite uses `os.rename()` as its atomic primitive. On POSIX systems, rename is atomic within the same filesystem. This means:

- Two agents cannot claim the same task
- File writes use a `.tmp` → rename pattern to prevent partial reads
- No file locking, mutexes, or coordination servers required

## Ordering

Tasks are processed in order of: `priority` (ascending, 1=first), then `created_at` (ascending, oldest first).

## Agent Filtering

Agents can filter inbox tasks by:
- **Tags**: Only pick up tasks matching specific tags
- **Assignment**: Only pick up tasks explicitly assigned to them

Unassigned tasks can be claimed by any agent.

## Design Constraints

- **Zero dependencies**: stdlib only (json, os, pathlib, uuid, time, datetime, shutil, dataclasses)
- **Single file**: Core library is one Python file
- **Language agnostic**: Any process that reads/writes JSON files is a valid agent
- **No network**: Filesystem only — use NFS/SMB for cross-machine
- **No daemon**: No background process required — agents poll independently
