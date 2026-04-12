#!/usr/bin/env python3
"""
setup-hook.py - Token Monitor hook installer for Claude Code

Patches ~/.claude/settings.json to register:
  - SessionEnd hook    → logs token usage on /exit or /clear
  - PostToolUse Write  → logs RAG capture checkpoint when summary is saved

Usage:
    python setup-hook.py                          # interactive setup
    python setup-hook.py --account claude-yourname
    python setup-hook.py --api-url http://192.168.x.x:8010
    python setup-hook.py --dry-run                # preview without writing
    python setup-hook.py --uninstall              # remove hooks
"""

import argparse
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

# Fix Windows console encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).resolve().parent
AUTO_LOGGER = SCRIPT_DIR / "auto-logger.py"

# ── Defaults ──────────────────────────────────────────────────────────────────
DEFAULT_API_URL   = "http://192.168.18.169:8010"
DEFAULT_DASHBOARD = "http://192.168.18.169:3010"
HOOK_MARKER       = "auto-logger.py"   # used to detect existing hook entries


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_settings_path() -> Path:
    return Path.home() / ".claude" / "settings.json"


def load_settings(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[WARN] Could not read {path}: {e}")
            print("       Starting with empty settings.")
    return {}


def build_command(script_path: Path, extra_args: str = "", env_prefix: str = "") -> str:
    """
    Build shell command string for the hook.

    On Windows (bash / Git Bash):
      python "C:\\Users\\...\\auto-logger.py" [extra_args]
      Quoting the path prevents bash from stripping backslashes.

    On Linux / macOS:
      python3 "/home/.../.../auto-logger.py" [extra_args]
    """
    python = "python" if platform.system() == "Windows" else "python3"
    parts  = []

    if env_prefix:
        parts.append(env_prefix.strip())

    parts.append(f'{python} "{script_path}"')

    if extra_args:
        parts.append(extra_args.strip())

    return " ".join(parts)


def hook_already_installed(hooks_list: list, marker: str) -> bool:
    """Return True if any hook in the list already references auto-logger."""
    for entry in hooks_list:
        for h in entry.get("hooks", []):
            if marker in h.get("command", ""):
                return True
    return False


def merge_hooks(settings: dict, new_hooks: dict) -> tuple[dict, list[str]]:
    """
    Merge new_hooks into settings without overwriting existing entries.
    Returns (updated_settings, list_of_actions_taken).
    """
    result  = settings.copy()
    hooks   = result.setdefault("hooks", {})
    actions = []

    for event, entries in new_hooks.items():
        existing = hooks.setdefault(event, [])
        for entry in entries:
            cmd = entry["hooks"][0]["command"]
            if hook_already_installed(existing, HOOK_MARKER):
                actions.append(f"SKIP  {event} - hook already present")
            else:
                existing.append(entry)
                actions.append(f"ADD   {event} -> {cmd[:80]}...")

    return result, actions


def remove_hooks(settings: dict) -> tuple[dict, list[str]]:
    """Remove all hook entries that reference auto-logger.py."""
    result  = settings.copy()
    hooks   = result.get("hooks", {})
    actions = []

    for event in list(hooks.keys()):
        before = hooks[event]
        after  = [
            entry for entry in before
            if not hook_already_installed([entry], HOOK_MARKER)
        ]
        removed = len(before) - len(after)
        if removed:
            actions.append(f"REMOVE {event} ({removed} hook(s))")
        hooks[event] = after
        if not hooks[event]:
            del hooks[event]

    return result, actions


def test_api(api_url: str) -> bool:
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
             "--connect-timeout", "4", f"{api_url}/health"],
            capture_output=True, text=True, timeout=8,
        )
        return result.stdout.strip() == "200"
    except Exception:
        return False


