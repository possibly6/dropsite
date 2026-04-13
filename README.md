# 🔻 DropSite

**The dead drop for your AI agents.**

No APIs. No message queues. No JSON-RPC. No agent discovery services.

Just folders and JSON files.

```
workspace/
├── inbox/       ← new tasks get dropped here
├── active/      ← agents claim tasks by moving them here
├── done/        ← completed work lands here
├── failed/      ← exhausted retries or corrupt files
├── blocked/     ← waiting on external dependencies
├── feedback/    ← human-in-the-loop review
└── agents/      ← agent registry
```

Any process that can read and write files can be an agent — Python, Node, bash, a human with a text editor. That's it. That's the protocol.

---

## Why This Exists

The agent communication landscape in 2026 looks like this:

| Protocol | By | Transport | Auth | Discovery | Setup Time |
|----------|-----|-----------|------|-----------|------------|
| **A2A** | Google / Linux Foundation | JSON-RPC over HTTPS | OAuth / Agent Cards | Federated registries | Hours |
| **ACP** | IBM / BeeAI | REST / SSE / stdio | Token-based | Service endpoints | Hours |
| **MCP** | Anthropic | JSON-RPC over stdio/HTTP | Varies | Server manifests | Minutes |
| **ANP** | Community | HTTPS + DIDs | Decentralized identity | Blockchain-adjacent | Days |
| **DropSite** | You, right now | **Filesystem** | **None needed** | **`ls` the directory** | **Seconds** |

Those protocols are solving real problems — cross-company agent interop, enterprise security, federated discovery across the internet. They're building HTTP for the agentic web.

**DropSite is localhost.**

If your agents are on the same machine (or same network share), you don't need any of that. You need a folder.

> A2A is to DropSite what Postgres is to SQLite.
> Both are correct choices. Depends on the job.

---

## Install

```bash
git clone https://github.com/possibly6/dropsite.git
cd dropsite
pip install -e .
```

Or install directly:
```bash
pip install git+https://github.com/possibly6/dropsite.git
```

The entire library is one file (`dropsite/dropsite.py`, ~320 lines, zero dependencies). You can also just copy it into your project.

---

## Quick Start

### 1. Create a workspace

```python
from dropsite import DropSite, TaskBuilder, AgentLoop

ds = DropSite("./workspace")
```

This creates the directory structure. That's your entire infrastructure.

### 2. Register agents

```python
ds.register_agent("larry", role="orchestrator")
ds.register_agent("coder", role="builder")
```

### 3. Drop a task

```python
task = (
    TaskBuilder("Build auth API", "larry")
    .describe("Build a REST API for user authentication")
    .context({"language": "python", "framework": "fastapi"})
    .assign("coder")
    .tag("code")
    .build()
)
ds.submit(task)
```

This writes a JSON file to the inbox. That's the entire communication mechanism.

### 4. Pick up work

```python
tasks = ds.list_tasks("inbox", tags=["code"])
claimed = ds.claim("coder", tasks[0].id)

# Do the work...

ds.complete(claimed, result={
    "files_created": ["api.py", "models.py"],
    "notes": "Used FastAPI with JWT auth"
})
```

### 5. Check results

```python
done = ds.list_tasks("done")
# Or just: cat workspace/done/*.json | python -m json.tool
```

### 6. Or use AgentLoop to automate it

```python
def code_handler(task):
    # Your agent logic here — call an LLM, run a script, whatever
    return {"files_created": ["api.py"], "status": "done"}

loop = AgentLoop(ds, "coder", handler=code_handler, filter_tags=["code"])
loop.run()  # polls inbox, claims tasks, runs handler, drops results
```

---

## The Whole Point

**You can debug this with `ls` and `cat`.**

```bash
# What's pending?
ls workspace/inbox/

# What's being worked on?
ls workspace/active/

# What just finished?
cat workspace/done/*.json | python -m json.tool
```

No dashboards. No observability platforms. No log aggregators. The filesystem _is_ the dashboard.

Every task is a JSON file with a complete history — who created it, who claimed it, when it started, when it finished, what the result was. `grep` is your query language.

