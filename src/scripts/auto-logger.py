#!/usr/bin/env python3
"""
auto-logger.py — Claude Code SessionEnd hook
Reads token usage from hook stdin then POSTs to Token Monitor API.

Standalone script — no dependencies on the repo. Download once, never update.

Account detection priority:
  1. CLAUDE_ACCOUNT env var (set at hook install time via setup-hook.py)
  2. `claude auth status` → email → slug (local-part, dots→dashes, lowercase)
     e.g. azmi.codes@gmail.com → "azmi-codes"
          figurululazmi@gmail.com → "figurululazmi"
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

import glob
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

def get_claude_account() -> str | None:
    """
    Detect which Claude account is logged in.
    Priority: CLAUDE_ACCOUNT env var > email-derived slug > None (UNASSIGNED).
    """
    # 1. Explicit override (set at hook install time via setup-hook.py or manual config)
    override = os.getenv("CLAUDE_ACCOUNT")
    if override:
        return override

    # 2. Derive identifier from logged-in email: local-part, dots→dashes, lowercase
    #    e.g. azmi.codes@gmail.com → "azmi-codes"
    #         figurululazmi@gmail.com → "figurululazmi"
    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            data  = json.loads(result.stdout.strip())
            email = data.get("email", "")
            if email:
                username = email.split("@")[0].replace(".", "-").lower()
                return username
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


def get_tokens_from_jsonl(session_id: str) -> tuple[int, int]:
    """
    Read token totals for a session from Claude Code's local JSONL files.

    Claude Code's SessionEnd hook does NOT pass usage in stdin — the token data
    lives in ~/.claude/projects/<slug>/<session-id>.jsonl as per-message usage
    on each assistant entry.

    Sums across all assistant messages:
      input  = input_tokens + cache_creation_input_tokens + cache_read_input_tokens
      output = output_tokens
    """
    if not session_id:
        return 0, 0

    claude_home = os.path.expanduser("~/.claude")
    pattern = os.path.join(claude_home, "projects", "**", f"{session_id}.jsonl")
    files = glob.glob(pattern, recursive=True)
    if not files:
        return 0, 0

    total_input = 0
    total_output = 0
    try:
        with open(files[0], encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    d = json.loads(line)
                    if d.get("type") != "assistant":
                        continue
                    usage = d.get("message", {}).get("usage", {})
                    total_input += (
                        usage.get("input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                    )
                    total_output += usage.get("output_tokens", 0)
                except (json.JSONDecodeError, AttributeError):
                    pass
    except Exception as e:
        print(f"[auto-logger] WARN: could not read JSONL for session {session_id}: {e}", file=sys.stderr)

    return total_input, total_output


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

    session_id = hook_data.get("session_id", "")

    # Claude Code does NOT send usage in SessionEnd stdin — read from local JSONL.
    # Fall back to stdin usage field only if JSONL yields nothing (future-proofing).
    input_tokens, output_tokens = get_tokens_from_jsonl(session_id)
    if input_tokens == 0 and output_tokens == 0:
        stdin_usage   = hook_data.get("usage", {})
        input_tokens  = stdin_usage.get("input_tokens", 0)
        output_tokens = stdin_usage.get("output_tokens", 0)

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
