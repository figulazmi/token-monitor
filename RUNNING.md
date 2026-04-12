# Token Monitor — Running Guide

> Panduan lengkap untuk menjalankan Token Monitor secara lokal (development) maupun di server produksi (VM B1).

---

## Prerequisites

Pastikan semua tools berikut sudah terinstall:

| Tool | Minimum Version | Cek |
|---|---|---|
| Docker Desktop | latest | `docker --version` |
| Python | 3.12+ | `python --version` |
| Node.js | 20+ | `node --version` |
| npm | 9+ | `npm --version` |

---

## Project Structure

```
token-monitor/
├── src/
│   ├── backend/
│   │   ├── app/
│   │   │   ├── core/         — config, database, pricing
│   │   │   ├── models/       — SQLAlchemy ORM (SessionLog)
│   │   │   ├── routers/      — sessions CRUD endpoints
│   │   │   ├── schemas/      — Pydantic request/response models
│   │   │   └── main.py       — app factory, /health, /stats
│   │   ├── .venv/            — Python virtual environment (gitignored)
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── frontend/
│   │   ├── src/
│   │   │   ├── TokenMonitor.jsx  — dashboard UI
│   │   │   └── main.tsx          — entry point
│   │   ├── nginx.conf        — SPA + API proxy
│   │   ├── Dockerfile
│   │   └── package.json
│   └── scripts/
│       └── auto-logger.py    — Claude Code SessionEnd hook
├── tests/
│   ├── conftest.py           — root: set SQLite DATABASE_URL before imports
│   ├── backend/
│   │   ├── conftest.py       — test client fixture (SQLite in-memory)
│   │   └── test_api.py       — API endpoint tests
│   └── scripts/
│       └── test_auto_logger.py — auto-logger unit tests
├── docker-compose.yml
├── pytest.ini
├── RUNNING.md                — this file
├── SETUP.md                  — VM B1 deployment guide
└── README.md
```

---

## Local Development (Windows)

### Step 1 — Start Database (Docker)

Jalankan PostgreSQL sebagai container lokal. **Wajib single line** — multiline dengan backtick di PowerShell sering gagal.

```powershell
docker run -d --name token-db-local -e POSTGRES_DB=tokenmonitor -e POSTGRES_USER=tokenuser -e POSTGRES_PASSWORD=tokenpass123 -p 5433:5432 postgres:16-alpine
```

Verifikasi database siap menerima koneksi:

```powershell
docker exec token-db-local pg_isready -U tokenuser -d tokenmonitor
```

Output yang diharapkan: `localhost:5432 - accepting connections`

> **Port 5433** dipakai di lokal (bukan 5432) untuk menghindari konflik jika ada PostgreSQL lain yang sudah berjalan di mesin.

---

### Step 2 — Setup Backend (pertama kali)

```powershell
cd src\backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> Jika venv pernah dibuat di path lama (sebelum restrukturisasi folder), hapus dan buat ulang:
> ```powershell
> Remove-Item -Recurse -Force .venv
> python -m venv .venv
> .venv\Scripts\pip install -r requirements.txt
> ```

---

### Step 3 — Jalankan Backend

**Penting:** `$env:DATABASE_URL` harus di-set di terminal yang **sama** sebelum menjalankan uvicorn. Env var tidak persist antar terminal di PowerShell.

```powershell
$env:DATABASE_URL = "postgresql://tokenuser:tokenpass123@localhost:5433/tokenmonitor"
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Backend otomatis membuat tabel saat startup pertama kali — tidak perlu migration manual.

Verifikasi backend berjalan:

```powershell
curl http://localhost:8000/health
```

Output: `{"status":"ok","timestamp":"..."}`

---

### Step 4 — Jalankan Frontend (terminal baru)

```powershell
cd src\frontend
npm install
npm run dev
```

Dashboard: **http://localhost:5173**

Frontend secara otomatis proxy `/api/*` → `http://localhost:8000` via Vite config.

---

## Running Tests

Tests menggunakan **SQLite in-memory** — tidak perlu PostgreSQL atau Docker untuk menjalankan tests.

```powershell
# Dari root project
cd C:\Users\<user>\source\repos\token-monitor
.venv\Scripts\python.exe -m pytest tests/ -v
```

