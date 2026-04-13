#!/usr/bin/env python3
"""
Token Monitor — Hook Installer
Installs the auto-logger.py SessionEnd hook for Claude Code.

Usage:
    python install.py                  # interactive
    python install.py --api-url http://192.168.18.169:8010
    python install.py --account copilot-azmi
    python install.py --uninstall

What this does:
  1. Copies auto-logger.py to ~/.claude/hooks/auto-logger.py
  2. Writes ~/.claude/token-monitor.json with your API URL + account config
  3. Patches ~/.claude/settings.json with SessionEnd + PostToolUse hooks

After install, every Claude Code session on this machine automatically logs
token usage to your Token Monitor dashboard.
"""

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR   = Path(__file__).parent
REPO_ROOT    = SCRIPT_DIR.parent
AUTO_LOGGER  = REPO_ROOT / "src" / "scripts" / "auto-logger.py"

CLAUDE_HOME  = Path.home() / ".claude"
HOOKS_DIR    = CLAUDE_HOME / "hooks"
HOOK_DEST    = HOOKS_DIR / "auto-logger.py"
CONFIG_FILE  = CLAUDE_HOME / "token-monitor.json"
SETTINGS     = CLAUDE_HOME / "settings.json"

IS_WINDOWS   = platform.system() == "Windows"


# ── Hook commands ─────────────────────────────────────────────────────────────
def hook_cmd(dest: Path) -> str:
    if IS_WINDOWS:
        return f'python "{dest}"'
    return f'python3 {dest}'

def checkpoint_cmd(dest: Path) -> str:
    if IS_WINDOWS:
        return f'python "{dest}" --checkpoint'
    return f'python3 {dest} --checkpoint'


# ── Settings.json helpers ─────────────────────────────────────────────────────
def load_settings() -> dict:
    if SETTINGS.exists():
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_settings(data: dict) -> None:
    SETTINGS.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"  Updated {SETTINGS}")


def has_hook(entries: list, marker: str) -> bool:
    return any(
        marker in h.get("command", "")
        for entry in entries
        for h in entry.get("hooks", [])
    )


def remove_hook(entries: list, marker: str) -> list:
    cleaned = []
    for entry in entries:
        entry["hooks"] = [
            h for h in entry.get("hooks", [])
            if marker not in h.get("command", "")
        ]
        if entry["hooks"]:
            cleaned.append(entry)
    return cleaned


# ── Install ───────────────────────────────────────────────────────────────────
def install(api_url: str, account: str | None, model: str) -> None:
    print("\n[1/4] Copying auto-logger.py to ~/.claude/hooks/")
    HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUTO_LOGGER, HOOK_DEST)
    if not IS_WINDOWS:
        HOOK_DEST.chmod(0o755)
    print(f"  {AUTO_LOGGER} -> {HOOK_DEST}")

    print("\n[2/4] Writing ~/.claude/token-monitor.json")
    config = {"api_url": api_url, "model": model}
    if account:
        config["account"] = account
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"  {CONFIG_FILE}")
    print(f"  api_url : {api_url}")
    print(f"  account : {account or '(auto-detect from claude auth status)'}")
    print(f"  model   : {model}")

    print("\n[3/4] Patching ~/.claude/settings.json")
    settings = load_settings()
    hooks = settings.setdefault("hooks", {})

    # SessionEnd
    session_end = hooks.setdefault("SessionEnd", [])
    if not has_hook(session_end, "auto-logger"):
        session_end.append({
            "matcher": "",
            "hooks": [{"type": "command", "command": hook_cmd(HOOK_DEST)}],
        })
        print("  + SessionEnd hook added")
    else:
        print("  SessionEnd hook already present (skipped)")

    # PostToolUse checkpoint
    post_tool = hooks.setdefault("PostToolUse", [])
    if not has_hook(post_tool, "auto-logger"):
        post_tool.append({
            "matcher": "Write",
            "hooks": [{"type": "command", "command": checkpoint_cmd(HOOK_DEST)}],
        })
        print("  + PostToolUse Write hook added")
    else:
        print("  PostToolUse hook already present (skipped)")

    save_settings(settings)

    print("\n[4/4] Verifying setup")
    _verify(api_url)


# ── Uninstall ─────────────────────────────────────────────────────────────────
def uninstall() -> None:
    print("\n[1/3] Removing hook from ~/.claude/settings.json")
    settings = load_settings()
    hooks = settings.get("hooks", {})
    hooks["SessionEnd"] = remove_hook(hooks.get("SessionEnd", []), "auto-logger")
    hooks["PostToolUse"] = remove_hook(hooks.get("PostToolUse", []), "auto-logger")
    save_settings(settings)

    print("\n[2/3] Removing ~/.claude/hooks/auto-logger.py")
    if HOOK_DEST.exists():
        HOOK_DEST.unlink()
        print(f"  Deleted {HOOK_DEST}")
    else:
        print("  Not found (already removed)")

    print("\n[3/3] Removing ~/.claude/token-monitor.json")
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
        print(f"  Deleted {CONFIG_FILE}")
    else:
        print("  Not found (already removed)")

    print("\nToken Monitor hook uninstalled.")


# ── Verify ────────────────────────────────────────────────────────────────────
def _verify(api_url: str) -> None:
    import subprocess
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"{api_url}/health"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip() == "200":
            print(f"  API reachable: {api_url}/health -> 200 OK")
        else:
            print(f"  WARNING: API returned {result.stdout.strip()} - is the server running?")
            print(f"    Check: {api_url}/health")
    except Exception as e:
        print(f"  WARNING: Could not reach {api_url} ({type(e).__name__})")
        print("    Start the server first, or check TOKEN_MONITOR_URL")


# ── Main ──────────────────────────────────────────────────────────────────────
def prompt(msg: str, default: str) -> str:
    val = input(f"{msg} [{default}]: ").strip()
    return val if val else default


def main() -> None:
    parser = argparse.ArgumentParser(description="Token Monitor hook installer")
    parser.add_argument("--api-url",   default=None, help="Token Monitor API URL")
    parser.add_argument("--account",   default=None, help="Account identifier (skip for auto-detect)")
    parser.add_argument("--model",     default=None, help="Claude model identifier")
    parser.add_argument("--uninstall", action="store_true", help="Remove hooks and config")
    parser.add_argument("--yes",       action="store_true", help="Non-interactive (use defaults)")
    args = parser.parse_args()

    print("Token Monitor — Hook Installer")
    print("=" * 40)

    if args.uninstall:
        uninstall()
        return

    if not AUTO_LOGGER.exists():
        print(f"ERROR: auto-logger.py not found at {AUTO_LOGGER}")
        print("Run this script from the token-monitor repo root.")
        sys.exit(1)

    # Resolve config values
    if args.yes:
        api_url = args.api_url or "http://localhost:8010"
        account = args.account
        model   = args.model or "claude-sonnet-4-6"
    else:
        print("\nConfigure your Token Monitor connection:")
        api_url = args.api_url or prompt("API URL", "http://localhost:8010")
        print("\nAccount identifier (leave blank to auto-detect from 'claude auth status')")
        print("  Example: azmi-codes, figurululazmi, copilot-azmi")
        account_raw = args.account if args.account is not None else input("Account [auto]: ").strip()
        account = account_raw if account_raw else None
        model   = args.model or prompt("Model", "claude-sonnet-4-6")

    install(api_url, account, model)

    print("\nInstallation complete.")
    print(f"Dashboard: {api_url.replace('8010', '3010') if '8010' in api_url else api_url}")
    print("Token usage will be logged automatically on every Claude Code session end.")


if __name__ == "__main__":
    main()
