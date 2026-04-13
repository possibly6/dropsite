"""
🔻 DropSite Tests

Run with: python -m pytest tests/ -v
"""

import sys, os, threading
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dropsite import DropSite, TaskBuilder, Task
import tempfile
import shutil


def make_ds(tmp_path=None):
    """Create a fresh DropSite in a temp directory."""
    path = tmp_path or tempfile.mkdtemp(prefix="dropsite_test_")
    return DropSite(path), path


def test_happy_path():
    """Drop → claim → complete lifecycle."""
    ds, path = make_ds()
    try:
        task = TaskBuilder("Test task", "user").describe("Do the thing").tag("test").build()
        tid = ds.submit(task)

        # Should be in inbox
        inbox = ds.list_tasks("inbox")
        assert len(inbox) == 1
        assert inbox[0].id == tid

        # Claim it
        claimed = ds.claim("worker", tid)
        assert claimed is not None
        assert claimed.assigned_to == "worker"
        assert claimed.status == "active"

        # Inbox should be empty
        assert len(ds.list_tasks("inbox")) == 0
        assert len(ds.list_tasks("active")) == 1

        # Complete it
        ds.complete(claimed, {"answer": 42})
        assert len(ds.list_tasks("active")) == 0
        assert len(ds.list_tasks("done")) == 1

        done = ds.list_tasks("done")[0]
        assert done.result == {"answer": 42}
        assert done.status == "done"

        print("✅ test_happy_path passed")
    finally:
        shutil.rmtree(path)


def test_concurrent_claim():
    """Two agents race to claim the same task. Only one wins."""
    ds, path = make_ds()
    try:
        task = TaskBuilder("Race task", "user").build()
        tid = ds.submit(task)

        results = []

        def try_claim(agent_name):
            result = ds.claim(agent_name, tid)
            results.append((agent_name, result))

        t1 = threading.Thread(target=try_claim, args=("agent_a",))
        t2 = threading.Thread(target=try_claim, args=("agent_b",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        winners = [name for name, r in results if r is not None]
        losers = [name for name, r in results if r is None]

        assert len(winners) == 1, f"Expected 1 winner, got {len(winners)}: {winners}"
        assert len(losers) == 1, f"Expected 1 loser, got {len(losers)}: {losers}"

        # Inbox empty, active has one
        assert len(ds.list_tasks("inbox")) == 0
        assert len(ds.list_tasks("active")) == 1

        print(f"✅ test_concurrent_claim passed — {winners[0]} won the race")
    finally:
        shutil.rmtree(path)


def test_auto_retry():
    """Failed tasks retry up to max_retries, then go to failed/."""
    ds, path = make_ds()
    try:
        task = TaskBuilder("Flaky task", "user").max_retries(2).build()
        tid = ds.submit(task)
        claimed = ds.claim("worker", tid)

        # First failure — should retry (back to inbox)
        ds.fail(claimed, "timeout")
        assert len(ds.list_tasks("inbox")) == 1
        assert len(ds.list_tasks("failed")) == 0

        # Claim and fail again
        claimed = ds.claim("worker", tid)
        ds.fail(claimed, "timeout again")
        assert len(ds.list_tasks("inbox")) == 1  # still retrying

        # Third failure — should go to failed/ (exceeded max_retries=2)
        claimed = ds.claim("worker", tid)
        ds.fail(claimed, "gave up")
        assert len(ds.list_tasks("inbox")) == 0
        assert len(ds.list_tasks("failed")) == 1

        print("✅ test_auto_retry passed")
    finally:
        shutil.rmtree(path)


def test_feedback_loop():
    """Task goes to feedback, human responds, task returns to inbox."""
    ds, path = make_ds()
    try:
        task = TaskBuilder("Review this", "bot").build()
        tid = ds.submit(task)
        claimed = ds.claim("bot", tid)

        ds.request_feedback(claimed, {"question": "Approve?", "options": ["yes", "no"]})
        assert len(ds.list_tasks("feedback")) == 1
        assert len(ds.list_tasks("active")) == 0

        ds.respond_feedback(tid, "yes, approved")
        assert len(ds.list_tasks("feedback")) == 0
        assert len(ds.list_tasks("inbox")) == 1

        # Check feedback response is in context
        returned = ds.list_tasks("inbox")[0]
        assert returned.context["_feedback_response"] == "yes, approved"

        print("✅ test_feedback_loop passed")
    finally:
        shutil.rmtree(path)


if __name__ == "__main__":
    test_happy_path()
    test_concurrent_claim()
    test_auto_retry()
    test_feedback_loop()
    print("\n🔻 All tests passed.")
