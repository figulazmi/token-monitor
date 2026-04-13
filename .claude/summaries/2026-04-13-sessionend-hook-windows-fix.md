---
id: 2026-04-13-sessionend-hook-windows-fix
date: 2026-04-13
source: claude-code-cli
project: homelab
topic: Claude Code SessionEnd Hook Not Firing on Windows - Fix
tags: [claude-code, hooks, windows, cmd-exe, auto-logger, token-monitor, fixed, homelab]
related: [auto-logger-setup, token-monitor-deployment]
session_type: debug
environment: homelab
git_branch: main
status: implemented
chunk_source: code
---

## CHUNK 1: SessionEnd Hook Silently Fails on Windows Due to Bash Syntax in cmd.exe

### Context

Token-monitor uses a Claude Code `SessionEnd` hook in the global `~/.claude/settings.json`
to auto-log token usage after each session. The hook calls `auto-logger.py` which POSTs
session data to the FastAPI backend at `http://192.168.18.169:8010`. Sessions were never
being recorded despite the script working correctly when invoked manually.

### Problem

The hook command used bash env-var assignment syntax and Git Bash paths:
```
CLAUDE_ACCOUNT=claude-figur python "C:\\..." >> "/c/Users/Clandesitine/hook-debug.log" 2>&1
```
A debug `echo` was added as the first command to write a log file — but the file was
never created, confirming the hook never executed at all. No error was surfaced.

### Solution

Claude Code on Windows runs hook commands via **cmd.exe**, not bash. Two things were
invalid for cmd.exe:
1. `VAR=value command` — bash env-var prefix syntax. cmd.exe treats this as a syntax
   error and exits immediately, silently.
2. `/c/Users/...` — Git Bash path format. cmd.exe cannot resolve this path, so even
   the debug `echo` failed before writing anything.

Fix: simplified the hook command to just invoke python directly with a Windows-quoted path:
```json
"command": "python \"C:\\Users\\Clandesitine\\source\\repos\\token-monitor\\src\\scripts\\auto-logger.py\""
```

This is the same pattern as the already-working `PostToolUse` hook.

### Key Facts

- Claude Code on Windows runs hook commands via cmd.exe — NOT bash or Git Bash
- `VAR=value python script.py` is bash-only syntax; cmd.exe exits silently on it
- `/c/Users/...` is a Git Bash path — invalid in cmd.exe, causes silent failure
- Silent failure: cmd.exe exits with error but Claude Code does not surface it to user
- Proof: debug `echo` as first command still produced no output — the shell failed at parse time
- Working pattern for Windows hooks: `python "C:\\Windows\\style\\path.py"` (no env-var prefix)
- The `PostToolUse` Write hook (`python "C:\\path\\auto-logger.py" --checkpoint`) worked all along because it used no env-var prefix

### Code / Commands

```json
// ~/.claude/settings.json — fixed SessionEnd hook
{
  "hooks": {
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python \"C:\\Users\\Clandesitine\\source\\repos\\token-monitor\\src\\scripts\\auto-logger.py\""
      }]
    }]
  }
}
```

### Caveats

If a hook command needs env vars on Windows, use `cmd /c "set VAR=value && python \"path\""` or a wrapper `.bat` file. Do not use bash syntax in hook commands on Windows, even if Git Bash is installed — the hook shell is always cmd.exe.

---

## CHUNK 2: auto-logger.py Account Auto-Detection Eliminates Need for CLAUDE_ACCOUNT Env Var

### Context

The original hook design required `CLAUDE_ACCOUNT=claude-figur` to be set before calling
`auto-logger.py` so sessions would be attributed to the correct account. This env-var
prefix approach is what broke the Windows hook (bash-only syntax). The script was
updated in a prior session to add `claude auth status` auto-detection.

### Problem

The hook design assumed the account identifier had to be injected externally via env var.
This required bash syntax (`VAR=value python ...`) which does not work on Windows cmd.exe.
The CLAUDE.md documentation also referenced old account slugs (`claude-figur`, `claude-azmi`)
that no longer matched the auto-detection output.

### Solution

`auto-logger.py` already implements a three-tier account detection priority:
1. `CLAUDE_ACCOUNT` env var (explicit override)
2. `claude auth status` → email → slug (e.g. `figurululazmi@gmail.com` → `figurululazmi`)
3. `None` (logged as UNASSIGNED)

Since `claude auth status` correctly returns the logged-in account's email, the env var
is not needed for standard Claude accounts. The hook command needs no env-var prefix at all.
The account detected from `claude auth status` is `figurululazmi` for this machine.

Manual test confirmed correct detection and successful POST to API:
```
[auto-logger] Logged 150 tokens (100 in / 50 out) [figurululazmi] -> http://192.168.18.169:8010
```

CLAUDE.md was updated: account table now shows auto-detected identifiers (`figurululazmi`,
`azmi-codes`) instead of legacy slugs (`claude-figur`, `claude-azmi`).

### Key Facts

- `auto-logger.py` derives account from `claude auth status` JSON output — `email` field local-part, dots-to-dashes
- `figurululazmi@gmail.com` → auto-detected as `figurululazmi`
- `azmi.codes@gmail.com` → auto-detected as `azmi-codes`
- `CLAUDE_ACCOUNT` env var only needed for non-standard cases (e.g. GitHub Copilot: `copilot-azmi`)
- `claude auth status` subprocess runs with 5s timeout; falls back to UNASSIGNED on failure
- The env-var override still works — useful for Copilot sessions or when multiple accounts active

### Code / Commands

```python
# auto-logger.py — account detection logic (simplified)
def get_claude_account() -> str | None:
    override = os.getenv("CLAUDE_ACCOUNT")
    if override:
        return override
    result = subprocess.run(["claude", "auth", "status"], capture_output=True, text=True, timeout=5)
    if result.returncode == 0:
        data = json.loads(result.stdout.strip())
        email = data.get("email", "")
        if email:
            return email.split("@")[0].replace(".", "-").lower()
    return None
```

---

## SESSION METADATA

- **Total chunks**: 2
- **Qdrant collection**: knowledge
- **Primary project**: homelab
- **Stack involved**: Claude Code hooks, Python, cmd.exe, Windows, auto-logger.py, FastAPI
- **Files modified**: `~/.claude/settings.json`, `token-monitor/CLAUDE.md`
- **Git branch**: main
- **Unresolved items**: Verify hook fires correctly on next `/exit` — check dashboard at http://192.168.18.169:3010
- **Author**: Figur Ulul Azmi
- **Generated by**: Claude Code CLI - RAG Knowledge Capture Skill