> **Catatan:** `pytest.ini` sudah dikonfigurasi dengan `pythonpath = src/backend` sehingga import `from app...` bekerja di dalam tests.

---

## Setiap Kali Buka Terminal Baru

Urutan yang harus dilakukan setiap membuka terminal baru untuk development:

```powershell
# 1. Pastikan container DB masih jalan
docker ps --filter name=token-db-local

# Jika tidak ada, start ulang:
docker start token-db-local

# 2. Set DATABASE_URL (wajib setiap terminal baru)
$env:DATABASE_URL = "postgresql://tokenuser:tokenpass123@localhost:5433/tokenmonitor"

# 3. Jalankan backend (dari folder src\backend)
cd src\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

---

## Production Deployment (VM B1)

Untuk production, semua service (DB + API + UI) dijalankan via Docker Compose.

```bash
# SSH ke VM B1
ssh user@192.168.18.169
cd /opt/homelab/infrastructure/token-monitor

# Pastikan network rag-net ada
docker network create rag-net 2>/dev/null || true

# Deploy semua service
docker compose up -d --build

# Verifikasi
curl http://localhost:8010/health
```

**URL Production:**
- Dashboard: http://192.168.18.169:3010
- API: http://192.168.18.169:8010

Lihat `SETUP.md` untuk panduan lengkap deployment dan hook configuration.

---

## Troubleshooting

### Container name already in use

```powershell
docker rm -f token-db-local
docker run -d --name token-db-local -e POSTGRES_DB=tokenmonitor -e POSTGRES_USER=tokenuser -e POSTGRES_PASSWORD=tokenpass123 -p 5433:5432 postgres:16-alpine
```

### Connection refused port 5433

Berarti container DB belum jalan. Cek status dan start jika perlu:

```powershell
docker ps -a --filter name=token-db-local
docker start token-db-local
```

### ModuleNotFoundError: No module named 'src'

Backend dijalankan dari folder yang salah. Harus dari dalam `src\backend`:

```powershell
cd src\backend
.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

### DATABASE_URL tidak ter-set (backend konek ke token-db:5432)

Default `DATABASE_URL` di `config.py` mengarah ke hostname Docker internal (`token-db:5432`) yang hanya bekerja di dalam Docker network. Untuk local dev selalu set env var dulu:

```powershell
$env:DATABASE_URL = "postgresql://tokenuser:tokenpass123@localhost:5433/tokenmonitor"
```

### venv error: "Fatal error in launcher: Unable to create process"

Terjadi ketika folder dipindah dan path di dalam `.venv` sudah tidak valid. Solusi: hapus dan buat ulang venv.

```powershell
cd src\backend
Remove-Item -Recurse -Force .venv
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### Port 5433 sudah dipakai proses lain

```powershell
# Cek proses yang pakai port 5433
netstat -ano | findstr :5433

# Ganti port di docker run (misalnya pakai 5434)
docker run -d --name token-db-local -e POSTGRES_DB=tokenmonitor -e POSTGRES_USER=tokenuser -e POSTGRES_PASSWORD=tokenpass123 -p 5434:5432 postgres:16-alpine

# Set DATABASE_URL dengan port baru
$env:DATABASE_URL = "postgresql://tokenuser:tokenpass123@localhost:5434/tokenmonitor"
```

---

## Quick Reference

| Kebutuhan | Command |
|---|---|
| Start DB lokal | `docker run -d --name token-db-local -e POSTGRES_DB=tokenmonitor -e POSTGRES_USER=tokenuser -e POSTGRES_PASSWORD=tokenpass123 -p 5433:5432 postgres:16-alpine` |
| Start DB yang sudah ada | `docker start token-db-local` |
| Stop DB | `docker stop token-db-local` |
| Cek DB ready | `docker exec token-db-local pg_isready -U tokenuser -d tokenmonitor` |
| Jalankan backend | `$env:DATABASE_URL = "postgresql://tokenuser:tokenpass123@localhost:5433/tokenmonitor"` lalu `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` |
| Jalankan frontend | `cd src\frontend && npm run dev` |
| Jalankan tests | `.venv\Scripts\python.exe -m pytest tests/ -v` |
| Health check | `curl http://localhost:8000/health` |
