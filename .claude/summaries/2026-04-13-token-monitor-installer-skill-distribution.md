---
id: 2026-04-13-token-monitor-installer-skill-distribution
date: 2026-04-13
source: claude-code-cli
project: homelab
topic: Token Monitor Installer and Skill Distribution Standard
tags: [token-monitor, auto-logger, claude-code, hooks, installer, skill, windows, cross-platform]
related: [auto-logger-hook-setup, claude-code-sessionend-hook, homelab-infrastructure]
session_type: feature
environment: homelab
git_branch: main
status: implemented
chunk_source: code
---

## CHUNK 1: Claude Code SessionEnd Hook Global Scope Confirmation

### Context

Token Monitor uses a Python script (`auto-logger.py`) registered as a Claude Code
`SessionEnd` hook in the global `~/.claude/settings.json`. The user needed to confirm
that this hook fires across all projects automatically, not just within the token-monitor repo.

### Problem

Unclear whether the SessionEnd hook in `~/.claude/settings.json` applies globally
(all projects on the machine) or only to the project where it was configured.

### Solution

Confirmed: hooks in `~/.claude/settings.json` (global settings) apply to ALL Claude
Code projects on the machine. The hook fires every time a session ends regardless of
which project is open. Token usage is read from `~/.claude/projects/**/<session-id>.jsonl`
and POSTed to the Token Monitor API.

### Key Facts

- `~/.claude/settings.json` = global scope — hooks fire for every project on the machine
- Project-specific hooks go in `.claude/settings.json` inside the project folder
- SessionEnd fires on: `/exit`, Ctrl-C, `/clear`, session timeout
- `auto-logger.py` reads token data from JSONL, not from hook stdin (Claude Code does not pass usage in stdin)
- Account is auto-detected from `claude auth status` → email local-part, dots replaced with dashes
- Hook verified in `~/.claude/settings.json` with both `SessionEnd` and `PostToolUse Write` entries

---

## CHUNK 2: Cross-Platform Hook Installer (install.py)

### Context

Token Monitor's `auto-logger.py` hook was installed manually by editing
`~/.claude/settings.json` with a hardcoded path to the repo. This is not distributable —
other users or machines require manual editing. A cross-platform installer was needed.

### Problem

No automated way for a new user on any OS to install the token monitoring hook.
The hook command path differs between Windows (`python "C:\..."`) and Linux/macOS (`python3 /...`).
Windows cmd.exe (which runs Claude Code hooks) cannot set env vars inline (`VAR=val python ...`
is bash syntax — invalid on Windows).

### Solution

Created `scripts/install.py` — a standalone Python installer that:
1. Copies `auto-logger.py` to `~/.claude/hooks/auto-logger.py` (OS-agnostic standard location)
2. Writes `~/.claude/token-monitor.json` with API URL, account, model config
3. Patches `~/.claude/settings.json` — adds `SessionEnd` + `PostToolUse Write` hooks
4. Verifies API connectivity via curl health check
5. Is idempotent — skips hooks that already contain "auto-logger" in the command

### Key Facts

- Install location: `~/.claude/hooks/auto-logger.py` (not the repo path — works even if repo is deleted)
- Windows hook command: `python "C:\Users\<user>\.claude\hooks\auto-logger.py"` (path must be quoted)
- Linux/macOS hook command: `python3 /home/<user>/.claude/hooks/auto-logger.py`
- Idempotent: checks for "auto-logger" substring in existing hook commands before adding
- `--uninstall` flag removes hooks from settings.json and deletes the copied script + config
- `--yes` flag for non-interactive/scripted install with defaults

### Code / Commands

```bash
# Interactive install
python scripts/install.py

# Non-interactive (CI or scripted)
python scripts/install.py --api-url http://192.168.18.169:8010 --yes

# With account override (e.g., GitHub Copilot sessions)
python scripts/install.py --api-url http://192.168.18.169:8010 --account copilot-azmi --yes

# Uninstall
python scripts/install.py --uninstall
```

---

## CHUNK 3: Config File Fallback for Windows Hook Env Var Limitation

### Context

