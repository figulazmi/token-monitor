# Token Monitor

Monitoring token usage Claude Code CLI + GitHub Copilot.
Auto-log setiap session selesai via Claude Code `SessionEnd` hook → FastAPI → PostgreSQL.

*Authored by: Figur Ulul Azmi*

## Stack
- **Backend**: FastAPI + PostgreSQL (Docker, join `rag-net`)
- **Frontend**: React dashboard (artifact / standalone)
- **Hook**: Python script otomatis fire saat session Claude Code selesai

## Struktur

```
token-monitor/
├── backend/          ← FastAPI app + SQLAlchemy + PostgreSQL
├── frontend/         ← React dashboard (token-monitor.jsx)
├── scripts/          ← auto-logger.py (Claude Code SessionEnd hook)
├── docker-compose.yml
└── SETUP.md          ← Panduan deployment lengkap
```

## Quick Start

```bash
# 1. Clone di VM B1
git clone <repo-url> /opt/homelab/token-monitor
cd /opt/homelab/token-monitor

# 2. Deploy
docker compose up -d --build

# 3. Verifikasi
curl http://localhost:8000/health

# 4. Setup hook di project (lihat SETUP.md)
```

## API Endpoints

| Method | Endpoint | Keterangan |
|--------|----------|------------|
| GET | `/health` | Health check |
| POST | `/log` | Simpan session log |
| GET | `/sessions` | List sessions |
| GET | `/stats` | Statistik agregat |
| DELETE | `/sessions/{id}` | Hapus session |

## Update & Deploy Ulang

```bash
cd /opt/homelab/token-monitor
git pull
docker compose up -d --build
```
