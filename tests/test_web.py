"""Tests for the hosted app's HTTP surface.

These exist because of a fault that reached production: the MCP SDK enables DNS-rebinding
protection and allows only localhost, so the deployed /mcp answered 421 "Invalid Host header"
to every remote client - the endpoint cited in the paper refusing everyone - while every local
probe passed, because a local probe sends a localhost Host header.

So the rule here: assert against a Host header that is NOT localhost. A test that only ever
sends 127.0.0.1 reproduces the blind spot rather than closing it.
"""
from __future__ import annotations

import json

import pytest
from starlette.testclient import TestClient

from wwc27_medagent import web

REMOTE = "wwc27-medagent-919325462297.europe-west1.run.app"

INIT = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                   "clientInfo": {"name": "test", "version": "1"}}}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("MCP_STATELESS", "1")
    monkeypatch.delenv("MCP_ALLOWED_HOSTS", raising=False)
    with TestClient(web.build_app()) as c:
        yield c


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


def test_an_allowlist_is_honoured_when_set(monkeypatch):
    """Anyone running this behind a known hostname should be able to keep the check on."""
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", REMOTE)
    settings = web.transport_security()
    assert settings.enable_dns_rebinding_protection is True
    assert REMOTE in settings.allowed_hosts

    monkeypatch.delenv("MCP_ALLOWED_HOSTS")
    assert web.transport_security().enable_dns_rebinding_protection is False


def test_an_allowlist_actually_refuses_a_host_outside_it(monkeypatch):
    monkeypatch.setenv("MCP_STATELESS", "1")
    monkeypatch.setenv("MCP_ALLOWED_HOSTS", "only-this-host.example")
    with TestClient(web.build_app()) as c:
        assert _mcp(c, REMOTE).status_code == 421, "the allowlist is not being applied"
        assert _mcp(c, "only-this-host.example").status_code == 200


def test_the_page_and_mcp_coexist(client):
    """The mount must not shadow the chat routes, nor the routes swallow /mcp."""
    assert client.get("/", headers={"Host": REMOTE}).status_code == 200
    assert _mcp(client, REMOTE).status_code == 200
    assert json.loads(client.get("/api/meta", headers={"Host": REMOTE}).text)["model"]
