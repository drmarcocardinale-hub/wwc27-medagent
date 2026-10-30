#!/usr/bin/env python3
"""End-to-end check of the deployed agent.

Why this exists: the unit tests run the tool-calling loop against a stub, and every fault that
reached a reader lived in the gap between that stub and the real model API - a thoughtSignature
the stub never sent, a bare TimeoutError urllib raises but the stub does not, a tool ceiling that
refused a four-city question, and a timeout budget that only bites under real latency. None of
them were visible without calling the live service. This script closes that gap: it asks the
deployed agent real questions and checks what comes back.

Run it after every deploy:

    python3 scripts/check_deployed.py

No API key is needed - it uses the shared key on the service. It spends a few of that
instance's free questions per run, so do not loop it.

    --url URL     check a different deployment (default: the Cloud Run service)
    --quick       skip the chat questions; check only health, metadata and MCP

Exit status is 0 when everything passed, 1 otherwise, so CI can use it.
"""
from __future__ import print_function

import argparse
import json
import sys
import time

try:                                     # keep it runnable on the stock macOS python3
    from urllib import request as urlrequest
    from urllib import error as urlerror
except ImportError:                                                  # pragma: no cover
    import urllib2 as urlrequest                                     # type: ignore
    import urllib2 as urlerror                                       # type: ignore

DEFAULT_URL = "https://wwc27-medagent-919325462297.europe-west1.run.app"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"
results = []


def record(status, name, detail="", seconds=None):
    results.append((status, name, detail, seconds))
    stamp = "" if seconds is None else "%6.1fs " % seconds
    print("%-4s %s%s" % (status, stamp, name))
    if detail:
        for line in str(detail).splitlines():
            print("         " + line[:160])


def call(url, path, payload=None, timeout=60):
    """Returns (status_code, parsed_or_text). Never raises."""
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url + path, data=data,
                             headers={"Content-Type": "application/json",
                                      "Accept": "application/json, text/event-stream"})
    try:
        resp = urlrequest.urlopen(req, timeout=timeout)
        body = resp.read().decode("utf-8", "replace")
        code = resp.getcode()
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        code = exc.code
    except Exception as exc:
        return 0, "%s: %s" % (type(exc).__name__, exc)
    text = body
    for line in body.splitlines():                   # streamable HTTP replies as SSE
        if line.startswith("data: "):
            text = line[6:]
            break
    try:
        return code, json.loads(text)
    except ValueError:
        return code, body


# --------------------------------------------------------------------------- the checks

def check_meta(url):
    """Liveness and configuration in one call.

    /api/meta rather than /healthz: a health route returning a constant says only that something
    is listening, while this reports the version, the model and whether a shared key is present -
    which is what actually has to be right. (/healthz also turned out to 404 at Google's edge on
    the run.app domain without reaching the container at all, so it was never a reliable probe.)
    """
    code, body = call(url, "/api/meta", timeout=90)  # first hit may wait for a cold start
    if code != 200 or not isinstance(body, dict):
        record(FAIL, "service is up", "GET /api/meta gave %s: %s" % (code, str(body)[:200]))
        return None
    record(PASS, "service is up", "version %s, model %s, shared key %s"
           % (body.get("version"), body.get("model"), body.get("house_key")))
    if not body.get("house_key"):
        record(SKIP, "shared key present",
               "no GEMINI_API_KEY on the service, so the chat cannot be checked")
    return body


def check_mcp(url):
    init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "check", "version": "1"}}}
    code, body = call(url, "/mcp", init)
    ok = code == 200 and isinstance(body, dict) and "result" in body
    name = (body.get("result", {}).get("serverInfo", {}).get("name")
            if isinstance(body, dict) else None)
    if ok and name == "wwc27-medagent":
        record(PASS, "MCP endpoint answers (the path cited in the paper)")
    else:
        record(FAIL, "MCP endpoint answers", "got %s: %s" % (code, str(body)[:300]))
        return False

    code, body = call(url, "/mcp", {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    tools = (body.get("result", {}).get("tools", []) if isinstance(body, dict) else [])
    if len(tools) == 9:
        record(PASS, "all 9 tools registered")
    else:
        record(FAIL, "all 9 tools registered", "found %d" % len(tools))
        return False
    return True


# Chosen for what they exercise, not for coverage. The second is the question that failed in
# production four separate ways; keep it.
QUESTIONS = [
    {"name": "single tool call",
     "ask": "What's the heat band for Salvador in July?",
     "needs_tools": True,
     "expect_any": ["salvador"]},
    {"name": "several tools, several turns (the one that kept breaking)",
     "ask": ("We're based in Sao Paulo and play in Fortaleza, Recife and Porto Alegre. "
             "Draft our pre-tournament medical plan."),
     "needs_tools": True,
     "expect_any": ["fortaleza", "recife", "porto alegre"]},
    {"name": "refuses what it does not cover",
     "ask": "Who should we pick at centre-back for the opening match?",
     "needs_tools": False,
     "expect_any": ["don't know", "do not know", "not cover", "cannot", "can't", "outside"]},
]


def ask(url, q):
    started = time.time()
    code, body = call(url, "/api/chat",
                      {"history": [{"role": "user", "text": q["ask"]}]}, timeout=280)
    took = time.time() - started

    if code == 402:
        record(SKIP, q["name"], "no shared key on this instance", took)
        return None
    if code == 429:
        record(SKIP, q["name"], "free questions for today are used up", took)
        return None
    if code != 200 or not isinstance(body, dict):
        detail = body.get("error") if isinstance(body, dict) else body
        record(FAIL, q["name"], "HTTP %s - %s" % (code, detail), took)
        return False

    answer = (body.get("answer") or "").strip()
    tools = body.get("tools") or []
    low = answer.lower()
    problems = []

    if not answer:
        problems.append("empty answer")
    if q["needs_tools"] and not tools:
        problems.append("no tool was called, so the answer did not come from the paper")
    if q["expect_any"] and not any(w in low for w in q["expect_any"]):
        problems.append("none of %s appear in the answer" % q["expect_any"])
    for bad in ("the agent failed", "traceback", "fault in the agent"):
        if bad in low:
            problems.append("error text surfaced to the reader")

    detail = "tools: %s" % (", ".join(t.get("name", "?") for t in tools) or "none")
    if problems:
        record(FAIL, q["name"], detail + "\n" + "\n".join(problems) + "\n" + answer[:300], took)
        return False
    record(PASS, q["name"], detail + "\n" + answer[:200], took)
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default=DEFAULT_URL)
    ap.add_argument("--quick", action="store_true", help="skip the chat questions")
    args = ap.parse_args()
    url = args.url.rstrip("/")

    print("Checking %s\n" % url)
    meta = check_meta(url)
    mcp_ok = check_mcp(url)

    # Only give up when nothing answered at all. An earlier version aborted on a single failed
    # probe and announced the service was down while it was plainly serving every other path; a
    # false alarm is the quickest way to make a check like this stop being trusted.
    if meta is None and not mcp_ok:
        print("\nNothing answered at %s - wrong URL, or the service is down." % url)
        return 1

    if not args.quick:
        print("")
        for q in QUESTIONS:
            ask(url, q)

    failed = [r for r in results if r[0] == FAIL]
    skipped = [r for r in results if r[0] == SKIP]
    print("\n%d passed, %d failed, %d skipped"
          % (len(results) - len(failed) - len(skipped), len(failed), len(skipped)))
    if failed:
        print("\nFailed:")
        for _, name, detail, _s in failed:
            print("  - %s" % name)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
