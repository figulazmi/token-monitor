"""
Tests for all Token Monitor API endpoints.
Runs against an in-memory SQLite DB — no PostgreSQL needed.
"""
import pytest

SESSION_PAYLOAD = {
    "platform":      "claude",
    "account":       "claude-azmi",
    "model":         "claude-sonnet-4-6",
    "input_tokens":  1000,
    "output_tokens": 300,
    "label":         "test session",
    "project":       "token-monitor",
}


# ── Health ───────────────────────────────────────────────────────────────────

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


# ── POST /sessions ────────────────────────────────────────────────────────────

def test_create_session_returns_201(client):
    r = client.post("/sessions", json=SESSION_PAYLOAD)
    assert r.status_code == 201


def test_create_session_calculates_cost(client):
    r = client.post("/sessions", json=SESSION_PAYLOAD)
    data = r.json()
    # sonnet: (1000/1M)*3 + (300/1M)*15 = 0.003 + 0.0045 = 0.0075
    assert round(data["cost_usd"], 6) == pytest.approx(0.0075, rel=1e-3)


def test_create_session_stores_account(client):
    r = client.post("/sessions", json=SESSION_PAYLOAD)
    assert r.json()["account"] == "claude-azmi"


def test_create_session_unassigned_account(client):
    payload = {**SESSION_PAYLOAD, "account": None}
    r = client.post("/sessions", json=payload)
    assert r.status_code == 201
    assert r.json()["account"] is None


def test_create_session_copilot(client):
    payload = {
        "platform":      "copilot",
        "account":       "copilot-azmi",
        "model":         "copilot-gpt4o",
        "input_tokens":  500,
        "output_tokens": 200,
        "label":         "copilot session",
    }
    r = client.post("/sessions", json=payload)
    assert r.status_code == 201
    assert r.json()["platform"] == "copilot"


# ── GET /sessions ─────────────────────────────────────────────────────────────

def test_list_sessions_empty(client):
    r = client.get("/sessions")
    assert r.status_code == 200
    assert r.json() == []


def test_list_sessions_returns_created(client):
    client.post("/sessions", json=SESSION_PAYLOAD)
    r = client.get("/sessions")
    assert len(r.json()) == 1


def test_list_sessions_filter_by_platform(client):
    client.post("/sessions", json=SESSION_PAYLOAD)
    client.post("/sessions", json={**SESSION_PAYLOAD, "platform": "copilot", "account": "copilot-azmi", "model": "copilot-gpt4o"})
    r = client.get("/sessions?platform=claude")
    assert all(s["platform"] == "claude" for s in r.json())
    assert len(r.json()) == 1


def test_list_sessions_filter_by_account(client):
    client.post("/sessions", json=SESSION_PAYLOAD)
    client.post("/sessions", json={**SESSION_PAYLOAD, "account": "claude-figur"})
    r = client.get("/sessions?account=claude-azmi")
    assert len(r.json()) == 1
    assert r.json()[0]["account"] == "claude-azmi"


def test_list_sessions_filter_by_project(client):
    client.post("/sessions", json=SESSION_PAYLOAD)
    client.post("/sessions", json={**SESSION_PAYLOAD, "project": "other-project"})
    r = client.get("/sessions?project=token-monitor")
    assert len(r.json()) == 1


def test_list_sessions_limit(client):
    for _ in range(5):
        client.post("/sessions", json=SESSION_PAYLOAD)
    r = client.get("/sessions?limit=3")
    assert len(r.json()) == 3


# ── PATCH /sessions/{id}/account ─────────────────────────────────────────────

def test_patch_account_assigns_account(client):
    r = client.post("/sessions", json={**SESSION_PAYLOAD, "account": None})
    session_id = r.json()["id"]

    r2 = client.patch(f"/sessions/{session_id}/account", json={"account": "claude-azmi"})
    assert r2.status_code == 200
    assert r2.json()["account"] == "claude-azmi"


def test_patch_account_can_unassign(client):
    r = client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = r.json()["id"]

    r2 = client.patch(f"/sessions/{session_id}/account", json={"account": None})
    assert r2.status_code == 200
    assert r2.json()["account"] is None


def test_patch_account_not_found(client):
    r = client.patch("/sessions/9999/account", json={"account": "claude-azmi"})
    assert r.status_code == 404


# ── DELETE /sessions/{id} ─────────────────────────────────────────────────────

def test_delete_session(client):
    r = client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = r.json()["id"]

    r2 = client.delete(f"/sessions/{session_id}")
    assert r2.status_code == 200
    assert r2.json() == {"deleted": session_id}


def test_delete_session_removes_from_list(client):
    r = client.post("/sessions", json=SESSION_PAYLOAD)
    session_id = r.json()["id"]
    client.delete(f"/sessions/{session_id}")

    assert client.get("/sessions").json() == []


def test_delete_session_not_found(client):
    r = client.delete("/sessions/9999")
    assert r.status_code == 404


# ── GET /stats ────────────────────────────────────────────────────────────────

def test_stats_empty_db(client):
    r = client.get("/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_sessions"] == 0
    assert body["total_cost_usd"] == 0


def test_stats_totals(client):
    client.post("/sessions", json=SESSION_PAYLOAD)
    r = client.get("/stats")
    body = r.json()
    assert body["total_sessions"] == 1
    assert body["total_input_tokens"] == 1000
    assert body["total_output_tokens"] == 300


def test_stats_by_platform(client):
    client.post("/sessions", json=SESSION_PAYLOAD)
    client.post("/sessions", json={**SESSION_PAYLOAD, "platform": "copilot", "account": "copilot-azmi", "model": "copilot-gpt4o"})
    body = client.get("/stats").json()
    platforms = {p["platform"] for p in body["by_platform"]}
    assert "claude" in platforms
    assert "copilot" in platforms


def test_stats_by_account(client):
    client.post("/sessions", json=SESSION_PAYLOAD)
    client.post("/sessions", json={**SESSION_PAYLOAD, "account": "claude-figur"})
    body = client.get("/stats").json()
    accounts = {a["account"] for a in body["by_account"]}
    assert "claude-azmi" in accounts
    assert "claude-figur" in accounts


def test_stats_by_model(client):
    client.post("/sessions", json=SESSION_PAYLOAD)
    body = client.get("/stats").json()
    models = [m["model"] for m in body["by_model"]]
    assert "claude-sonnet-4-6" in models


# ── Pricing accuracy ──────────────────────────────────────────────────────────

def test_pricing_opus(client):
    r = client.post("/sessions", json={**SESSION_PAYLOAD, "model": "claude-opus-4-6", "input_tokens": 1_000_000, "output_tokens": 0})
    assert r.json()["cost_usd"] == pytest.approx(15.0, rel=1e-3)


def test_pricing_haiku(client):
    r = client.post("/sessions", json={**SESSION_PAYLOAD, "model": "claude-haiku-4-5", "input_tokens": 0, "output_tokens": 1_000_000})
    assert r.json()["cost_usd"] == pytest.approx(4.0, rel=1e-3)
