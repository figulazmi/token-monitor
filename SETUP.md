# Token Monitor — Setup & Deployment

Backend monitoring token usage Claude Code CLI + Copilot, deployed di VM B1 dengan FastAPI + PostgreSQL.

*Authored by: Figur Ulul Azmi*

---

## Steps

1. Copy folder `token-monitor/` ke VM B1
2. Pastikan Docker network `rag-net` sudah ada: `docker network ls`
3. Deploy stack:
   ```bash
   cd /opt/homelab/token-monitor
   docker compose up -d --build
   ```
4. Verifikasi API up: `curl http://localhost:8000/health`
5. Copy `scripts/auto-logger.py` ke lokasi permanen, misal `/opt/homelab/scripts/auto-logger.py`
6. Set executable: `chmod +x /opt/homelab/scripts/auto-logger.py`
7. Daftarkan hook di setiap project (lihat bagian Config)

---

## Commands

```bash
# Deploy / rebuild
docker compose up -d --build

# Cek log API
docker logs token-api -f

# Cek log DB
docker logs token-db -f

# Test POST manual
curl -X POST http://localhost:8000/log \
  -H "Content-Type: application/json" \
  -d '{"platform":"claude","model":"claude-sonnet-4-6","input_tokens":5000,"output_tokens":1200,"label":"test session","project":"petrochina-eproc"}'

# Lihat stats
curl http://localhost:8000/stats | python3 -m json.tool

# Lihat sessions
curl http://localhost:8000/sessions?limit=10 | python3 -m json.tool
```

---

## Config

### Hook Claude Code (per project — tambahkan ke `.claude/settings.json`)

```json
{
  "hooks": {
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "TOKEN_MONITOR_PROJECT=petrochina-eproc python3 /opt/homelab/scripts/auto-logger.py"
          }
        ]
      }
    ]
  }
}
```

### Environment variables auto-logger

| Variable | Default | Keterangan |
|---|---|---|
| `TOKEN_MONITOR_URL` | `http://192.168.18.169:8000` | URL FastAPI |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Model yang dipakai |
| `TOKEN_MONITOR_PROJECT` | nama folder CWD | Nama project |

### Untuk project berbeda (homelab, dll)

```json
"command": "TOKEN_MONITOR_PROJECT=homelab CLAUDE_MODEL=claude-opus-4-6 python3 /opt/homelab/scripts/auto-logger.py"
```

---

## Usage

- **Dashboard**: buka artifact React token-monitor, fetch dari `http://192.168.18.169:8000`
- **Stats harian**: `curl http://192.168.18.169:8000/stats`
- **Filter per project**: `curl http://192.168.18.169:8000/sessions?project=petrochina-eproc`
- **Hook otomatis**: fire setiap session Claude Code selesai (exit / `/clear` / timeout)
- **Log manual Copilot**: input via dashboard React (form "+ Log Session")

---

## Benefits

- Token usage Claude Code CLI ter-log otomatis tanpa intervensi manual
- Estimasi biaya real berdasarkan API rates per model
- Bisa identifikasi jam/hari paling boros token → optimasi jadwal kerja
- Data persist di PostgreSQL → bisa query historis kapanpun
- Join `rag-net` yang sudah ada → tidak perlu setup network baru
- Copilot tetap bisa dilog manual via dashboard

---

## Validation

```bash
# 1. Health check
curl http://localhost:8000/health
# Expected: {"status":"ok","timestamp":"..."}

# 2. Test hook manual
echo '{"usage":{"input_tokens":1000,"output_tokens":300}}' | \
  TOKEN_MONITOR_PROJECT=test python3 /opt/homelab/scripts/auto-logger.py
# Expected: [auto-logger] Logged 1,300 tokens (1,000 in / 300 out) → http://...

# 3. Verifikasi data masuk
curl http://localhost:8000/sessions?limit=1
```

---

## Notes

- Hook `SessionEnd` fire saat: exit Claude Code, `/clear`, session timeout
- Jika API down saat session selesai, log **tidak di-retry** — data hilang untuk session itu
- Port `8000` exposed ke host — akses via Tailscale dari mesin developer
- `psycopg2-binary` dipakai untuk simplicity; production bisa ganti ke `psycopg2`
