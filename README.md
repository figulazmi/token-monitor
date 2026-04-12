# Token Monitor

Token usage monitoring for Claude Code CLI + GitHub Copilot across multiple accounts.  
Sessions are auto-logged via Claude Code `SessionEnd` hook → FastAPI → PostgreSQL.

*Authored by: Figur Ulul Azmi*

## Stack

| Layer     | Technology                              |
|-----------|-----------------------------------------|
| Backend   | FastAPI · SQLAlchemy · PostgreSQL        |
| Frontend  | React · Vite · nginx                    |
| Database  | PostgreSQL 16 (Docker volume)           |
| Hook      | Python script (`scripts/auto-logger.py`) |
| Network   | Docker `rag-net` (shared with homelab)  |

## Accounts Monitored

| Account                | Platform        | Identifier      |
|------------------------|-----------------|-----------------|
| azmi.codes@gmail.com   | Claude Pro      | `claude-azmi`   |
| figulazmi@gmail.com    | Claude Pro      | `claude-figul`  |
| azmi.codes@gmail.com   | GitHub Copilot  | `copilot-azmi`  |

## Project Structure

```
token-monitor/
├── backend/
│   ├── app/
│   │   ├── core/         — config, database, pricing
│   │   ├── models/       — SQLAlchemy ORM
│   │   ├── routers/      — sessions CRUD
│   │   ├── schemas/      — Pydantic request/response
│   │   └── main.py       — app factory, /health, /stats
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx      — entry point
│   │   └── TokenMonitor.jsx — dashboard UI
│   ├── nginx.conf        — SPA + API proxy config
│   ├── Dockerfile        — multi-stage build
│   └── package.json
├── scripts/
│   └── auto-logger.py    — Claude Code SessionEnd hook
├── docker-compose.yml
├── SETUP.md
└── README.md
```

## API Endpoints

| Method   | Endpoint          | Description                  |
|----------|-------------------|------------------------------|
| `GET`    | `/health`         | Health check                 |
| `GET`    | `/stats`          | Aggregated stats by account, platform, model |
| `POST`   | `/sessions`       | Log a session                |
| `GET`    | `/sessions`       | List sessions (filterable)   |
| `DELETE` | `/sessions/{id}`  | Delete a session             |

### Query params for `GET /sessions`

| Param      | Example            |
|------------|--------------------|
| `platform` | `claude`           |
| `account`  | `claude-azmi`      |
| `project`  | `petrochina-eproc` |
| `limit`    | `50`               |

## Quick Deploy to VM B1

```bash
# 1. Clone
git clone <repo-url> /opt/homelab/token-monitor
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

```bash
# Backend
cd backend
python -m uvicorn app.main:app --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# → http://localhost:5173 (proxies /api → localhost:8000)
```

## Hook Setup (per Claude account)

Add to project `.claude/settings.json`:

```json
{
  "hooks": {
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "CLAUDE_ACCOUNT=claude-azmi TOKEN_MONITOR_PROJECT=my-project python3 /opt/homelab/scripts/auto-logger.py"
      }]
    }]
  }
}
```

See `SETUP.md` for full configuration guide.
