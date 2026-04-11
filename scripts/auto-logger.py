#!/usr/bin/env python3
"""
auto-logger.py — Claude Code SessionEnd hook
Membaca usage dari hook input lalu POST ke Token Monitor API.

Setup di CLAUDE.md atau settings.json:
  hooks:
    SessionEnd:
      - command: python3 /path/to/auto-logger.py

Claude Code menginjeksi JSON ke stdin saat hook fire.
Docs: https://docs.claude.com/en/docs/claude-code/hooks
"""

import json
import os
import subprocess
import sys
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────
API_URL   = os.getenv("TOKEN_MONITOR_URL", "http://192.168.18.169:8000")
PLATFORM  = "claude"
MODEL     = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
PROJECT   = os.getenv("TOKEN_MONITOR_PROJECT", "")      # e.g. "petrochina-eproc"


def get_git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def get_label_from_git() -> str:
    """Ambil commit message terakhir sebagai label session."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=%s"],
            capture_output=True, text=True, timeout=3
        )
        return result.stdout.strip()[:120] if result.returncode == 0 else ""
    except Exception:
        return ""


def post_log(payload: dict) -> bool:
    """POST ke API menggunakan curl (stdlib-only untuk compatibility)."""
    try:
        body = json.dumps(payload)
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "-X", "POST",
             "-H", "Content-Type: application/json",
             "-d", body,
             f"{API_URL}/log"],
            capture_output=True, text=True, timeout=10
        )
        status_code = result.stdout.strip()
        return status_code == "200"
    except Exception as e:
        print(f"[auto-logger] ERROR posting log: {e}", file=sys.stderr)
        return False


def main():
    # Baca hook input dari stdin (JSON dari Claude Code)
    try:
        raw = sys.stdin.read()
        hook_data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        hook_data = {}

    # Ekstrak token usage dari hook payload
    # Format Claude Code SessionEnd hook:
    # { "session_id": "...", "usage": { "input_tokens": N, "output_tokens": N } }
    usage        = hook_data.get("usage", {})
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # Skip jika tidak ada usage data (session kosong)
    if input_tokens == 0 and output_tokens == 0:
        print("[auto-logger] No token usage detected, skipping.", file=sys.stderr)
        sys.exit(0)

    git_branch = get_git_branch()
    label      = get_label_from_git() or f"Session {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    project    = PROJECT or os.path.basename(os.getcwd())

    payload = {
        "platform":      PLATFORM,
        "model":         MODEL,
        "input_tokens":  input_tokens,
        "output_tokens": output_tokens,
        "label":         label,
        "git_branch":    git_branch,
        "project":       project,
    }

    success = post_log(payload)
    if success:
        total = input_tokens + output_tokens
        print(f"[auto-logger] Logged {total:,} tokens ({input_tokens:,} in / {output_tokens:,} out) → {API_URL}")
    else:
        print(f"[auto-logger] Failed to post log to {API_URL}", file=sys.stderr)


if __name__ == "__main__":
    main()
