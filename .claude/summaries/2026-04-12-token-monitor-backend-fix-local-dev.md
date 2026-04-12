---
id: 2026-04-12-token-monitor-backend-fix-local-dev
date: 2026-04-12
source: claude-code-cli
project: homelab
topic: Token Monitor Backend Import Fix and Local Dev Setup
tags: [fastapi, sqlalchemy, docker, postgresql, python, token-monitor, fixed, local-dev]
related: [token-monitor-project-restructure, homelab-vm-b1-deployment]
session_type: debug
environment: dev
git_branch: main
status: implemented
chunk_source: code
---

## CHUNK 1: Fix ModuleNotFoundError After Project Restructure to src/

### Context

Token Monitor FastAPI backend was restructured from `backend/` to `src/backend/`.
After moving, all 6 backend Python files had their imports updated to use
`from src.backend.app.*` prefix — which is wrong for uvicorn running from inside `src/backend/`.

### Problem

Running uvicorn from `src/backend/` with `app.main:app` caused:
```
ModuleNotFoundError: No module named 'src'
```
Because `src.backend.app.core.database` is not resolvable when the working directory
is already `src/backend/` — Python path starts from there, not from project root.

### Solution

Replace all occurrences of `from src.backend.app.` with `from app.` across 6 files:

- `src/backend/app/main.py`
- `src/backend/app/core/database.py`
- `src/backend/app/models/__init__.py`
- `src/backend/app/models/session_log.py`
- `src/backend/app/routers/sessions.py`
- `src/backend/app/schemas/__init__.py`

Backend must always be launched from inside `src/backend/` as working directory:
```powershell
cd src\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### Key Facts

- When uvicorn runs `app.main:app`, Python root = current working directory
- If CWD is `src/backend/`, then `from app.core...` works; `from src.backend.app.core...` does NOT
- This affects all 6 files that contain internal imports between app modules
- `pytest.ini` sets `pythonpath = src/backend` so tests work from project root without this issue
- After any folder restructure, verify all internal imports match the new CWD context

---

## CHUNK 2: Run PostgreSQL via Docker for Local Development (Windows)

### Context

Token Monitor requires PostgreSQL. For local development on Windows, Docker Desktop
is used to run a PostgreSQL container. The `docker-compose.yml` does not expose
the DB port to the host — it only connects via Docker internal `rag-net` network.
A separate standalone container is needed for local dev.

### Problem

Running `docker compose up` only works for full-stack production deployment.
For local backend dev, the DB must be accessible at `localhost:5433` from the host machine.
Port 5432 is avoided to prevent conflict with any local PostgreSQL installation.

### Solution

Run a standalone PostgreSQL container with host port mapping:

```powershell
docker run -d --name token-db-local -e POSTGRES_DB=tokenmonitor -e POSTGRES_USER=tokenuser -e POSTGRES_PASSWORD=tokenpass123 -p 5433:5432 postgres:16-alpine
```

Verify it is ready:
```powershell
docker exec token-db-local pg_isready -U tokenuser -d tokenmonitor
```

If container name already exists:
```powershell
docker rm -f token-db-local
docker run -d --name token-db-local -e POSTGRES_DB=tokenmonitor -e POSTGRES_USER=tokenuser -e POSTGRES_PASSWORD=tokenpass123 -p 5433:5432 postgres:16-alpine
```

On subsequent dev sessions (container already exists but stopped):
```powershell
docker start token-db-local
```

### Key Facts

- `docker-compose.yml` uses `rag-net` internal network — DB is NOT accessible from host by default
- Use standalone `docker run -p 5433:5432` for local dev, NOT `docker compose up`
- Port 5433 on host maps to 5432 inside the container
- Container `token-db-local` is for dev only; production uses `token-db` via docker-compose
- Always use single-line `docker run` command on Windows — multiline backtick continuation frequently fails in PowerShell
- `Base.metadata.create_all()` in `main.py` auto-creates tables on first startup — no manual migration needed

---

## CHUNK 3: DATABASE_URL Must Be Set in Same PowerShell Terminal Session

### Context

Token Monitor backend reads `DATABASE_URL` via pydantic-settings from environment variable.
The default value in `config.py` is `postgresql://tokenuser:tokenpass123@token-db:5432/tokenmonitor`
which uses `token-db` — a Docker internal hostname only resolvable inside Docker network.

