# Token Monitor — Setup & Deployment Guide

_Authored by: Figur Ulul Azmi_

---

## 1. First Deploy on VM B1

```bash
# SSH into VM B1
ssh user@192.168.18.169

# Clone repo
git clone <repo-url> /opt/homelab/infrastructure/token-monitor
cd /opt/homelab/infrastructure/token-monitor

# Ensure Docker network exists (shared with rag-gateway)
docker network ls | grep rag-net || docker network create rag-net

# Deploy
docker compose up -d --build

# Verify
curl http://localhost:8010/health
# → {"status":"ok","timestamp":"..."}

curl http://localhost:8010/stats
# → {"total_sessions":0,...}
```

**Dashboard:** http://192.168.18.169:3010  
**API:** http://192.168.18.169:8010

---

## 2. Update & Redeploy

```bash
# Laptop — commit + push
git push origin main

# VM B1 — pull + rebuild
cd /opt/homelab/infrastructure/token-monitor
git pull
docker compose up -d --build
```

---

## 3. Docker Commands

```bash
# View logs
docker logs token-api -f
docker logs token-ui -f
docker logs token-db -f

# Restart single service
docker compose restart token-api

# Stop all
docker compose down

# Stop + wipe database
docker compose down -v
```

---

## 4. Hook Configuration

The `auto-logger.py` script fires on every Claude Code `SessionEnd` event and
POSTs token usage to the API automatically.

### 4a. Copy script to VM B1

```bash
# On VM B1 — script is already in the repo
chmod +x /opt/homelab/infrastructure/token-monitor/scripts/auto-logger.py
```

### 4b. Configure (on your laptop)

Add to **global** `~/.claude/settings.json` (applies to all projects):

**Windows (cmd.exe — account auto-detected from `claude auth status`)**

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python \"C:\\Users\\Clandesitine\\source\\repos\\token-monitor\\src\\scripts\\auto-logger.py\""
          }
        ]
      }
    ]
  }
}
```

> **Windows note:** `VAR=value python ...` is bash syntax — invalid in cmd.exe (Claude Code's hook shell on Windows). Use plain `python "path"` only. Account is auto-detected from `claude auth status`.

**Linux/macOS**

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /opt/homelab/infrastructure/token-monitor/src/scripts/auto-logger.py"
          }
        ]
      }
    ]
  }
}
```

### 4c. Environment variables

| Variable                | Default                      | Description                          |
| ----------------------- | ---------------------------- | ------------------------------------ |
| `TOKEN_MONITOR_URL`     | `http://192.168.18.169:8010` | Backend API URL                      |
| `CLAUDE_ACCOUNT`        | `claude-azmi`                | Account identifier (see table below) |
| `CLAUDE_MODEL`          | `claude-sonnet-4-6`          | Model used in the session            |
| `TOKEN_MONITOR_PROJECT` | CWD folder name              | Project name tag                     |

| `CLAUDE_ACCOUNT` value | Account                  |
| ---------------------- | ------------------------ |
| `claude-azmi`          | Claude Pro azmi.codes    |
| `claude-figur`         | Claude Pro figurululazmi |
| `copilot-azmi`         | Copilot azmi.codes       |

### 4d. Override model or project via env var

Set env vars before the hook if auto-detection is insufficient (e.g. GitHub Copilot sessions).

**Windows (PowerShell — set before running):**

```powershell
$env:CLAUDE_ACCOUNT = "copilot-azmi"
$env:CLAUDE_MODEL = "claude-opus-4-6"
$env:TOKEN_MONITOR_PROJECT = "homelab"
```

**Linux/macOS:**

```bash
CLAUDE_ACCOUNT=copilot-azmi CLAUDE_MODEL=claude-opus-4-6 TOKEN_MONITOR_PROJECT=homelab \
  python3 /opt/homelab/infrastructure/token-monitor/src/scripts/auto-logger.py
```

### 4e. How Token Detection Works

Claude Code's `SessionEnd` hook **does not** send token usage in stdin. What is actually passed:

```json
{ "session_id": "abc123-...", "hook_event_name": "SessionEnd", "cwd": "/path/to/project" }
```

No `usage` field. Token data lives in Claude Code's local JSONL file for the session:

```
~/.claude/projects/<project-slug>/<session-id>.jsonl
```

Every time Claude responds, one line is appended:

```json
{
  "type": "assistant",
  "sessionId": "abc123-...",
  "message": {
    "content": "...",
    "usage": {
      "input_tokens": 3,
      "cache_read_input_tokens": 12506,
      "cache_creation_input_tokens": 0,
      "output_tokens": 160
    }
  }
}
```

