---
id: 2026-04-13-token-monitor-hook-fixes-standalone
date: 2026-04-13
source: claude-code-cli
project: homelab
topic: Token Monitor Hook Fixes - Unicode Bug, PostToolUse RAG Checkpoint, Standalone Script
tags: [token-monitor, claude-code, hooks, auto-logger, qdrant, windows, bash, homelab, implemented]
related: [auto-logger-setup, claude-code-hooks, rag-knowledge-capture]
session_type: feature
environment: homelab
git_branch: main
status: implemented
chunk_source: code
---

## CHUNK 1: auto-logger.py Silent Crash on Windows - Unicode Encoding Bug

### Context

`auto-logger.py` is a Claude Code `SessionEnd` hook that reads token usage from stdin and POSTs to the Token Monitor API at `http://192.168.18.169:8010`. On Windows, the hook fires but token data never appears in the dashboard.

### Problem

The script crashed silently on every execution due to `UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'`. The `→` character in the success print statement cannot be encoded by Windows default console encoding `cp1252`. Claude Code swallows hook stderr, so no error was visible.

### Solution

Two-part fix:
1. Add `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` at module top — forces UTF-8 output regardless of terminal encoding.
2. Replace `→` with `->` as belt-and-suspenders fallback.

### Key Facts

- Windows default console encoding is `cp1252`, not UTF-8 — any non-Latin Unicode character crashes print
- Claude Code SessionEnd hook swallows stderr — script crashes are invisible to the user
- `sys.stdout.reconfigure()` only works if `hasattr(sys.stdout, "reconfigure")` — check before calling
- This same fix must be applied to any Python hook script that prints Unicode characters on Windows
- `errors="replace"` ensures output continues even if an unencodable character slips through

### Code / Commands

```python
# Add immediately after imports in any Python Claude Code hook script on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
```

---

## CHUNK 2: Windows Bash Path Quoting Bug in Hook Commands

### Context

Claude Code on Windows runs hook commands via bash (Git Bash). Hook command strings are stored in `~/.claude/settings.json` as JSON strings with double-escaped backslashes (`C:\\Users\\...`).

### Problem

After JSON parsing, the command becomes `python C:\Users\...\auto-logger.py`. In bash, unquoted backslashes are escape characters — `\U` → `U`, `\s` → `s`, etc. Python receives `C:UsersClandesitinesource...auto-logger.py` (backslashes stripped), then resolves it relative to CWD, producing a completely wrong path. Error: `can't open file 'C:\...\token-monitor\UsersClandesitine...auto-logger.py'`.

### Solution

Wrap the path in escaped double quotes inside the JSON command string. After JSON parsing the command becomes `python "C:\Users\...\auto-logger.py"` — bash treats the quoted string as-is, preserving all backslashes.

### Key Facts

- Claude Code hooks on Windows execute via bash, not cmd.exe
- Bash strips backslashes from unquoted strings: `\s` → `s`, `\r` → `r`, `\U` → `U`
- Python's `C:` relative path resolution: `C:somepath` resolves to `C:\[CWD]\somepath`, not `C:\somepath`
- Fix: use `\"C:\\Users\\...\\script.py\"` in JSON — after JSON parse: `"C:\...\script.py"` (bash-quoted)
- The existing SessionEnd hook had the same latent bug but was never confirmed via actual hook trigger

### Code / Commands

```json
{
  "hooks": {
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python \"C:\\Users\\name\\path\\to\\auto-logger.py\""
      }]
    }]
  }
}
```

---

## CHUNK 3: PostToolUse Write Hook for RAG Capture Checkpoint

### Context

Token Monitor tracks Claude Code session token usage via `SessionEnd` hook. Tokens are only logged when a session ends (`/exit` or `/clear`). There was no mid-session checkpoint to record when a RAG knowledge capture happened.

### Problem

When running `/rag-knowledge-capture-cli` before `/clear`, there was no automatic signal to Token Monitor that a RAG capture event occurred.

### Solution

Added `--checkpoint` mode to `auto-logger.py` and a `PostToolUse Write` hook in `~/.claude/settings.json`. When Claude writes any file to `.claude/summaries/*.md`, the hook fires and posts a "RAG Capture: [filename]" entry (0 tokens) to Token Monitor as a timestamp marker.

### Key Facts

- `PostToolUse Write` hook matcher fires on every `Write` tool call — script filters to `summaries/*.md` only
- PostToolUse stdin format: `{ "tool_input": { "file_path": "...", "content": "..." } }` — different from SessionEnd
- `--checkpoint` mode logs `input_tokens=0, output_tokens=0` — visible in dashboard as event marker
- All other `Write` calls (non-summary files) exit silently with no API call
- Same `auto-logger.py` file handles both modes — dispatched by `"--checkpoint" in sys.argv`

### Code / Commands

```python
def main_checkpoint():
    hook_data = json.loads(sys.stdin.read() or "{}")
    file_path = hook_data.get("tool_input", {}).get("file_path", "").replace("\\", "/")
    if "summaries/" not in file_path or not file_path.endswith(".md"):
        sys.exit(0)
    # post to API with label="RAG Capture: [filename]", tokens=0
```

```json
"PostToolUse": [{
  "matcher": "Write",
  "hooks": [{"type": "command",
    "command": "python \"C:\\Users\\...\\auto-logger.py\" --checkpoint"}]
}]
```

---

## CHUNK 4: auto-logger.py Standalone - Remove EMAIL_ACCOUNT_MAP

