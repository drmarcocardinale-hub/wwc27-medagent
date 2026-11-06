"""Tests for the hosted app's HTTP surface.

These exist because of a fault that reached production: the MCP SDK enables DNS-rebinding
protection and allows only localhost, so the deployed /mcp answered 421 "Invalid Host header"
to every remote client - the endpoint cited in the paper refusing everyone - while every local
probe passed, because a local probe sends a localhost Host header.

So the rule here: assert against a Host header that is NOT localhost. A test that only ever
sends 127.0.0.1 reproduces the blind spot rather than closing it.

One structural constraint shapes the rest. Under mcp 1.x, streamable_http_app() binds a single
StreamableHTTPSessionManager to the server singleton and its run() may be called only once per
instance, so a second build_app() in the same session raises. (2.x builds a new manager each
time, which is why an earlier version of this file passed locally and failed the whole 1.x half
of the CI matrix.) Hence: exactly one real app per module, and anything needing different
configuration is tested without building a second one.
"""
from __future__ import annotations

import json

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from wwc27_medagent import web

REMOTE = "wwc27-medagent-919325462297.europe-west1.run.app"

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "1"}}}


@pytest.fixture(scope="module")
def client():
    """The one real app for this module; see the note above on why there can only be one."""
    mp = pytest.MonkeyPatch()
    mp.setenv("MCP_STATELESS", "1")
    mp.delenv("MCP_ALLOWED_HOSTS", raising=False)
    try:
        with TestClient(web.build_app()) as c:
            yield c
    finally:
        mp.undo()


def _mcp(client, host):
    return client.post("/mcp", json=INIT,
                       headers={"Host": host,
                                "Accept": "application/json, text/event-stream"})


def test_mcp_answers_a_remote_host_not_just_localhost(client):
    """The production fault: 421 to every client whose Host is not localhost."""
    r = _mcp(client, REMOTE)
    assert r.status_code != 421, "the MCP endpoint refuses remote clients: %s" % r.text
    assert r.status_code == 200, r.text
    assert "wwc27-medagent" in r.text


def test_mcp_still_answers_locally(client):
    assert _mcp(client, "127.0.0.1:8000").status_code == 200


def test_the_chat_surface_answers_a_remote_host(client):
    r = client.get("/api/meta", headers={"Host": REMOTE})
    assert r.status_code == 200
    assert r.json()["version"]


def test_the_page_and_mcp_coexist(client):
    """The mount must not shadow the chat routes, nor the routes swallow /mcp."""
    assert client.get("/", headers={"Host": REMOTE}).status_code == 200
    assert _mcp(client, REMOTE).status_code == 200
    assert json.loads(client.get("/api/meta", headers={"Host": REMOTE}).text)["model"]


# --------------------------------------------------------------- configuration, without an app

def test_an_allowlist_is_honoured_when_set(monkeypatch):
    """Anyone running this behind a known hostname should be able to keep the check on."""
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", REMOTE)
    settings = web.transport_security()
    assert settings.enable_dns_rebinding_protection is True
    assert REMOTE in settings.allowed_hosts

    monkeypatch.delenv("MCP_ALLOWED_HOSTS")
    assert web.transport_security().enable_dns_rebinding_protection is False


def test_the_settings_actually_reach_the_mcp_app(monkeypatch):
    """Configuring the allowlist is worthless if build_app does not pass it on. Checked by
    capturing the call rather than by building a second app, which 1.x forbids."""
    from wwc27_medagent import server

    seen = {}

    def fake_app(**kwargs):
        seen.update(kwargs)
        return Starlette(routes=[])

    monkeypatch.setenv("MCP_ALLOWED_HOSTS", REMOTE)
    monkeypatch.setattr(server.mcp, "streamable_http_app", fake_app)
    web.build_app()

    got = seen.get("transport_security")
    assert got is not None, f"transport_security was not passed on; got {sorted(seen)}"
    assert REMOTE in got.allowed_hosts
    assert got.enable_dns_rebinding_protection is True
