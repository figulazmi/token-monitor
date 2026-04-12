# Token Monitor

Token usage monitoring for Claude Code CLI + GitHub Copilot across multiple accounts.  
Sessions are auto-logged via Claude Code `SessionEnd` hook → FastAPI → PostgreSQL.

_Authored by: Figur Ulul Azmi_

## Stack

| Layer    | Technology                               |
| -------- | ---------------------------------------- |
| Backend  | FastAPI · SQLAlchemy · PostgreSQL        |
| Frontend | React · Vite · nginx                     |
| Database | PostgreSQL 16 (Docker volume)            |
| Hook     | Python script (`scripts/auto-logger.py`) |
| Network  | Docker `rag-net` (shared with homelab)   |

## Accounts Monitored

| Account                 | Platform       | Identifier     |
| ----------------------- | -------------- | -------------- |
| azmi.codes@gmail.com    | Claude Pro     | `claude-azmi`  |
| figurululazmi@gmail.com | Claude Pro     | `claude-figur` |
| azmi.codes@gmail.com    | GitHub Copilot | `copilot-azmi` |

## Project Structure

```
token-monitor/
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── core/         — config, database, pricing
│   │   │   ├── models/       — SQLAlchemy ORM
│   │   │   ├── routers/      — sessions CRUD
│   │   │   ├── schemas/      — Pydantic request/response
│   │   │   └── main.py       — app factory, /health, /stats
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── main.tsx          — entry point
│   │   │   └── TokenMonitor.jsx  — dashboard UI
│   │   ├── nginx.conf        — SPA + API proxy config
│   │   ├── Dockerfile        — multi-stage build
│   │   └── package.json
│   └── scripts/
│       └── auto-logger.py    — Claude Code SessionEnd hook
├── tests/
│   ├── backend/              — API endpoint tests (SQLite)
│   └── scripts/              — auto-logger unit tests
├── docker-compose.yml
├── pytest.ini
├── RUNNING.md                — local dev guide
├── SETUP.md                  — VM B1 deployment guide
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

## Quick Deploy to VM B1

```bash
# 1. Clone
git clone <repo-url> /opt/homelab/infrastructure/token-monitor
cd /opt/homelab/token-monitor

# 2. Ensure rag-net exists
docker network create rag-net 2>/dev/null || true

# 3. Deploy all services
docker compose up -d --build

# 4. Verify
curl http://localhost:8000/health
# → {"status":"ok","timestamp":"..."}
```

Dashboard: **http://192.168.18.169:3000**  
API: **http://192.168.18.169:8000**

## Update & Redeploy

```bash
# Laptop — push changes
git push origin main

# VM B1 — pull + rebuild
cd /opt/homelab/token-monitor
git pull
docker compose up -d --build
```

## Local Development

See **[RUNNING.md](RUNNING.md)** for the complete step-by-step guide including database setup, troubleshooting, and quick reference.

```powershell
# Quick start — run these in order

# 1. Start DB (Docker)
docker run -d --name token-db-local -e POSTGRES_DB=tokenmonitor -e POSTGRES_USER=tokenuser -e POSTGRES_PASSWORD=tokenpass123 -p 5433:5432 postgres:16-alpine

# 2. Backend (from src\backend)
$env:DATABASE_URL = "postgresql://tokenuser:tokenpass123@localhost:5433/tokenmonitor"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload

# 3. Frontend (separate terminal, from src\frontend)
npm run dev
# → http://localhost:5173
```

## Hook Setup (per Claude account)

Add to global `~/.claude/settings.json` to auto-log all sessions:

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /opt/homelab/token-monitor/src/scripts/auto-logger.py"
          }
        ]
      }
    ]
  }
}
```

Account is auto-detected from `claude auth status` — no env var needed.  
See `SETUP.md` for full configuration guide including manual override options.
