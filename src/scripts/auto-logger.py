#!/usr/bin/env python3
"""
auto-logger.py — Claude Code SessionEnd hook
Reads token usage from hook stdin then POSTs to Token Monitor API.

Account detection priority:
  1. CLAUDE_ACCOUNT env var (manual override)
  2. `claude auth status` → email → mapped to identifier
  3. None (logged as UNASSIGNED — assignable from dashboard)

Setup in global ~/.claude/settings.json (applies to ALL projects):
  {
    "hooks": {
      "SessionEnd": [{
        "matcher": "",
        "hooks": [{
          "type": "command",
          "command": "python C:\\Users\\Clandesitine\\source\\repos\\token-monitor\\scripts\\auto-logger.py"
        }]
      }]
    }
  }

Docs: https://docs.anthropic.com/en/docs/claude-code/hooks
"""

import json
import os
import subprocess
import sys
from datetime import datetime

# Fix Windows console encoding — prevents UnicodeEncodeError on cp1252 terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Config ───────────────────────────────────────────────────────────────────
API_URL  = os.getenv("TOKEN_MONITOR_URL", "http://192.168.18.169:8010")
PLATFORM = "claude"
MODEL    = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
PROJECT  = os.getenv("TOKEN_MONITOR_PROJECT", "")

# Email → account identifier mapping
# Add team members here before distributing the repo.
# Format: "email@domain.com": "claude-identifier"
EMAIL_ACCOUNT_MAP: dict[str, str] = {
    "azmi.codes@gmail.com":    "claude-azmi",
    "figurululazmi@gmail.com": "claude-figur",
    # "teammate@email.com":   "claude-teammate",   # ← add team members here
}


def get_claude_account() -> str | None:
    """
    Detect which Claude account is logged in.
    Priority: CLAUDE_ACCOUNT env var > claude auth status > None (UNASSIGNED).
    """
    # 1. Manual override via env var
    override = os.getenv("CLAUDE_ACCOUNT")
    if override:
        return override

    # 2. Auto-detect via `claude auth status`
    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout.strip())
            email = data.get("email", "")
            account = EMAIL_ACCOUNT_MAP.get(email)
            if account:
                return account
            # Email known but not in map → return email-based fallback
            if email:
                print(f"[auto-logger] Unknown email '{email}', logging as UNASSIGNED", file=sys.stderr)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError):
        pass

    # 3. Fallback: UNASSIGNED
    return None


def get_git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def get_label_from_git() -> str:
    """Use last commit message as session label."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip()[:120] if result.returncode == 0 else ""
    except Exception:
        return ""


def post_log(payload: dict) -> bool:
    """POST to API using curl (stdlib-only for broad compatibility)."""
    try:
        body = json.dumps(payload)
        result = subprocess.run(
            [
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
                "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", body,
                f"{API_URL}/sessions",
            ],
            capture_output=True, text=True, timeout=10,
        )
        return result.stdout.strip() in ("200", "201")
    except Exception as e:
        print(f"[auto-logger] ERROR posting log: {e}", file=sys.stderr)
        return False


def main_checkpoint():
    """
    Called via PostToolUse Write hook.
    Detects when a .claude/summaries/*.md file is written (RAG knowledge capture)
    and posts a checkpoint entry to the Token Monitor API.

    Stdin format (PostToolUse):
      { "tool_name": "Write", "tool_input": { "file_path": "...", "content": "..." }, ... }
    """
    try:
        raw = sys.stdin.read()
        hook_data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        hook_data = {}

    tool_input = hook_data.get("tool_input", {})
    file_path  = tool_input.get("file_path", "").replace("\\", "/")

    # Only act on .claude/summaries/*.md writes
    if "summaries/" not in file_path or not file_path.endswith(".md"):
        sys.exit(0)

    filename   = os.path.basename(file_path)
    account    = get_claude_account()
    git_branch = get_git_branch()
    project    = PROJECT or os.path.basename(os.getcwd())

    payload = {
        "platform":      PLATFORM,
        "account":       account,
        "model":         MODEL,
        "input_tokens":  0,
        "output_tokens": 0,
        "label":         f"RAG Capture: {filename}",
        "git_branch":    git_branch,
        "project":       project,
    }

    success = post_log(payload)
    if success:
        account_disp = account or "UNASSIGNED"
        print(f"[auto-logger] RAG checkpoint logged: {filename} [{account_disp}] -> {API_URL}")
    else:
        print(f"[auto-logger] Failed to post RAG checkpoint to {API_URL}", file=sys.stderr)


def main():
    # Read hook input from stdin
    # Format: { "session_id": "...", "usage": { "input_tokens": N, "output_tokens": N } }
    try:
        raw = sys.stdin.read()
        hook_data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        hook_data = {}

    usage         = hook_data.get("usage", {})
    input_tokens  = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    if input_tokens == 0 and output_tokens == 0:
        print("[auto-logger] No token usage detected, skipping.", file=sys.stderr)
        sys.exit(0)

    account    = get_claude_account()
    git_branch = get_git_branch()
    label      = get_label_from_git() or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    project    = PROJECT or os.path.basename(os.getcwd())

    payload = {
        "platform":      PLATFORM,
        "account":       account,         # None = UNASSIGNED, assignable from dashboard
        "model":         MODEL,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "label":         label,
        "git_branch":    git_branch,
        "project":       project,
    }

    success = post_log(payload)
    if success:
        total        = input_tokens + output_tokens
        account_disp = account or "UNASSIGNED"
        print(
            f"[auto-logger] Logged {total:,} tokens "
            f"({input_tokens:,} in / {output_tokens:,} out) "
            f"[{account_disp}] -> {API_URL}",
        )
    else:
        print(f"[auto-logger] Failed to post log to {API_URL}", file=sys.stderr)


if __name__ == "__main__":
    if "--checkpoint" in sys.argv:
        main_checkpoint()
    else:
        main()
