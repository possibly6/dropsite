# 🔻 DropSite

**The dead drop for your AI agents.**

No APIs. No message queues. No JSON-RPC. No agent discovery services.

Just folders and JSON files.

```
workspace/
├── .dropsite/
│   ├── inbox/          ← new tasks get dropped here
│   ├── active/         ← agents claim tasks by moving them here
│   ├── done/           ← completed work lands here
│   └── manifest.json   ← who's who
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
pip install dropsite
```

Or just copy `dropsite.py` into your project. It's ~300 lines with zero dependencies.

---

## Quick Start

### 1. Create a workspace

```python
from dropsite import DropSite

ds = DropSite("./workspace")
ds.init()
```

This creates the directory structure. That's your entire infrastructure.

### 2. Register agents

```python
ds.register_agent("larry", role="orchestrator")
ds.register_agent("coder", role="builder")
```

### 3. Drop a task

```python
ds.drop_task(
    from_agent="larry",
    to_agent="coder",
    task_type="write_code",
    payload={
        "description": "Build a REST API for user authentication",
        "language": "python",
        "framework": "fastapi"
    }
)
```

This writes a JSON file to `coder`'s inbox. That's the entire communication mechanism.

### 4. Pick up work

```python
# From the coder agent's perspective
tasks = ds.check_inbox("coder")
task = ds.claim_task("coder", tasks[0]["id"])

# Do the work...

ds.complete_task("coder", task["id"], result={
    "files_created": ["api.py", "models.py"],
    "status": "done",
    "notes": "Used FastAPI with JWT auth"
})
```

### 5. Check results

```python
done = ds.get_completed("larry")
# Or just: cat workspace/.dropsite/done/*.json
```

---

## The Whole Point

**You can debug this with `ls` and `cat`.**

```bash
# What's pending?
ls workspace/.dropsite/inbox/

# What's being worked on?
ls workspace/.dropsite/active/

# What just finished?
cat workspace/.dropsite/done/task_abc123.json | python -m json.tool
```

No dashboards. No observability platforms. No log aggregators. The filesystem _is_ the dashboard.

Every task is a JSON file with a complete history — who created it, who claimed it, when it started, when it finished, what the result was. `grep` is your query language. `mv` is your state machine.

---

## Human-in-the-Loop

Because tasks are just files, a human can participate in the pipeline with zero tooling:

```python
# Agent drops a task that needs approval
ds.drop_task(
    from_agent="larry",
    to_agent="human",
    task_type="approve_trade",
    payload={
        "action": "buy",
        "ticker": "NVDA",
        "size": 100,
        "rationale": "Bullish GEX flip detected"
    }
)
```

The human literally just opens the JSON file, reads it, and either moves it to `done/` with an approval flag or deletes it. You could build a simple UI on top of this, or you could use your file manager.

---

## Real-World Usage

This protocol has been running in production coordinating an autonomous AI agent system:

- **243+ tasks completed** autonomously
- **99% success rate** across orchestrator → builder agent pipelines
- Running 24/7 on a Mac Mini M4 via pm2
- Tasks include: code generation, API integrations, Discord bot commands, data pipeline construction
- Average task lifecycle: drop → claim → complete in under 2 minutes for code tasks

The filesystem approach survived everything we threw at it — agent crashes (the task just sits in `active/` until timeout), concurrent access (atomic file moves), and debugging at 3am (just `cat` the file).

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

## CLI

```bash
# Initialize a workspace
dropsite init ./workspace

# Register an agent
dropsite register ./workspace --name larry --role orchestrator

# Drop a task
dropsite drop ./workspace --from larry --to coder --type write_code --payload '{"desc": "build auth API"}'

# Check an inbox
dropsite inbox ./workspace --agent coder

# List completed tasks
dropsite done ./workspace
```

---

## How It Works (The Protocol)

The protocol is intentionally minimal. See [PROTOCOL.md](docs/PROTOCOL.md) for the full spec, but here's the gist:

**State machine:**
```
DROP → INBOX → CLAIMED → ACTIVE → DONE
                                    ↘ FAILED
```

**Task lifecycle:**
1. Agent A writes a JSON file to Agent B's `inbox/`
2. Agent B reads `inbox/`, moves the file to `active/` (atomic claim)
3. Agent B does the work
4. Agent B moves the file to `done/` with results attached (or `failed/`)

**File format:**
```json
{
  "id": "task_a1b2c3",
  "from": "larry",
  "to": "coder",
  "type": "write_code",
  "status": "inbox",
  "created_at": "2026-04-13T14:30:00Z",
  "payload": { ... },
  "result": null,
  "history": [
    {"status": "inbox", "at": "2026-04-13T14:30:00Z"},
    {"status": "claimed", "at": "2026-04-13T14:30:01Z", "by": "coder"}
  ]
}
```

That's the entire protocol. No versioning negotiations, no capability discovery, no handshake. Just files.

---

## FAQ

**Q: Doesn't this break with concurrent access?**
A: File moves (`os.rename`) are atomic on all major operating systems. Two agents can't claim the same task. The first `rename` wins, the second gets a `FileNotFoundError`. This is the same primitive that lock files have used for decades.

**Q: What about networked filesystems?**
A: Works on NFS and SMB shares. We've tested it across machines on the same LAN. For anything beyond that, you probably want a real protocol.

**Q: How do I monitor this in production?**
A: `watch -n 1 'ls workspace/.dropsite/active/'` — seriously. Or build a 20-line script that counts files in each directory. The simplicity is the monitoring.

**Q: Why not just use Redis/RabbitMQ/Kafka?**
A: You can! Those are great tools. DropSite is for when you don't want to run, configure, or maintain any of those. If your agents are already on the same box and you just need them to pass messages, a folder is the lowest-overhead option that exists.

**Q: Can agents be written in different languages?**
A: Yes. If it can read and write JSON files, it's a valid DropSite agent. We've run Python orchestrators coordinating Node.js builders with bash scripts handling cleanup.

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
  <code>pip install dropsite</code>
</p>