### Context

`auto-logger.py` had a hardcoded `EMAIL_ACCOUNT_MAP` dict mapping emails to account identifiers. Team members had to re-download the script every time a new member was added to the map.

### Problem

Tight coupling between the script and team roster made it impossible to distribute as a "download once" standalone file. The repo owner had to coordinate updates with every team member whenever someone joined.

### Solution

Removed `EMAIL_ACCOUNT_MAP` entirely. Account detection now derives a slug from the email local-part: `email.split("@")[0].replace(".", "-").lower()`. `CLAUDE_ACCOUNT` env var (set at install time via `setup-hook.py`) still takes highest priority.

### Key Facts

- `CLAUDE_ACCOUNT` env var baked into hook command at install time — takes priority over email derivation
- Derivation rule: `azmi.codes@gmail.com` → `azmi-codes`, `figurululazmi@gmail.com` → `figurululazmi`
- No re-deploy of VM B1 needed — `auto-logger.py` is a client-side script only
- Team onboarding: download `auto-logger.py` + `setup-hook.py` once, run `setup-hook.py --account claude-name`
- Any email now produces a valid account slug — no more UNASSIGNED for unknown emails
- 14/14 unit tests pass after updating 3 test expectations for the new derivation behavior

### Code / Commands

```python
def get_claude_account() -> str | None:
    override = os.getenv("CLAUDE_ACCOUNT")
    if override:
        return override
    data  = json.loads(subprocess.run(["claude","auth","status"], ...).stdout)
    email = data.get("email", "")
    if email:
        return email.split("@")[0].replace(".", "-").lower()
    return None
```

---

## CHUNK 5: setup-hook.py - Team Hook Installer Script

### Context

Team members need to patch their `~/.claude/settings.json` with `SessionEnd` and `PostToolUse Write` hooks pointing to their local copy of `auto-logger.py`. Manual JSON editing is error-prone on Windows due to path quoting requirements.

### Problem

No automated way for team members to install hooks correctly. Manual editing risks missing path quotes, creating duplicate entries, or overwriting existing hook configurations.

### Solution

Created `src/scripts/setup-hook.py` — a standalone installer that auto-detects script location, builds correctly-quoted commands for current OS, merges into existing `~/.claude/settings.json` without overwriting other settings, detects duplicates (safe to re-run), and tests API connectivity.

### Key Facts

- Detects OS: uses `python` on Windows, `python3` on Linux/macOS — path quoting applied automatically
- Duplicate detection: checks if `auto-logger.py` string already present before adding
- `--uninstall` flag removes all `auto-logger.py` hook entries cleanly
- `--dry-run` shows full JSON diff without writing to disk
- `--api-url` flag supports custom Token Monitor URL for teams not on 192.168.18.169
- Tests `GET /health` against API URL and warns if unreachable

### Code / Commands

```bash
# Team onboarding
python setup-hook.py --account claude-yourname   # installs + tests connectivity
python setup-hook.py --dry-run                   # preview only
python setup-hook.py --uninstall                 # remove hooks
```

---

## CHUNK 6: Global CLAUDE.md and Qdrant Deferred Tool Session Start Protocol

### Context

`mcp__qdrant-knowledge__search_knowledge` is configured in `~/.claude/settings.json` but not auto-loaded. Claude was reading source files directly instead of querying the Qdrant RAG knowledge base first, wasting tokens.

### Problem

Two issues: (1) Without calling `ToolSearch("select:mcp__qdrant-knowledge__search_knowledge")` first, the tool cannot be called — it is a deferred tool. (2) No enforced protocol to query Qdrant before file reads. Both caused unnecessary token consumption every session.

### Solution

Created `~/.claude/CLAUDE.md` (global, applies to all projects automatically) with a mandatory `## MANDATORY: Session Start` section as the first content block. Added same protocol to `token-monitor/CLAUDE.md`. Saved as feedback memory for reinforcement across sessions.

### Key Facts

- `~/.claude/CLAUDE.md` is loaded automatically in every project — no per-project setup needed
- Deferred tools require explicit `ToolSearch("select:tool-name")` call before first use each session
- `mcp__qdrant-knowledge__search_knowledge` requires `project` param: `"homelab"` or `"petrochina-eproc"`
- Protocol: ToolSearch first → search_knowledge → only then read files if Qdrant insufficient
- Global CLAUDE.md also documents VM B1 IPs, SSH user, account identifiers to avoid per-project repetition

### Code / Commands

```markdown
<!-- ~/.claude/CLAUDE.md — first section -->
## MANDATORY: Session Start
1. ToolSearch("select:mcp__qdrant-knowledge__search_knowledge")
2. search_knowledge("...", project="homelab")
Only after these two steps may you read source files.
```

---

## SESSION METADATA

- **Total chunks**: 6
- **Qdrant collection**: knowledge
- **Primary project**: homelab
- **Stack involved**: Python 3.13, Claude Code hooks, bash, Windows Git Bash, JSON, pytest
- **Files modified**: `src/scripts/auto-logger.py`, `src/scripts/setup-hook.py` (new), `~/.claude/settings.json`, `~/.claude/CLAUDE.md` (new), `CLAUDE.md`, `SETUP.md`, `tests/scripts/test_auto_logger.py`
- **Git branch**: main
- **Unresolved items**: None
- **Author**: Figur Ulul Azmi
- **Generated by**: Claude Code CLI — RAG Knowledge Capture Skill