---

## Human-in-the-Loop

Because tasks are just files, a human can participate in the pipeline with zero tooling:

```python
# Agent drops a task that needs approval
task = (
    TaskBuilder("Approve trade", "larry")
    .context({
        "action": "buy",
        "ticker": "NVDA",
        "size": 100,
        "rationale": "Bullish GEX flip detected"
    })
    .assign("human")
    .tag("approval")
    .build()
)
ds.submit(task)
```

When the agent is working on a task and needs human review:

```python
# Inside an agent handler
def my_agent(task):
    draft = generate_email(task.context)
    ds.request_feedback(task, {
        "question": "Send this email?",
        "draft": draft,
        "options": ["approve", "revise", "reject"]
    })
    return {"status": "awaiting_feedback"}
```

The human reviews via CLI or by opening the JSON:
```bash
# See what needs review
dropsite list ./workspace feedback

# Respond
dropsite feedback ./workspace <task_id> "approved, send it"
```

---

## Works With Any LLM

```python
import anthropic
from dropsite import DropSite, AgentLoop

client = anthropic.Anthropic()
ds = DropSite("./workspace")

def claude_agent(task):
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": task.description}]
    )
    return {"response": response.content[0].text}

loop = AgentLoop(ds, "claude", handler=claude_agent, filter_tags=["analysis"])
loop.run()

# Or OpenAI, Ollama, vLLM, LM Studio, llama.cpp — anything.
# If it can return text, it can be a DropSite agent.
```

---

## Advanced Features

### Priority Queue

Tasks are sorted by priority (1 = highest) then creation time:

```python
ds.submit(TaskBuilder("Urgent", "user").priority(1).build())    # picked up first
ds.submit(TaskBuilder("Normal", "user").priority(5).build())
ds.submit(TaskBuilder("Low", "user").priority(10).build())
```

### Auto-Retry

Failed tasks automatically retry up to `max_retries`:

```python
task = TaskBuilder("Flaky API call", "user").max_retries(5).build()
# If the handler throws, task goes back to inbox up to 5 times
# After that, it lands in failed/ for investigation
```

### Tag-Based Routing

Agents filter by tags to specialize:

```python
AgentLoop(ds, "writer", handler=write_fn, filter_tags=["content"])
AgentLoop(ds, "coder", handler=code_fn, filter_tags=["code"])
AgentLoop(ds, "ops", handler=deploy_fn, filter_tags=["deploy"])
```

### Stale Task Reaper

If an agent crashes mid-task, work can get orphaned in `active/`. The reaper moves stale tasks back to inbox:

```python
# Move any task stuck in active/ for more than 5 minutes back to inbox
reaped = ds.reap_stale(timeout_seconds=300)
print(f"Reaped {len(reaped)} stale tasks")
```

### Task Chaining

Agents can drop new tasks from within handlers, creating pipelines:

```python
def researcher(task):
    findings = do_research(task.context["topic"])
    # Chain to the writer
    writer_task = (
        TaskBuilder("Write article", "researcher")
        .context({"research": findings})
        .assign("writer")
        .tag("content")
        .build()
    )
    ds.submit(writer_task)
    return {"findings": findings}
```

---

## CLI

```bash
# Initialize a workspace
dropsite init ./workspace

# Register an agent
dropsite register ./workspace --name larry --role orchestrator

# Drop a task
dropsite drop ./workspace --from larry --title "Build auth API" --type code --payload '{"lang": "python"}'

# Check an inbox
dropsite inbox ./workspace --agent coder

# List tasks in any folder
dropsite list ./workspace done
dropsite list ./workspace failed

# Workspace stats
dropsite stats ./workspace

# Respond to feedback
dropsite feedback ./workspace <task_id> "approved"
```

---

## Real-World Usage

This protocol was born from a production system coordinating an autonomous AI agent (orchestrator + builder agents) running 24/7 on a Mac Mini M4 via pm2. It has handled hundreds of autonomous tasks including code generation, API integrations, Discord bot commands, and data pipeline construction.

