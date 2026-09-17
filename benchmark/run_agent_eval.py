"""End-to-end evaluation of WWC27-MedAgent against two baselines.

Conditions (each question x each run):
  agent             the model with the WWC27-MedAgent MCP tools (no article text in context)
  paper_in_context  the same model with the full manuscript in its system prompt, no tools
  closed_book       the same model with neither tools nor the article

Usage
  pip install -e ".[bench]"          # installs anthropic
  export ANTHROPIC_API_KEY=...
  python benchmark/run_agent_eval.py --model <model-id> --runs 5
  python benchmark/run_agent_eval.py --mock oracle --runs 2     # pipeline self-test, no API calls

Output: benchmark/results/responses_<timestamp>.jsonl  (one line per question x condition x run)
Then:   python benchmark/score.py benchmark/results/responses_<timestamp>.jsonl
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from contextlib import AsyncExitStack
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from grading import grade, parse_response  # noqa: E402

ANSWER_FORMAT = (
    "Finish your reply with a JSON object on its own, with keys: "
    '"answer" (short text), "value" (a single number if the question asks for one, else null), '
    '"items" (list of short strings if the question asks for one or more categories/cities, else []), '
    '"refused" (true if the question cannot be answered from the available evidence), '
    '"sources" (list of DOIs or URLs you relied on).'
)

SYSTEM = {
    "agent": ("You are a sports-medicine assistant connected to the WWC27-MedAgent tools. Answer only from "
              "tool outputs. If the tools do not support an answer, say you don't know and set refused=true. "
              + ANSWER_FORMAT),
    "paper_in_context": ("You are a sports-medicine assistant. Answer only from the article below. If the article "
                         "does not support an answer, say you don't know and set refused=true. " + ANSWER_FORMAT
                         + "\n\n<article>\n{manuscript}\n</article>"),
    "closed_book": ("You are a sports-medicine assistant. Answer from your own knowledge. If you cannot answer "
                    "reliably, say you don't know and set refused=true. " + ANSWER_FORMAT),
}


def load_items(sets):
    items = [json.loads(l) for l in (HERE / "questions.jsonl").open(encoding="utf-8")]
    return [i for i in items if not sets or i["set"] in sets]


# ------------------------------------------------------------------ MCP bridge
class MCPTools:
    """Starts the local MCP server over stdio and exposes its tools in Anthropic tool format."""

    def __init__(self):
        self.stack = AsyncExitStack()
        self.session = None
        self.tools = []

    async def __aenter__(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=sys.executable, args=["-m", "wwc27_medagent.server"])
        r, w = await self.stack.enter_async_context(stdio_client(params))
        self.session = await self.stack.enter_async_context(ClientSession(r, w))
        await self.session.initialize()
        listed = await self.session.list_tools()
        self.tools = [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
                      for t in listed.tools]
        return self

    async def __aexit__(self, *exc):
        await self.stack.aclose()

    async def call(self, name, args):
        res = await self.session.call_tool(name, args)
        return "\n".join(getattr(c, "text", "") for c in res.content) or "{}"


# ------------------------------------------------------------------ model loop
async def ask_anthropic(client, model, system, question, mcp=None, max_turns=8):
    messages = [{"role": "user", "content": question}]
    calls, usage = [], {"input_tokens": 0, "output_tokens": 0}
    for _ in range(max_turns):
        kw = {"model": model, "max_tokens": 2000, "system": system, "messages": messages}
        if mcp:
            kw["tools"] = mcp.tools
        resp = await asyncio.to_thread(client.messages.create, **kw)
        usage["input_tokens"] += resp.usage.input_tokens
        usage["output_tokens"] += resp.usage.output_tokens
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            text = "".join(b.text for b in resp.content if b.type == "text")
            return text, calls, usage
        results = []
        for b in resp.content:
            if b.type == "tool_use":
                calls.append({"name": b.name, "input": b.input})
                try:
                    out = await mcp.call(b.name, b.input)
                except Exception as e:  # tool errors are returned to the model
                    out = json.dumps({"error": str(e)})
                results.append({"type": "tool_result", "tool_use_id": b.id, "content": out})
        messages.append({"role": "user", "content": results})
    return "Stopped: too many tool turns.", calls, usage


def mock_oracle(item):
    """Pipeline self-test: returns the ground truth (or a refusal) in the required format."""
    t = item["answer_type"]
    obj = {"answer": "", "value": None, "items": [], "refused": False, "sources": item.get("refs", [])}
    if t == "number":
        obj.update(answer=str(item["ground_truth"]), value=item["ground_truth"])
    elif t == "set":
        obj.update(answer=", ".join(item["ground_truth"]), items=item["ground_truth"])
    elif t == "refusal":
        obj.update(answer="I don't know: this is outside the evidence base.", refused=True)
    else:
        obj.update(answer="Draft plan covering: " + "; ".join(item["rubric"]))
    return "Mock answer.\n" + json.dumps(obj, ensure_ascii=False)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="Anthropic model id")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--conditions", default="agent,paper_in_context,closed_book")
    ap.add_argument("--sets", default="", help="comma list, e.g. reproduction,out_of_scope")
    ap.add_argument("--mock", choices=["oracle"], help="no API calls; tests the pipeline")
    a = ap.parse_args()
    if not a.mock and not a.model:
        ap.error("--model is required unless --mock is used")

    items = load_items([s for s in a.sets.split(",") if s])
    conds = a.conditions.split(",")
    manuscript = (HERE.parent / "wwc27_medagent" / "data" / "manuscript.md").read_text(encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = HERE / "results" / f"responses_{'mock_' if a.mock else ''}{stamp}.jsonl"
    out_path.parent.mkdir(exist_ok=True)

    client = None
    if not a.mock:
        import anthropic
        client = anthropic.Anthropic()

    async with AsyncExitStack() as stack:
        mcp = await stack.enter_async_context(MCPTools()) if ("agent" in conds) else None
        with out_path.open("w", encoding="utf-8") as fh:
            for run in range(1, a.runs + 1):
                for cond in conds:
                    system = SYSTEM[cond].replace("{manuscript}", manuscript)
                    for it in items:
                        t0 = time.perf_counter()
                        if a.mock:
                            text, calls, usage = mock_oracle(it), [], {"input_tokens": 0, "output_tokens": 0}
                        else:
                            text, calls, usage = await ask_anthropic(client, a.model, system, it["question"],
                                                                     mcp if cond == "agent" else None)
                        parsed = parse_response(text)
                        g = grade(it, parsed)
                        rec = {"run": run, "condition": cond, "id": it["id"], "set": it["set"],
                               "question": it["question"], "response_text": text, "parsed": parsed,
                               "auto_correct": g["correct"], "grading_detail": g["detail"],
                               "tool_calls": calls, "latency_s": round(time.perf_counter() - t0, 2),
                               "usage": usage, "model": a.model or "mock-oracle"}
                        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    print(f"run {run} {cond}: done", flush=True)
    print("wrote", out_path)


if __name__ == "__main__":
    asyncio.run(main())
