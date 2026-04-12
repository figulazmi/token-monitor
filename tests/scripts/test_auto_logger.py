"""
Tests for scripts/auto-logger.py — account detection logic.
"""
import importlib.util
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

# ── Load module (hyphen in filename requires importlib) ───────────────────────
_SCRIPT_PATH = os.path.join(
    os.path.dirname(__file__),
    "../../src/scripts/auto-logger.py",
)

spec = importlib.util.spec_from_file_location("auto_logger", _SCRIPT_PATH)
auto_logger = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auto_logger)


# ── get_claude_account ────────────────────────────────────────────────────────

def test_env_var_override(monkeypatch):
    """CLAUDE_ACCOUNT env var takes highest priority."""
    monkeypatch.setenv("CLAUDE_ACCOUNT", "claude-azmi")
    assert auto_logger.get_claude_account() == "claude-azmi"


def test_env_var_figur(monkeypatch):
    monkeypatch.setenv("CLAUDE_ACCOUNT", "claude-figur")
    assert auto_logger.get_claude_account() == "claude-figur"


def test_auto_detect_azmi(monkeypatch):
    """Detect claude-azmi from claude auth status email."""
    monkeypatch.delenv("CLAUDE_ACCOUNT", raising=False)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"loggedIn": True, "email": "azmi.codes@gmail.com"})

    with patch("subprocess.run", return_value=mock_result):
        assert auto_logger.get_claude_account() == "claude-azmi"


def test_auto_detect_figur(monkeypatch):
    """Detect claude-figur from claude auth status email."""
    monkeypatch.delenv("CLAUDE_ACCOUNT", raising=False)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"loggedIn": True, "email": "figurululazmi@gmail.com"})

    with patch("subprocess.run", return_value=mock_result):
        assert auto_logger.get_claude_account() == "claude-figur"


def test_unknown_email_returns_none(monkeypatch):
    """Unknown email → UNASSIGNED (None)."""
    monkeypatch.delenv("CLAUDE_ACCOUNT", raising=False)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"loggedIn": True, "email": "unknown@example.com"})

    with patch("subprocess.run", return_value=mock_result):
        assert auto_logger.get_claude_account() is None


def test_claude_cli_not_found_returns_none(monkeypatch):
    """If claude CLI not installed → fallback to None."""
    monkeypatch.delenv("CLAUDE_ACCOUNT", raising=False)
    with patch("subprocess.run", side_effect=FileNotFoundError):
        assert auto_logger.get_claude_account() is None


def test_claude_cli_timeout_returns_none(monkeypatch):
    """If claude CLI times out → fallback to None."""
    import subprocess
    monkeypatch.delenv("CLAUDE_ACCOUNT", raising=False)
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 5)):
        assert auto_logger.get_claude_account() is None


def test_invalid_json_returns_none(monkeypatch):
    """If claude auth status returns invalid JSON → fallback to None."""
    monkeypatch.delenv("CLAUDE_ACCOUNT", raising=False)
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = "not valid json"

    with patch("subprocess.run", return_value=mock_result):
        assert auto_logger.get_claude_account() is None


def test_env_var_takes_priority_over_cli(monkeypatch):
    """CLAUDE_ACCOUNT env var beats claude auth status."""
    monkeypatch.setenv("CLAUDE_ACCOUNT", "claude-azmi")
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = json.dumps({"loggedIn": True, "email": "figurululazmi@gmail.com"})

    with patch("subprocess.run", return_value=mock_result):
        # Should return env var value, not detected email
        assert auto_logger.get_claude_account() == "claude-azmi"


# ── get_git_branch ────────────────────────────────────────────────────────────

def test_git_branch_returns_string():
    branch = auto_logger.get_git_branch()
    assert isinstance(branch, str)


def test_git_branch_on_failure():
    with patch("subprocess.run", side_effect=Exception("no git")):
        assert auto_logger.get_git_branch() == ""


# ── calc_cost (via pricing module) ────────────────────────────────────────────

def test_pricing_sonnet():
    from app.core.pricing import calc_cost
    cost = calc_cost("claude-sonnet-4-6", 1_000_000, 0)
    assert cost == pytest.approx(3.0)


def test_pricing_opus():
    from app.core.pricing import calc_cost
    cost = calc_cost("claude-opus-4-6", 0, 1_000_000)
    assert cost == pytest.approx(75.0)


def test_pricing_unknown_model_uses_default():
    from app.core.pricing import calc_cost
    cost = calc_cost("unknown-model", 1_000_000, 0)
    assert cost == pytest.approx(3.0)  # default input rate
