# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

# Project Overview

**token-monitor** — Token usage monitoring for Claude Code CLI + GitHub Copilot across multiple accounts.
Sessions are auto-logged via Claude Code `SessionEnd` hook → FastAPI → PostgreSQL.

- **Stack:** FastAPI · SQLAlchemy · PostgreSQL (backend), React · Vite · nginx (frontend)
- **Hook:** Python script (`scripts/auto-logger.py`) — fires on `SessionEnd`
- **Deployment:** Docker Compose on VM B1 (homelab), auto-deploy via Gitea CI
- **Network:** Docker `rag-net` (shared with homelab stack)

## Accounts Monitored

| Account                 | Platform       | `CLAUDE_ACCOUNT` |
| ----------------------- | -------------- | ---------------- |
| azmi.codes@gmail.com    | Claude Pro     | `claude-azmi`    |
| figurululazmi@gmail.com | Claude Pro     | `claude-figur`   |
| azmi.codes@gmail.com    | GitHub Copilot | `copilot-azmi`   |

## Project Structure

```
token-monitor/
├── backend/
│   ├── app/
│   │   ├── core/         — config, database, pricing
│   │   ├── models/       — SQLAlchemy ORM (SessionLog)
│   │   ├── routers/      — sessions CRUD
│   │   ├── schemas/      — Pydantic request/response
│   │   └── main.py       — app factory, /health, /stats
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx           — root component
│   │   ├── TokenMonitor.jsx  — dashboard UI
│   │   ├── components/       — UI components
│   │   ├── hooks/            — custom React hooks
│   │   ├── services/         — API client
│   │   ├── types/            — TypeScript types
│   │   └── main.tsx          — entry point
│   ├── nginx.conf            — SPA + API proxy config
│   ├── Dockerfile            — multi-stage build
│   └── package.json
├── scripts/
│   └── auto-logger.py        — Claude Code SessionEnd hook
├── .gitea/workflows/
│   └── deploy.yml            — Gitea CI auto-deploy to VM B1
├── docker-compose.yml
├── SETUP.md
└── README.md
```

## API Endpoints

| Method   | Endpoint         | Description                                  |
| -------- | ---------------- | -------------------------------------------- |
| `GET`    | `/health`        | Health check                                 |
| `GET`    | `/stats`         | Aggregated stats by account, platform, model |
| `POST`   | `/sessions`      | Log a session                                |
| `GET`    | `/sessions`      | List sessions (filterable)                   |
| `DELETE` | `/sessions/{id}` | Delete a session                             |

### Query params for `GET /sessions`

| Param      | Example            |
| ---------- | ------------------ |
| `platform` | `claude`           |
| `account`  | `claude-azmi`      |
| `project`  | `petrochina-eproc` |
| `limit`    | `50`               |

## Build & Run Commands

```bash
# Backend (local dev)
cd backend
python -m uvicorn app.main:app --reload

# Frontend (local dev — separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173 (proxies /api → localhost:8000)
```

```bash
# Docker (full stack)
docker compose up -d --build

# Logs
docker logs token-api -f
docker logs token-ui -f
docker logs token-db -f

# Restart single service
docker compose restart token-api

# Stop all (preserve data)
docker compose down

# Stop + wipe database
docker compose down -v
```

## VM B1 Deployment

- **Dashboard:** `http://192.168.18.169:3000`
- **API:** `http://192.168.18.169:8000`

### First Deploy (one-time)

```bash
ssh user@192.168.18.169

git clone <repo-url> /opt/homelab/token-monitor
cd /opt/homelab/token-monitor

# Ensure shared Docker network exists
docker network ls | grep rag-net || docker network create rag-net

docker compose up -d --build

curl http://localhost:8000/health
# → {"status":"ok","timestamp":"..."}
```

### Update / Redeploy

```bash
# Laptop — push triggers Gitea CI auto-deploy
git push origin main

# Or manually on VM B1
cd /opt/homelab/token-monitor
git pull
docker compose up -d --build
```

### Notes

- CI/CD: `.gitea/workflows/deploy.yml` — auto SSH deploy on push to `main`
- Secrets: `VM_B1_HOST`, `VM_B1_USER`, `VM_B1_SSH_KEY` stored in Gitea repo secrets
- Optional custom DB password: create `/opt/homelab/token-monitor/.env` with `DB_PASSWORD=...`

## Hook Setup (per Claude account)

Add to each project's `.claude/settings.json`:

**Account: azmi.codes@gmail.com**

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "CLAUDE_ACCOUNT=claude-azmi TOKEN_MONITOR_PROJECT=my-project python3 /opt/homelab/token-monitor/scripts/auto-logger.py"
          }
        ]
      }
    ]
  }
}
```

**Account: figurululazmi@gmail.com**

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "CLAUDE_ACCOUNT=claude-figur TOKEN_MONITOR_PROJECT=my-project python3 /opt/homelab/token-monitor/scripts/auto-logger.py"
          }
        ]
      }
    ]
  }
}
```

### Hook Environment Variables

| Variable                | Default                      | Description                          |
| ----------------------- | ---------------------------- | ------------------------------------ |
| `TOKEN_MONITOR_URL`     | `http://192.168.18.169:8000` | Backend API URL                      |
| `CLAUDE_ACCOUNT`        | `claude-azmi`                | Account identifier (see table above) |
| `CLAUDE_MODEL`          | `claude-sonnet-4-6`          | Model used in the session            |
| `TOKEN_MONITOR_PROJECT` | CWD folder name              | Project name tag                     |

Hook fires on: `/exit`, Ctrl-C, `/clear`, session timeout.
If API is unreachable when hook fires — the log is **lost** (no retry).

## External Brain (Qdrant RAG)

You have access to MCP tool `search_knowledge`.
ALWAYS call this tool FIRST when asked about prior work, architecture decisions, or infrastructure setup.

### MANDATORY rules:

- ALWAYS pass `project` parameter
- ALWAYS use descriptive query minimum 8 words
- For token-monitor / homelab infra: `project="homelab"`

### Query examples:

- `search_knowledge("token monitor FastAPI PostgreSQL session logging setup", project="homelab")`
- `search_knowledge("how to deploy token monitor docker to VM B1", project="homelab")`
- `search_knowledge("Claude Code SessionEnd hook auto-logger configuration", project="homelab")`

### When to use `project="homelab"`:

- Questions about VM B1, Docker, Gitea CI, rag-net infrastructure
- Questions about auto-logger.py hook, token tracking, account configuration
- Questions about other homelab services: n8n, Qdrant, Ollama, Open WebUI

## STRICT RAG MODE

For ANY knowledge or context query (architecture, prior decisions, infrastructure how-tos):

1. ALWAYS call `search_knowledge` FIRST — before reading any file
2. Only read source files AFTER Qdrant context is retrieved
3. If Qdrant returns no results → say "NOT FOUND IN KNOWLEDGE BASE" and ask user

## Critical Rules

- **LANGUAGE:** All code, comments, variable names, logs MUST be in English.
- **PLAN FIRST:** For tasks touching more than 2 files, outline the plan before coding.

## Git Workflow

- Main branch: `main`
- Auto-deploy on push via Gitea CI (`.gitea/workflows/deploy.yml`)
- Never commit: `.env`, `*.local`

## Session End Protocol

Before ending any session or using /clear:

1. `/cost` — record token usage
2. `@.claude/skills/rag-knowledge-capture-cli/SKILL.md` — summarize session into RAG chunks
3. Save to `.claude/summaries/YYYY-MM-DD-[topic].md`
4. Run: `bash ~/scripts/push-to-qdrant.sh .claude/summaries/[file]`