The filesystem approach survived agent crashes (tasks sit in `active/` until the reaper moves them back), concurrent access (atomic rename for claims), and 3am debugging sessions (`cat` the file, see exactly what happened).

---

## When to Use DropSite

✅ **Use DropSite when:**
- Your agents are on the same machine or network
- You want zero-infrastructure communication
- You need to debug agent interactions by reading files
- You're prototyping a multi-agent system
- You want human-in-the-loop with zero UI investment
- Your agent count is 2-20 (not 2,000)

❌ **Use A2A/ACP/MCP when:**
- Agents are distributed across the internet
- You need enterprise auth and discovery
- You're building a multi-company agent ecosystem
- You need streaming or real-time pub/sub
- Your scale requires a real message broker

DropSite is deliberately simple. It will never grow into a distributed system. That's not a limitation — that's the design.

---

## How It Works (The Protocol)

See [PROTOCOL.md](docs/PROTOCOL.md) for the full spec. The gist:

**State machine:**
```
DROP → INBOX → CLAIMED → ACTIVE → DONE
                                    ↘ FAILED
                          ↘ FEEDBACK → (human responds) → INBOX
                          ↘ BLOCKED → (unblocked) → INBOX
```

**Concurrency primitive:** `os.rename()` is atomic on POSIX. Two agents can't claim the same task — the first `rename` wins, the second gets `FileNotFoundError`. No locks, no mutexes, no coordination server.

**Durability:** Every write goes to a `.tmp` file first, then `replace()` swaps it in atomically. A crash at any point leaves exactly one valid copy in exactly one folder.

---

## Repo Structure

```
dropsite/
├── dropsite/
│   ├── __init__.py        # Package exports
│   ├── dropsite.py        # Core library (~320 lines)
│   └── cli.py             # Command-line interface
├── examples/
│   ├── basic-two-agents/  # Researcher → Writer pipeline
│   ├── human-in-the-loop/ # Approval workflows
│   └── multi-agent-pipeline/  # LLM integration
├── tests/
│   └── test_dropsite.py   # Happy path, race condition, retry, feedback
├── docs/
│   └── PROTOCOL.md        # Formal protocol specification
├── .github/workflows/
│   └── ci.yml             # Tests on Python 3.10–3.13
├── pyproject.toml
├── LICENSE                 # MIT
└── README.md
```

---

## FAQ

**Q: Doesn't this break with concurrent access?**
A: File moves (`os.rename`) are atomic on all major operating systems. Two agents can't claim the same task. The first `rename` wins, the second gets a `FileNotFoundError`. This is the same primitive that lock files have used for decades.

**Q: What about corrupted files?**
A: All writes use a `.tmp` → `replace()` pattern to prevent partial reads. If a file is somehow corrupted, `_read()` catches the JSON error and moves it to `failed/` automatically.

**Q: What about networked filesystems?**
A: Works on NFS and SMB shares. For anything beyond a LAN, you probably want a real protocol.

**Q: How do I monitor this in production?**
A: `watch -n 1 'ls workspace/active/'` — seriously. Or build a 20-line script that counts files in each directory.

**Q: Why not just use Redis/RabbitMQ/Kafka?**
A: You can! Those are great tools. DropSite is for when you don't want to run, configure, or maintain any of those. If your agents are already on the same box, a folder is the lowest-overhead option that exists.

**Q: Can agents be written in different languages?**
A: Yes. If it can read and write JSON files, it's a valid DropSite agent. We've run Python orchestrators coordinating with bash scripts and Node.js workers.

---

## Philosophy

The espionage metaphor isn't just branding. Dead drops are a real tradecraft technique where two operatives communicate without ever meeting — they leave messages at a predetermined location. Neither party needs to know anything about the other's identity, schedule, or methods. They just need to know where the drop site is.

That's exactly how this works. Your agents don't need to know each other's APIs, ports, protocols, or authentication schemes. They just need to know where the folder is.

---

## License

MIT — do whatever you want with it.

---

<p align="center">
  <b>🔻 dropsite</b><br>
  <i>the dead drop for your AI agents</i><br><br>
  <code>pip install git+https://github.com/possibly6/dropsite.git</code>
</p>