### Problem

Running uvicorn without setting `DATABASE_URL` caused backend to attempt connection to
`token-db:5432` (Docker hostname) from the host machine, resulting in:
```
psycopg2.OperationalError: connection to server at "localhost", port 5433 failed: Connection refused
```
Even when `$env:DATABASE_URL` was set, but in a different terminal session than uvicorn.

### Solution

`$env:DATABASE_URL` must be set in the **same PowerShell terminal** before running uvicorn.
Environment variables in PowerShell do not persist across sessions.

```powershell
$env:DATABASE_URL = "postgresql://tokenuser:tokenpass123@localhost:5433/tokenmonitor"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Verify the variable is set before running:
```powershell
echo $env:DATABASE_URL
# Must print the full connection string before proceeding
```

### Key Facts

- `$env:VAR = "value"` in PowerShell is session-scoped — dies when terminal closes
- Default `DATABASE_URL` in `config.py` uses Docker hostname `token-db` — only works inside Docker
- For local dev, always override with `localhost:5433` in the same terminal that runs uvicorn
- pydantic-settings reads env vars at import time — setting after import has no effect
- Tests are not affected: `tests/conftest.py` sets `DATABASE_URL=sqlite://...` before any imports

---

## CHUNK 4: Claude Code Slash Commands Must Be in commands/ Not skills/

### Context

Claude Code CLI supports user-defined slash commands (e.g., `/rag-knowledge-capture-cli`).
The skill file was stored at `.claude/skills/rag-knowledge-capture-cli/SKILL.md` — a custom
convention from a previous session — but stopped being recognized as a slash command.

### Problem

Typing `/rag-knowledge-capture-cli` in Claude Code had no effect. The skill file existed
but Claude Code could not load it as an invocable command.

### Solution

Claude Code reads slash commands exclusively from the `commands/` directory, not `skills/`.
The correct locations are:

- **Global** (available in all projects): `~/.claude/commands/rag-knowledge-capture-cli.md`
- **Project-level**: `.claude/commands/rag-knowledge-capture-cli.md`

Fix applied:
```bash
mkdir -p ~/.claude/commands
cp .claude/skills/rag-knowledge-capture-cli/SKILL.md ~/.claude/commands/rag-knowledge-capture-cli.md
cp .claude/skills/rag-knowledge-capture-cli/SKILL.md .claude/commands/rag-knowledge-capture-cli.md
```

After copying, restart Claude Code and `/rag-knowledge-capture-cli` becomes available.

### Key Facts

- Claude Code slash commands MUST be `.md` files directly inside `commands/` directory
- File must be named exactly as the command: `rag-knowledge-capture-cli.md` → `/rag-knowledge-capture-cli`
- `skills/` is a user-defined convention — NOT recognized by Claude Code's command loader
- Global `~/.claude/commands/` makes the command available across ALL projects
- Project `.claude/commands/` makes the command available only in that project
- Restart Claude Code after adding new command files for them to be registered

---

## SESSION METADATA

- **Total chunks**: 4
- **Qdrant collection**: knowledge
- **Primary project**: homelab
- **Stack involved**: FastAPI, SQLAlchemy, PostgreSQL, Docker, Python, PowerShell, Claude Code CLI
- **Files modified**: `src/backend/app/main.py`, `src/backend/app/core/database.py`, `src/backend/app/models/__init__.py`, `src/backend/app/models/session_log.py`, `src/backend/app/routers/sessions.py`, `src/backend/app/schemas/__init__.py`, `RUNNING.md` (created), `README.md`, `.claude/commands/rag-knowledge-capture-cli.md` (created)
- **Git branch**: main
- **Unresolved items**: Verify `/rag-knowledge-capture-cli` works after Claude Code restart; confirm tests pass after import fixes
- **Author**: Figur Ulul Azmi
- **Generated by**: Claude Code CLI — RAG Knowledge Capture Skill