On Windows, Claude Code runs hooks via cmd.exe. Setting environment variables inline
(`VAR=value python script.py`) is bash syntax and fails silently on Windows. This means
the Token Monitor API URL and account cannot be configured via env var prefix in the hook
command on Windows machines.

### Problem

Users on Windows cannot set `TOKEN_MONITOR_URL`, `CLAUDE_ACCOUNT`, or `CLAUDE_MODEL`
as inline env vars in the hook command. Previously the API URL was hardcoded in
`auto-logger.py` itself (pointing to `192.168.18.169`), which breaks for any other user.

### Solution

Added config file loading to `auto-logger.py`. The script now reads
`~/.claude/token-monitor.json` as a fallback between env vars and built-in defaults.
The installer (`install.py`) writes this file during setup with the user's chosen API URL,
account, and model.

Config priority (highest to lowest):
1. Environment variable (`TOKEN_MONITOR_URL`, `CLAUDE_ACCOUNT`, `CLAUDE_MODEL`)
2. `~/.claude/token-monitor.json` (written by installer)
3. Built-in defaults (`http://localhost:8010`, auto-detect account, `claude-sonnet-4-6`)

### Key Facts

- Config file path: `~/.claude/token-monitor.json`
- JSON keys: `api_url`, `account` (optional — omit for auto-detect), `model`, `project`
- Config is loaded once at script startup into `_cfg` dict — no file I/O per request
- Env vars always override config file values (env var `or` cfg.get pattern)
- `account` key in config file provides same override as `CLAUDE_ACCOUNT` env var
- Default API URL changed from hardcoded homelab IP to `http://localhost:8010` for portability

### Code / Commands

```json
// ~/.claude/token-monitor.json (written by install.py)
{
  "api_url": "http://192.168.18.169:8010",
  "model": "claude-sonnet-4-6"
}
// account omitted = auto-detect from claude auth status
```

```python
# auto-logger.py — config loading pattern
_cfg = _load_config()
API_URL = os.getenv("TOKEN_MONITOR_URL") or _cfg.get("api_url", "http://localhost:8010")
MODEL   = os.getenv("CLAUDE_MODEL")     or _cfg.get("model", "claude-sonnet-4-6")
```

---

## CHUNK 4: SKILL.md Format for Claude Code Skill Marketplace

### Context

The user wanted to make token-monitor distributable in a standard format compatible
with Claude Code skill marketplaces (e.g., skillsmp.com). Claude Code skills are
invokable via `/skill-name` and are defined as `SKILL.md` files with YAML frontmatter.

### Problem

No standardized entry point for other users to discover and install token-monitor
as a Claude Code skill. The existing SETUP.md is documentation, not an invokable skill.

### Solution

Created `.agents/skills/token-monitor-setup/SKILL.md` following the Claude Code skill
format. When invoked as `/token-monitor-setup`, Claude follows the skill instructions
to guide the user through the full install process interactively.

The SKILL.md covers:
- Prerequisites check (repo cloned? API URL known?)
- Running `python scripts/install.py` with correct flags
- Post-install verification (curl health check, manual hook test)
- Troubleshooting table for common failure modes
- Config file reference with all supported keys

### Key Facts

- Skill location: `.agents/skills/<skill-name>/SKILL.md` (project-level skills)
- User-level skills: `~/.claude/skills/<skill-name>/SKILL.md`
- SKILL.md frontmatter requires: `name` (slug) and `description` (one-paragraph)
- Invoked as `/token-monitor-setup` inside any Claude Code session
- Skill is separate from install.py — skill = guided UX, install.py = automation
- Skills on skillsmp.com follow identical SKILL.md format with frontmatter + markdown body

---

## SESSION METADATA

- **Total chunks**: 4
- **Qdrant collection**: knowledge
- **Primary project**: homelab
- **Stack involved**: Python, Claude Code hooks, Windows cmd.exe, bash, JSON config
- **Files modified**: `src/scripts/auto-logger.py`, `scripts/install.py` (new), `.agents/skills/token-monitor-setup/SKILL.md` (new)
- **Git branch**: main
- **Unresolved items**: Existing user hooks still point to repo path — migration to `~/.claude/hooks/` is optional but not automated
- **Author**: Figur Ulul Azmi
- **Generated by**: Claude Code CLI -- RAG Knowledge Capture Skill
