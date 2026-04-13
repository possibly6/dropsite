"""
🔻 DropSite Example: LLM-powered agent.

Shows how to wire any LLM (Claude, GPT, Ollama, etc.) as a DropSite agent.
Replace the mock with your actual LLM call.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dropsite import DropSite, TaskBuilder, AgentLoop

ds = DropSite("./llm_workspace")


def llm_agent(task):
    """
    Replace this mock with your actual LLM call:

    # Claude
    import anthropic
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": task.description}]
    )
    return {"response": response.content[0].text}

    # OpenAI
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": task.description}]
    )
    return {"response": response.choices[0].message.content}

    # Ollama (local)
    import requests
    r = requests.post("http://localhost:11434/api/generate",
        json={"model": "llama3", "prompt": task.description})
    return {"response": r.json()["response"]}
    """
    # Mock response for demo
    return {"response": f"[LLM would analyze: {task.description}]"}


if __name__ == "__main__":
    print("🔻 DropSite Demo: LLM Agent\n")

    task = (
        TaskBuilder("Analyze market trends", "orchestrator")
        .describe("What are the top 3 trends in AI agent frameworks in 2026?")
        .assign("llm")
        .tag("analysis")
        .build()
    )
    ds.submit(task)

    loop = AgentLoop(ds, "llm", llm_agent, filter_tags=["analysis"])
    loop.run(once=True)

    # Show result
    done = ds.list_tasks("done")
    if done:
        print(f"\n📄 Result: {done[0].result}")