`auto-logger.py` reads the JSONL file and sums all `type=assistant` entries:

1. Gets `session_id` from hook stdin
2. Globs `~/.claude/projects/**/<session-id>.jsonl`
3. Sums usage across all assistant messages
4. POSTs total to Token Monitor API

**Token fields explained:**

| Field | What it means | Cost vs normal |
| --- | --- | --- |
| `input_tokens` | New input tokens (non-cached) | 1× |
| `cache_read_input_tokens` | Tokens read from prompt cache | 0.1× |
| `cache_creation_input_tokens` | Tokens written to prompt cache | 1.25× |
| `output_tokens` | Claude's response tokens | 1× |

`auto-logger` sums all three input fields as **total input** — same as `/cost` reports.

---

### 4f. PostToolUse Write Hook (RAG Capture checkpoint)

Logs a checkpoint entry to Token Monitor whenever `/rag-knowledge-capture-cli` writes a summary file to `.claude/summaries/`. The entry has `tokens=0` but serves as a visible timestamp marker in the dashboard.

Add to **global** `~/.claude/settings.json` alongside the existing `SessionEnd` hook:

```json
"PostToolUse": [
  {
    "matcher": "Write",
    "hooks": [
      {
        "type": "command",
        "command": "python \"C:\\Users\\Clandesitine\\source\\repos\\token-monitor\\src\\scripts\\auto-logger.py\" --checkpoint"
      }
    ]
  }
]
```

> **Windows / bash path note:** The path must be wrapped in `\"...\"`. Without quotes, bash strips backslashes from Windows paths (`\s` → `s`, `\r` → `r`, etc.), causing Python to resolve an incorrect path relative to CWD.

**How `--checkpoint` mode works:**
- Reads PostToolUse stdin: `{ "tool_input": { "file_path": "..." } }`
- Only acts if `file_path` contains `summaries/` and ends in `.md`
- Posts: `label="RAG Capture: [filename]"`, `input_tokens=0`, `output_tokens=0`
- Any other `Write` call → silent no-op (exits immediately)

---

## 5. Manual Testing

**Option A — Full end-to-end (reads from real JSONL):**

```bash
# 1. Find a real session ID from an existing JSONL file
ls ~/.claude/projects/C--Users-Clandesitine-source-repos-token-monitor/*.jsonl
# → ...3a78fa75-4fb9-4e13-8748-a06ffee66a1e.jsonl

# 2. Pass it as the hook would (Windows)
echo '{"session_id":"3a78fa75-4fb9-4e13-8748-a06ffee66a1e"}' | python "C:\Users\Clandesitine\source\repos\token-monitor\src\scripts\auto-logger.py"
# → [auto-logger] Logged 1,084,781 tokens (1,065,824 in / 18,957 out) [figurululazmi] -> http://...
```

**Option B — API only (bypass JSONL, direct curl POST):**

```bash
# Manual POST via curl
curl -X POST http://localhost:8010/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "copilot",
    "account": "copilot-azmi",
    "model": "copilot-gpt4o",
    "input_tokens": 5000,
    "output_tokens": 1200,
    "label": "auth middleware refactor",
    "project": "petrochina-eproc"
  }'

# Query stats
curl http://localhost:8010/stats | python3 -m json.tool

# Filter by account
curl "http://localhost:8010/sessions?account=claude-azmi&limit=10"
```

---

## 6. GitHub Copilot — Manual Logging

Copilot does not have a hook system. Use the dashboard form at  
**http://192.168.18.169:3010** → `+ LOG SESSION` → select **GitHub Copilot** + **Copilot · azmi.codes**.

---

## 7. Optional — Custom DB Password

Create `/opt/homelab/infrastructure/token-monitor/.env`:

```env
DB_PASSWORD=your-secure-password
```

Then redeploy: `docker compose up -d --build`

---

## 8. Hook fires on

- Exiting Claude Code (`/exit`, Ctrl-C)
- Running `/clear`
- Session timeout

> If the API is unreachable when the hook fires, the session log is **not retried** and is lost for that session.

---

## 9. Validate Everything Works

```bash
# 1. Health check
curl http://192.168.18.169:8010/health

# 2. Dashboard loads
curl -s http://192.168.18.169:3010 | grep "TOKEN MONITOR"

# 3. Test hook
echo '{"usage":{"input_tokens":500,"output_tokens":100}}' | \
  CLAUDE_ACCOUNT=claude-azmi TOKEN_MONITOR_PROJECT=validation-test \
  python3 /opt/homelab/infrastructure/token-monitor/scripts/auto-logger.py

# 4. Verify data appeared
curl "http://192.168.18.169:8010/sessions?limit=1" | python3 -m json.tool
```
