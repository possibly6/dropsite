"""
🔻 DropSite Example: Two agents, one drop site.

A researcher finds data, drops a task for the writer.
The writer picks it up and produces content.
They never meet. They just check the drop site.
"""

import sys, os, time, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dropsite import DropSite, TaskBuilder, AgentLoop

# Create workspace
ds = DropSite("./demo_workspace")

# ── Agent handlers ──

def researcher(task):
    """Simulates research, then chains a task to the writer."""
    topic = task.context.get("topic", "AI agents")
    findings = f"Found 3 key trends about {topic}: trend A, trend B, trend C."

    # Chain to writer
    writer_task = (
        TaskBuilder(f"Write article about {topic}", "researcher")
        .describe("Turn research findings into a blog post")
        .context({"research": findings, "topic": topic})
        .assign("writer")
        .tag("content")
        .build()
    )
    ds.submit(writer_task)

    return {"findings": findings}


def writer(task):
    """Picks up research and produces content."""
    research = task.context.get("research", "")
    article = f"# Article\n\nBased on our research:\n{research}\n\nConclusion: These trends matter."
    return {"article": article}


# ── Run ──

if __name__ == "__main__":
    print("🔻 DropSite Demo: Researcher → Writer pipeline\n")

    # Drop initial research task
    task = (
        TaskBuilder("Research AI trends", "user")
        .describe("Find the latest trends in AI agent communication")
        .context({"topic": "AI agent protocols"})
        .assign("researcher")
        .tag("research")
        .build()
    )
    ds.submit(task)
    print(f"  Dropped task: {task.title} [{task.id}]\n")

    # Run researcher (single pass)
    r_loop = AgentLoop(ds, "researcher", researcher, filter_tags=["research"])
    r_loop.run(once=True)

    print()

    # Run writer (single pass)
    w_loop = AgentLoop(ds, "writer", writer, filter_tags=["content"])
    w_loop.run(once=True)

    # Show results
    print("\n📊 Final workspace stats:")
    for folder, count in ds.stats().items():
        if count > 0:
            print(f"  {folder}: {count}")

    print("\n✅ Done! Check ./demo_workspace/done/ for results.")