def detect_account() -> str | None:
    """Try to detect the logged-in Claude account identifier."""
    try:
        result = subprocess.run(
            ["claude", "auth", "status"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            data  = json.loads(result.stdout.strip())
            email = data.get("email", "")
            if email:
                return email
    except Exception:
        pass
    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Token Monitor hook installer for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--account",   help="CLAUDE_ACCOUNT value (e.g. claude-yourname)")
    parser.add_argument("--api-url",   default=DEFAULT_API_URL, help="Token Monitor API URL")
    parser.add_argument("--dry-run",   action="store_true", help="Preview changes without writing")
    parser.add_argument("--uninstall", action="store_true", help="Remove hooks from settings.json")
    args = parser.parse_args()

    # ── Banner ────────────────────────────────────────────────────────────────
    print()
    print("  Token Monitor - Hook Installer")
    print("  " + "=" * 38)
    print()

    # ── Verify auto-logger.py exists ──────────────────────────────────────────
    if not AUTO_LOGGER.exists():
        print(f"  [ERROR] auto-logger.py not found at:")
        print(f"          {AUTO_LOGGER}")
        print()
        print("  Make sure you cloned the full token-monitor repository.")
        sys.exit(1)

    print(f"  Script : {AUTO_LOGGER}")

    # ── Detect / prompt account ───────────────────────────────────────────────
    account_flag = ""
    if not args.uninstall:
        account = args.account
        if not account:
            detected_email = detect_account()
            if detected_email:
                print(f"  Account: {detected_email} (auto-detected)")
                print()
                name = input(
                    "  Enter your CLAUDE_ACCOUNT identifier\n"
                    "  (e.g. claude-yourname, or press Enter to auto-detect at runtime): "
                ).strip()
                if name:
                    account = name
            else:
                print("  Could not auto-detect Claude account.")
                name = input(
                    "  Enter your CLAUDE_ACCOUNT identifier\n"
                    "  (e.g. claude-yourname, or press Enter to skip): "
                ).strip()
                if name:
                    account = name

        if account:
            account_flag = f"CLAUDE_ACCOUNT={account}"
            print(f"  Account: {account}")

    print(f"  API URL: {args.api_url}")
    print()

    # ── Build hook commands ───────────────────────────────────────────────────
    env_prefix = account_flag
    if args.api_url != DEFAULT_API_URL:
        env_prefix = f"TOKEN_MONITOR_URL={args.api_url} {env_prefix}".strip()

    session_cmd    = build_command(AUTO_LOGGER, env_prefix=env_prefix)
    checkpoint_cmd = build_command(AUTO_LOGGER, extra_args="--checkpoint", env_prefix=env_prefix)

    new_hooks = {
        "SessionEnd": [{
            "matcher": "",
            "hooks": [{"type": "command", "command": session_cmd}],
        }],
        "PostToolUse": [{
            "matcher": "Write",
            "hooks": [{"type": "command", "command": checkpoint_cmd}],
        }],
    }

    # ── Load existing settings ────────────────────────────────────────────────
    settings_path = get_settings_path()
    existing      = load_settings(settings_path)

    # ── Apply changes ─────────────────────────────────────────────────────────
    if args.uninstall:
        updated, actions = remove_hooks(existing)
    else:
        updated, actions = merge_hooks(existing, new_hooks)

    # ── Print diff ────────────────────────────────────────────────────────────
    print("  Changes:")
    if actions:
        for action in actions:
            print(f"    {action}")
    else:
        print("    (nothing to change)")
    print()

    if args.dry_run:
        print("  [DRY RUN] Would write to:", settings_path)
        print()
        print(json.dumps(updated, indent=2))
        return

    # ── Write settings ────────────────────────────────────────────────────────
    if not actions or all(a.startswith("SKIP") for a in actions):
        print("  Nothing changed.")
    else:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(
            json.dumps(updated, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        verb = "Uninstalled" if args.uninstall else "Installed"
        print(f"  [{verb}] {settings_path}")

    if args.uninstall:
        print()
        print("  Hooks removed. Restart Claude Code to apply.")
        return

    # ── Test API connectivity ─────────────────────────────────────────────────
    print("  Testing API connectivity...")
    if test_api(args.api_url):
        print(f"  [OK] API reachable at {args.api_url}")
    else:
        print(f"  [WARN] API not reachable at {args.api_url}")
        print("         Token logs will be lost if API is down when hooks fire.")
        print("         Check: is VM B1 online and on the same network?")

    # ── Next steps ────────────────────────────────────────────────────────────
    dashboard = args.api_url.replace(":8010", ":3010")
    print()
    print("  Setup complete!")
    print()
    print("  Next steps:")
    print("  1. Restart Claude Code to activate the hooks")
    print("  2. Open any project and run /exit - a session entry should appear at:")
    print(f"     {dashboard}")
    print()
    if not account_flag:
        print("  NOTE: No account set. Sessions will be logged as UNASSIGNED.")
        print("        Ask the repo owner to add your email to EMAIL_ACCOUNT_MAP")
        print(f"        in: {AUTO_LOGGER}")
        print()


if __name__ == "__main__":
    main()
