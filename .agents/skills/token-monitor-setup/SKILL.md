---
name: token-monitor-setup
description: >
  Install and configure the Token Monitor SessionEnd hook for Claude Code.
  Automatically logs token usage to your Token Monitor dashboard after every
  Claude Code session. Supports Windows, macOS, and Linux. Detects Claude account
  from `claude auth status`. Runs install.py then verifies API connectivity.
---

# Token Monitor Setup Skill

## Purpose

Install the `auto-logger.py` SessionEnd hook so Claude Code automatically logs
token usage to a Token Monitor dashboard after every session.

After setup, token data flows like this:
```
/exit or Ctrl-C
  └─ SessionEnd hook fires
       └─ auto-logger.py reads ~/.claude/projects/**/<session-id>.jsonl
            └─ POST /sessions → Token Monitor API
                 └─ Dashboard updated
```

---

## Step 1 — Confirm prerequisites

Ask the user:
1. **Where is the token-monitor repo?** (path on this machine, or should they clone it first)
2. **What is the Token Monitor API URL?** (e.g. `http://192.168.18.169:8010` or `http://localhost:8010`)
3. **Account override needed?** — Only if they use GitHub Copilot or have multiple Claude accounts.
   Auto-detection from `claude auth status` covers most cases.

If the repo is not cloned yet, instruct them:
```bash
git clone https://github.com/<owner>/token-monitor.git
cd token-monitor
```

---

## Step 2 — Run the installer

Run the cross-platform installer. It copies `auto-logger.py` to `~/.claude/hooks/`,
writes the config, and patches `~/.claude/settings.json` automatically.

**Interactive (recommended for first install):**
```bash
python scripts/install.py
```

**Non-interactive (CI / scripted setup):**
```bash
# Replace URL and account with actual values
python scripts/install.py --api-url http://192.168.18.169:8010 --yes

# With explicit account override (e.g. Copilot sessions)
python scripts/install.py --api-url http://192.168.18.169:8010 --account copilot-azmi --yes
```

**Windows note:** use `python` (not `python3`). The installer auto-detects the OS
and writes the correct hook command format for cmd.exe.

---

## Step 3 — Verify installation

Check that the hook was added to settings.json:
```bash
# Show SessionEnd hooks
python -c "import json; s=json.load(open('C:/Users/<user>/.claude/settings.json')); print(json.dumps(s.get('hooks',{}), indent=2))"
```

Check API connectivity:
```bash
curl http://<api-url>/health
# Expected: {"status":"ok","timestamp":"..."}
```

Test the hook manually (requires a real session JSONL file):
```bash
# Find a real session ID
ls ~/.claude/projects/**/*.jsonl

# Feed it to the script as the hook would
echo '{"session_id":"<paste-session-id>"}' | python ~/.claude/hooks/auto-logger.py
# Expected: [auto-logger] Logged X tokens (Y in / Z out) [account] -> http://...
```

---

## Step 4 — Open the dashboard

Navigate to the Token Monitor dashboard to see logged sessions:
```
http://<server-ip>:3010
```

---

## Uninstall

To remove all hooks and config:
```bash
python scripts/install.py --uninstall
```

---

## Config file

The installer writes `~/.claude/token-monitor.json`:
```json
{
  "api_url": "http://192.168.18.169:8010",
  "model": "claude-sonnet-4-6",
  "account": "figurululazmi"   // omit for auto-detect
}
```

This config is the fallback for Windows where env vars cannot be set inline in hook commands.
Env vars always take priority over this file.

| Key       | Env var override         | Purpose                             |
|-----------|--------------------------|-------------------------------------|
| `api_url` | `TOKEN_MONITOR_URL`      | API endpoint                        |
| `account` | `CLAUDE_ACCOUNT`         | Account identifier (override only)  |
| `model`   | `CLAUDE_MODEL`           | Model name tag                      |
| —         | `TOKEN_MONITOR_PROJECT`  | Project tag (CWD folder if omitted) |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `[auto-logger] No token usage detected, skipping.` | Session JSONL not found — check `~/.claude/projects/` exists and session was long enough to write data |
| `[auto-logger] Failed to post log` | API unreachable — verify `api_url` in `~/.claude/token-monitor.json` and that the server is running |
| Hook not firing | Verify `~/.claude/settings.json` contains `SessionEnd` hook pointing to `~/.claude/hooks/auto-logger.py` |
| Wrong account shown | Set `account` in `~/.claude/token-monitor.json` or `CLAUDE_ACCOUNT` env var |
| `python: command not found` (Linux/macOS) | Install Python 3 — hook uses `python3` on non-Windows |
