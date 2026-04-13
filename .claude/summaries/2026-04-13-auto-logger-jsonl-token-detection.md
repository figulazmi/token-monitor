---
id: 2026-04-13-auto-logger-jsonl-token-detection
date: 2026-04-13
source: claude-code-cli
project: homelab
topic: auto-logger Token Detection Fix via JSONL Reading
tags: [auto-logger, claude-code, hooks, session-end, jsonl, token-monitor, homelab, fixed]
related: [token-monitor-hook-setup, claude-code-session-end-hook]
session_type: debug
environment: homelab
git_branch: main
status: implemented
chunk_source: code
---

## CHUNK 1: Claude Code SessionEnd Hook Does Not Provide Token Usage in Stdin

### Context

`auto-logger.py` is a Python script that fires on Claude Code's `SessionEnd` hook
and POSTs session token usage to the Token Monitor API (`POST /sessions`).
The script was written with the assumption that the hook would pass token counts
in stdin as `{"usage": {"input_tokens": N, "output_tokens": N}}`.

### Problem

When triggering `/exit` or any session-ending action in Claude Code, `auto-logger.py`
always printed `"No token usage detected, skipping."` and exited without logging.
Inspecting the script: `usage.get("input_tokens", 0)` and `usage.get("output_tokens", 0)`
always returned 0 because the `usage` field was never present in stdin.

Root cause: Claude Code's `SessionEnd` hook passes **only session metadata** in stdin,
not token counts:

```json
{ "session_id": "abc123-...", "hook_event_name": "SessionEnd", "cwd": "/path/to/project" }
```

No `usage` field exists. The assumption in the original script was incorrect.

### Key Facts

- Claude Code `SessionEnd` hook stdin contains only: `session_id`, `hook_event_name`, `cwd`
- No `usage` field is ever sent by the hook — not a bug, just undocumented behavior
- All previous session logs were silently skipped due to this missing field
- The fix is to read token data from Claude Code's local JSONL files instead of stdin
- `session_id` from hook stdin IS present and matches the JSONL filename

---

## CHUNK 2: Reading Token Usage from Claude Code Local JSONL Files

### Context

Claude Code stores every session's conversation as a JSONL file at:
`~/.claude/projects/<project-slug>/<session-id>.jsonl`
Each assistant response is one line with a `message.usage` object containing
per-message token counts. The `session_id` from the `SessionEnd` hook stdin
matches the JSONL filename exactly.

### Solution

Added `get_tokens_from_jsonl(session_id)` function to `auto-logger.py` that:
1. Globs `~/.claude/projects/**/<session-id>.jsonl`
2. Iterates all lines, filters `type == "assistant"`
3. Sums three input fields + output_tokens across all messages
4. Returns `(total_input, total_output)`

Updated `main()` to call JSONL reader first; falls back to stdin `usage` field
(future-proofing in case Anthropic adds it later).

Token field summing logic:
```python
total_input += (
    usage.get("input_tokens", 0)
    + usage.get("cache_creation_input_tokens", 0)
    + usage.get("cache_read_input_tokens", 0)
)
total_output += usage.get("output_tokens", 0)
```

Verified working: `echo '{"session_id":"3a78fa75-..."}' | python auto-logger.py`
→ `Logged 1,084,781 tokens (1,065,824 in / 18,957 out) [figurululazmi]`

### Key Facts

- JSONL path pattern: `~/.claude/projects/**/<session-id>.jsonl`
- Token fields per assistant message: `input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, `output_tokens`
- `cache_creation_input_tokens`: tokens written to prompt cache (1.25x cost)
- `cache_read_input_tokens`: tokens read from prompt cache (0.1x cost)
- Summing all three input fields matches what `/cost` reports
- JSONL uses `utf-8` encoding with occasional non-ASCII — open with `errors="replace"`
- `glob` module used (stdlib only, no new dependencies added)
- File: `src/scripts/auto-logger.py` — new function `get_tokens_from_jsonl()` added before `post_log()`

---

## CHUNK 3: SETUP.md Documentation Fixes for Hook Configuration

### Context

`SETUP.md` contained stale hook configuration examples and an incorrect manual testing
procedure that no longer reflected how `auto-logger.py` actually works after the
JSONL-based token detection fix.

### Problem

Three issues found in `SETUP.md`:
1. Section 4b/4d used `CLAUDE_ACCOUNT=... python3 ...` bash env-var prefix syntax —
   invalid on Windows cmd.exe (Claude Code's hook shell on Windows). Causes silent hook failure.
2. Section 4d showed multiline bash with backslash continuation — broken in cmd.exe.
3. Section 5 (Manual Testing) used `echo '{"usage":{"input_tokens":1000,...}}'` in stdin —
   this field is now ignored; script reads from JSONL instead.

### Solution

- Section 4b: replaced per-account configs with one Windows example (`python "path"`)
  and one Linux/macOS example (`python3 path`), with note explaining why bash env-var
  prefix is invalid on Windows cmd.exe
- Section 4d: split into PowerShell `$env:VAR = "..."` and bash `VAR=val python3 ...`
- Section 4e (new): added full explanation of how token detection works via JSONL,
  including stdin format, JSONL path, example JSONL entry, and token field breakdown table
- Section 5: replaced broken stdin test with Option A (pass real `session_id` from JSONL)
  and Option B (direct curl POST to API)

### Key Facts

- Windows cmd.exe is the hook shell for Claude Code on Windows — bash env-var prefix fails silently
- Always use `python "C:\\path\\to\\script.py"` (no env prefix) in Windows hooks
- Account auto-detection via `claude auth status` makes explicit `CLAUDE_ACCOUNT` unnecessary for normal sessions
- Only set `CLAUDE_ACCOUNT` explicitly for GitHub Copilot sessions (no `claude auth status`)
- File modified: `SETUP.md` — sections 4b, 4d, 4e (new), 5

---

## SESSION METADATA

- **Total chunks**: 3
- **Qdrant collection**: knowledge
- **Primary project**: homelab
- **Stack involved**: Python, Claude Code hooks, JSONL, token-monitor FastAPI
- **Files modified**: `src/scripts/auto-logger.py`, `SETUP.md`
- **Git branch**: main
- **Unresolved items**: None — fix verified working in local test
- **Author**: Figur Ulul Azmi
- **Generated by**: Claude Code CLI — RAG Knowledge Capture Skill
