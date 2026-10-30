"""Tests for the hosted chat layer.

The model API itself is never called here. What is worth testing is the code between the model
and the tools: that the schemas handed to Gemini are derived from the live MCP tool list rather
than hand-written, that a function call comes back through ``mcp.call_tool`` and produces the
real number, that the loop stops, and that the free-question rationing counts.

A stub standing in for Gemini is what makes the loop testable at all; without it the only way to
exercise this path would be to spend money on every CI run.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from wwc27_medagent import chat


# --------------------------------------------------------------------------- schema shaping

def test_declarations_come_from_the_live_tool_list():
    """Nine tools are registered on the server; the model must be offered exactly those."""
    from wwc27_medagent.server import mcp

    decls = asyncio.run(chat.declarations())
    names = {d["name"] for d in decls}
    registered = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == registered, "the chat offers a different tool set than the MCP server"
    assert all(d["description"] for d in decls), "every tool needs a description to be callable"


def test_schema_is_reduced_to_what_gemini_accepts():
    """Pydantic emits 'title' on every field and anyOf for optionals; Gemini rejects both."""
    cleaned = chat._clean({
        "type": "object",
        "title": "estimate_heat_riskArguments",
        "properties": {
            "temperature_c": {"title": "Temperature C", "type": "number"},
            "domain": {"anyOf": [{"type": "string"}, {"type": "null"}], "title": "Domain",
                       "description": "optional filter"},
            "itinerary": {"type": "array", "items": {"type": "string", "title": "Item"}},
        },
        "required": ["temperature_c"],
    })
    assert "title" not in cleaned
    assert "title" not in cleaned["properties"]["temperature_c"]
    assert cleaned["properties"]["domain"] == {"type": "string", "nullable": True,
                                               "description": "optional filter"}
    assert cleaned["properties"]["itinerary"]["items"] == {"type": "string"}
    assert cleaned["required"] == ["temperature_c"]


def test_no_argument_tools_declare_no_parameters():
    """tournament_facts takes nothing, and an empty parameters object is rejected by the API."""
    decls = {d["name"]: d for d in asyncio.run(chat.declarations())}
    assert "parameters" not in decls["tournament_facts"]


# --------------------------------------------------------------------------- tool dispatch

def test_run_tool_returns_the_packages_own_answer():
    """The chat must not compute anything itself; 28 C at 85% is 32.4 C by core."""
    from wwc27_medagent import core

    out = asyncio.run(chat.run_tool("estimate_heat_risk",
                                    {"temperature_c": 28, "relative_humidity_pct": 85}))
    payload = json.loads(out)
    assert payload["indicative_swbgt_c"] == round(core.simplified_wbgt(28, 85), 1) == 32.4
    assert payload["band"] == "very high"
    assert payload["source"]["link"]


# --------------------------------------------------------------------------- the loop

class _Stub(BaseHTTPRequestHandler):
    """Replies with a function call first, then with text - the shape of a real exchange."""

    script: list = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        _Stub.seen.append(body)
        reply = _Stub.script[min(len(_Stub.seen) - 1, len(_Stub.script) - 1)]
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *a):
        pass


def _serve(script):
    _Stub.script = script
    _Stub.seen = []
    srv = HTTPServer(("127.0.0.1", 0), _Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def _text(t):
    return {"candidates": [{"content": {"parts": [{"text": t}]}}]}


def _call(name, args):
    return {"candidates": [{"content": {"parts": [{"functionCall": {"name": name,
                                                                    "args": args}}]}}]}


@pytest.fixture
def stub(monkeypatch):
    def start(script):
        srv = _serve(script)
        monkeypatch.setattr(chat, "API_ROOT", "http://127.0.0.1:%d" % srv.server_address[1])
        return srv
    yield start


def test_loop_calls_the_tool_and_feeds_the_result_back(stub):
    stub([_call("estimate_heat_risk", {"temperature_c": 28, "relative_humidity_pct": 85}),
          _text("32.4 C, very high.")])
    out = asyncio.run(chat.answer([{"role": "user", "text": "Salvador at 28 and 85?"}], "k"))
    assert out["answer"] == "32.4 C, very high."
    assert [t["name"] for t in out["tools"]] == ["estimate_heat_risk"]
    # the tool's real output must reach the model on the second request
    second = _Stub.seen[1]
    fed = json.dumps(second["contents"])
    assert "32.4" in fed, "the model was not given the tool's actual result"


def test_loop_stops_instead_of_calling_tools_for_ever(stub, monkeypatch):
    monkeypatch.setattr(chat, "MAX_TOOL_CALLS", 3)
    stub([_call("tournament_facts", {})])            # a stub that never stops asking
    out = asyncio.run(chat.answer([{"role": "user", "text": "loop"}], "k"))
    assert "more tool calls than the limit" in out["answer"]
    assert len(out["tools"]) == 3


def test_a_bad_argument_is_reported_to_the_model_not_raised(stub):
    stub([_call("get_venue_profile", {"city": "Reykjavik"}), _text("I don't know.")])
    out = asyncio.run(chat.answer([{"role": "user", "text": "Reykjavik?"}], "k"))
    assert out["answer"] == "I don't know."
    fed = json.dumps(_Stub.seen[1]["contents"])
    assert "error" in fed.lower() or "know" in fed.lower()


def test_system_prompt_and_tools_are_sent(stub):
    stub([_text("ok")])
    asyncio.run(chat.answer([{"role": "user", "text": "hi"}], "k"))
    sent = _Stub.seen[0]
    assert "paper agent" in sent["systemInstruction"]["parts"][0]["text"].lower()
    assert sent["tools"][0]["functionDeclarations"], "no tools were offered to the model"


# --------------------------------------------------------------------------- rationing

def test_free_questions_are_counted_per_caller(monkeypatch):
    monkeypatch.setattr(chat, "FREE_PER_DAY", 2)
    monkeypatch.setattr(chat, "_quota", {})
    monkeypatch.setattr(chat, "_spent", ("", 0))
    assert chat.free_left("1.2.3.4") == 2
    assert chat.take_free_question("1.2.3.4") is True
    assert chat.take_free_question("1.2.3.4") is True
    assert chat.take_free_question("1.2.3.4") is False, "a third free question was allowed"
    assert chat.free_left("1.2.3.4") == 0
    assert chat.take_free_question("5.6.7.8") is True, "one caller exhausted another's quota"


def test_a_global_ceiling_survives_a_caller_changing_address(monkeypatch):
    """The point of the global cap: per-caller rationing is per IP, and IPs are cheap.

    Without this, something with a pool of addresses gets FREE_PER_DAY questions per address
    and bills the house key for every one of them.
    """
    monkeypatch.setattr(chat, "FREE_PER_DAY", 8)
    monkeypatch.setattr(chat, "GLOBAL_PER_DAY", 3)
    monkeypatch.setattr(chat, "_quota", {})
    monkeypatch.setattr(chat, "_spent", ("", 0))

    taken = sum(chat.take_free_question("10.0.0.%d" % i) for i in range(20))
    assert taken == 3, "a fresh address kept earning free questions past the global cap"
    assert chat.global_left() == 0
    assert chat.free_left("10.0.0.99") == 0, "a new caller is told 0, not FREE_PER_DAY"


def test_hitting_the_global_cap_does_not_consume_a_callers_own_quota(monkeypatch):
    """Refusing for the instance's reason must not also spend the visitor's day."""
    monkeypatch.setattr(chat, "FREE_PER_DAY", 5)
    monkeypatch.setattr(chat, "GLOBAL_PER_DAY", 1)
    monkeypatch.setattr(chat, "_quota", {})
    monkeypatch.setattr(chat, "_spent", ("", 0))

    assert chat.take_free_question("1.1.1.1") is True
    assert chat.take_free_question("2.2.2.2") is False
    monkeypatch.setattr(chat, "GLOBAL_PER_DAY", 9)        # as a new day would
    assert chat._quota.get("2.2.2.2") is None, "the refused caller was charged anyway"
    assert chat.free_left("2.2.2.2") == 5


def test_a_400_distinguishes_a_bad_key_from_a_bad_request():
    """Both arrive as 400 INVALID_ARGUMENT and need opposite actions from the reader."""
    bad_key = json.dumps({"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                    "message": "API key not valid. Please pass a valid API key.",
                                    "details": [{"reason": "API_KEY_INVALID"}]}})
    assert "rejected the key itself" in chat._explain(400, bad_key)

    bad_request = json.dumps({"error": {"code": 400, "status": "INVALID_ARGUMENT",
                                        "message": "Invalid JSON payload received."}})
    out = chat._explain(400, bad_request)
    assert "fault in the agent" in out, "a malformed request blamed the reader's key"
    assert "Invalid JSON payload" in out, "Google's own message was discarded"


def test_a_disabled_api_is_not_reported_as_a_bad_key():
    detail = json.dumps({"error": {"code": 403, "message": "Generative Language API has not been "
                                   "used in project 123 before or it is disabled.",
                                   "details": [{"reason": "SERVICE_DISABLED"}]}})
    assert "not allowed to use this API" in chat._explain(403, detail)


def test_explain_survives_a_body_that_is_not_json():
    """Gateways return HTML, not JSON; parsing it must not raise on the error path."""
    assert "server error" in chat._explain(502, "<html>gateway</html>")
    assert chat._reason("<html>gateway</html>") == ("", "")
    assert "404" in chat._explain(404, ""), "an unmapped code should still name itself"


def test_history_is_trimmed_so_a_long_thread_cannot_grow_without_bound(stub, monkeypatch):
    monkeypatch.setattr(chat, "MAX_HISTORY", 4)
    stub([_text("ok")])
    history = [{"role": "user", "text": "q%d" % i} for i in range(20)]
    asyncio.run(chat.answer(history, "k"))
    assert len(_Stub.seen[0]["contents"]) == 4
