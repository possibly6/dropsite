"""
🔻 DropSite Example: Human-in-the-loop approval workflow.

An agent drafts something, drops it for human review.
The human reviews the JSON file and responds.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dropsite import DropSite, TaskBuilder, AgentLoop

ds = DropSite("./hitl_workspace")


def drafter(task):
    """Generates a draft, then requests human feedback."""
    draft = f"Subject: {task.context.get('topic', 'Update')}\n\nDear team,\n\nHere are the key points..."

    ds.request_feedback(task, {
        "question": "Should we send this email?",
        "draft": draft,
        "options": ["approve", "revise", "reject"],
    })

    return {"status": "awaiting_feedback"}


if __name__ == "__main__":
    print("🔻 DropSite Demo: Human-in-the-Loop\n")

    # Drop a drafting task
    task = (
        TaskBuilder("Draft team update email", "user")
        .context({"topic": "Q1 Results"})
        .assign("drafter")
        .tag("drafting")
        .build()
    )
    ds.submit(task)

    # Run the drafter
    loop = AgentLoop(ds, "drafter", drafter, filter_tags=["drafting"])
    loop.run(once=True)

    print("\n📋 Task is now in feedback/")
    print("   A human would review: cat hitl_workspace/feedback/*.json")
    print()

    # Simulate human response
    feedback_tasks = ds.list_tasks("feedback")
    if feedback_tasks:
        t = feedback_tasks[0]
        print(f"   Simulating human approval for [{t.id}]...")
        ds.respond_feedback(t.id, "approve — looks good, send it")
        print("   ✅ Task returned to inbox with feedback attached.")

    print("\n📊 Stats:")
    for folder, count in ds.stats().items():
        if count > 0:
            print(f"  {folder}: {count}")
