# Token Monitor — Setup & Deployment Guide

*Authored by: Figur Ulul Azmi*

---

## 1. First Deploy on VM B1

```bash
# SSH into VM B1
ssh user@192.168.18.169

# Clone repo
git clone <repo-url> /opt/homelab/token-monitor
cd /opt/homelab/token-monitor

# Ensure Docker network exists (shared with rag-gateway)
docker network ls | grep rag-net || docker network create rag-net

# Deploy
docker compose up -d --build

# Verify
curl http://localhost:8000/health
# → {"status":"ok","timestamp":"..."}

curl http://localhost:8000/stats
# → {"total_sessions":0,...}
```

**Dashboard:** http://192.168.18.169:3000  
**API:**       http://192.168.18.169:8000

---

## 2. Update & Redeploy

```bash
# Laptop — commit + push
git push origin main

# VM B1 — pull + rebuild
cd /opt/homelab/token-monitor
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
chmod +x /opt/homelab/token-monitor/scripts/auto-logger.py
```

### 4b. Configure per account (on your laptop)

Add to each project's `.claude/settings.json`:

**Account: azmi.codes@gmail.com**
```json
{
  "hooks": {
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "CLAUDE_ACCOUNT=claude-azmi TOKEN_MONITOR_PROJECT=my-project python3 /opt/homelab/token-monitor/scripts/auto-logger.py"
      }]
    }]
  }
}
```

**Account: figulazmi@gmail.com**
```json
{
  "hooks": {
    "SessionEnd": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "CLAUDE_ACCOUNT=claude-figul TOKEN_MONITOR_PROJECT=my-project python3 /opt/homelab/token-monitor/scripts/auto-logger.py"
      }]
    }]
  }
}
```

### 4c. Environment variables

| Variable               | Default                      | Description                             |
|------------------------|------------------------------|-----------------------------------------|
| `TOKEN_MONITOR_URL`    | `http://192.168.18.169:8000` | Backend API URL                         |
| `CLAUDE_ACCOUNT`       | `claude-azmi`                | Account identifier (see table below)    |
| `CLAUDE_MODEL`         | `claude-sonnet-4-6`          | Model used in the session               |
| `TOKEN_MONITOR_PROJECT`| CWD folder name              | Project name tag                        |

| `CLAUDE_ACCOUNT` value | Account                 |
|------------------------|-------------------------|
| `claude-azmi`          | Claude Pro azmi.codes   |
| `claude-figul`         | Claude Pro figulazmi    |
| `copilot-azmi`         | Copilot azmi.codes      |

### 4d. Override model per project

```bash
CLAUDE_ACCOUNT=claude-azmi CLAUDE_MODEL=claude-opus-4-6 TOKEN_MONITOR_PROJECT=homelab \
  python3 /opt/homelab/token-monitor/scripts/auto-logger.py
```

---

## 5. Manual Testing

```bash
# Test the hook script manually
echo '{"usage":{"input_tokens":1000,"output_tokens":300}}' | \
  CLAUDE_ACCOUNT=claude-azmi TOKEN_MONITOR_PROJECT=test \
  python3 /opt/homelab/token-monitor/scripts/auto-logger.py
# → [auto-logger] Logged 1,300 tokens (1,000 in / 300 out) [claude-azmi] → http://...

# Manual POST via curl
curl -X POST http://localhost:8000/sessions \
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
curl http://localhost:8000/stats | python3 -m json.tool

# Filter by account
curl "http://localhost:8000/sessions?account=claude-azmi&limit=10"
```

---

## 6. GitHub Copilot — Manual Logging

Copilot does not have a hook system. Use the dashboard form at  
**http://192.168.18.169:3000** → `+ LOG SESSION` → select **GitHub Copilot** + **Copilot · azmi.codes**.

---

## 7. Optional — Custom DB Password

Create `/opt/homelab/token-monitor/.env`:

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
curl http://192.168.18.169:8000/health

# 2. Dashboard loads
curl -s http://192.168.18.169:3000 | grep "TOKEN MONITOR"

# 3. Test hook
echo '{"usage":{"input_tokens":500,"output_tokens":100}}' | \
  CLAUDE_ACCOUNT=claude-azmi TOKEN_MONITOR_PROJECT=validation-test \
  python3 /opt/homelab/token-monitor/scripts/auto-logger.py

# 4. Verify data appeared
curl "http://192.168.18.169:8000/sessions?limit=1" | python3 -m json.tool
```
