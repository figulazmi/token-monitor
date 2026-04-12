---
id: 2026-04-13-token-monitor-deploy-setup
date: 2026-04-13
source: claude-code-cli
project: homelab
topic: Token Monitor VM B1 Deployment - Port Conflict and Auth Fix
tags: [token-monitor, docker, fastapi, github-ssh, port-conflict, hooks, homelab, deploy]
related: [homelab-infrastructure, claude-code-hooks, docker-compose]
session_type: setup
environment: homelab
git_branch: main
status: implemented
chunk_source: code
---

## CHUNK 1: Token Monitor Deployment Path Decision

### Context

Token-monitor is a FastAPI + React + PostgreSQL app deployed on VM B1 homelab at `192.168.18.169`. The existing VM structure under `/opt/homelab/` has two categories: `ai-stack/` (Qdrant, RAG Gateway, OpenClaw) and `infrastructure/` (Portainer, Uptime Kuma).

### Problem

Deciding where to clone the repo on VM B1 — `/opt/homelab/token-monitor/` (flat), `/opt/homelab/ai-stack/token-monitor/`, or `/opt/homelab/infrastructure/token-monitor/`.

### Solution

Deployed to `/opt/homelab/infrastructure/token-monitor/`. Rationale: token-monitor is a monitoring/observability tool (monitors token usage), semantically equivalent to uptime-kuma (monitors uptime). `ai-stack/` is reserved for services that *provide* AI capabilities (Qdrant, RAG Gateway). All documentation and CI/CD paths updated accordingly.

### Key Facts

- Final deploy path: `/opt/homelab/infrastructure/token-monitor/`
- `ai-stack/` = services providing AI capabilities (Qdrant, RAG, Ollama)
- `infrastructure/` = tooling that observes/manages the system (Portainer, Uptime Kuma, token-monitor)
- All references in README.md, SETUP.md, RUNNING.md, CLAUDE.md, deploy.yml updated from `/opt/homelab/token-monitor/` to `/opt/homelab/infrastructure/token-monitor/`

---

## CHUNK 2: Port Conflict Resolution on VM B1

### Context

Token-monitor docker-compose.yml originally mapped UI to port 3000 and API to port 8000. VM B1 runs multiple Docker services simultaneously.

### Problem

Both ports already occupied: 3000 by Open WebUI, 8000 by another docker-proxy process. Running `ss -tlnp | grep LISTEN` revealed the full picture. Other occupied ports: 3001 (Uptime Kuma), 5678 (n8n), 6333/6334 (Qdrant), 9000/9443 (Portainer), 11434 (Ollama).

### Solution

Changed port mappings in `docker-compose.yml`:
- UI: `3000:80` → `3010:80`
- API: `8000:8000` → `8010:8000`

Updated all references across: `docker-compose.yml`, `CLAUDE.md`, `README.md`, `SETUP.md`, `RUNNING.md`, `.gitea/workflows/deploy.yml`, `src/scripts/auto-logger.py`, `src/frontend/src/services/api.ts`.

### Key Facts

- Dashboard now at: `http://192.168.18.169:3010`
- API now at: `http://192.168.18.169:8010`
- `vite.config.ts` local dev proxy target `localhost:8000` intentionally left unchanged — that is the internal container port for local development, not production
- `ss -tlnp | grep LISTEN` is the correct command to audit all occupied ports on VM B1

### Code / Commands

```yaml
# docker-compose.yml — final port mapping
token-api:
  ports:
    - "8010:8000"   # external 8010 -> internal 8000

token-ui:
  ports:
    - "3010:80"     # external 3010 -> internal 80
```

---

## CHUNK 3: GitHub SSH Authentication on VM B1

### Context

VM B1 needs to push/pull to GitHub repo `figulazmi/token-monitor`. The VM had no SSH key configured and the user's GitHub account has 2FA enabled.

### Problem

`git push origin main` failed with `remote: Invalid username or token. Password authentication is not supported for Git operations.` GitHub removed password auth support in 2021; 2FA makes it impossible regardless.

### Solution

Generated ED25519 SSH key on VM B1, added public key to GitHub, switched remote URL to SSH format.

### Key Facts

- GitHub does not support password authentication for Git operations since August 2021
- 2FA on GitHub makes password auth impossible even if it were supported
- SSH key is the recommended approach for servers (no expiry, no plain-text secrets)
- PAT (Personal Access Token) is an alternative but can expire and gets embedded in remote URL

### Code / Commands

```bash
# On VM B1 - generate key
ssh-keygen -t ed25519 -C "vm-b1-token-monitor" -f ~/.ssh/id_ed25519 -N ""
cat ~/.ssh/id_ed25519.pub
# copy output to https://github.com/settings/ssh/new

# Switch remote from HTTPS to SSH
git remote set-url origin git@github.com:figulazmi/token-monitor.git
git push origin main
```

---

## CHUNK 4: Git Push Rejected - Remote Ahead of Local

### Context

After switching to SSH on VM B1 and attempting `git push origin main`, push was rejected because the laptop had committed changes (port updates) that were not present on VM B1's local clone.

### Problem

```
! [rejected] main -> main (fetch first)
error: failed to push some refs to 'github.com:figulazmi/token-monitor.git'
hint: Updates were rejected because the remote contains work that you do not have locally.
```

### Solution

Pull with rebase before pushing: `git pull --rebase origin main && git push origin main`. Rebase is preferred over merge here to avoid creating an unnecessary merge commit when there are no conflicting changes.

### Key Facts

- `git pull --rebase` avoids a merge commit when remote has newer commits with no conflict
- This scenario is expected when: changes made on laptop pushed to GitHub and VM B1 clone is behind
- Normal redeploy workflow: `git pull origin main` on VM B1 (not git push) — VM B1 is a deployment target, not a development machine

---

## CHUNK 5: SessionEnd Hook - Wrong TOKEN_MONITOR_URL

### Context

The Claude Code global settings file at `C:\Users\Clandesitine\.claude\settings.json` already had a `SessionEnd` hook configured to run `auto-logger.py`. This hook fires on `/exit`, `/clear`, Ctrl-C, and session timeout.

### Problem

Hook command had a hardcoded override: `TOKEN_MONITOR_URL=http://localhost:8000` — pointing to localhost instead of VM B1. This means every session end would attempt to POST to the local machine (which has no API running) and silently fail.

### Solution

Removed the `TOKEN_MONITOR_URL=http://localhost:8000` prefix from the hook command. The default in `auto-logger.py` line 34 was already updated to `http://192.168.18.169:8010` in this session, so no override needed.

### Key Facts

- Hook fires from laptop (Windows), not from VM B1
- `auto-logger.py` default `TOKEN_MONITOR_URL` = `http://192.168.18.169:8010` (updated this session)
- Account auto-detected from `claude auth status` -> `figurululazmi@gmail.com` -> `claude-figur`
- Claude Code hooks do not support slash command triggers — only `SessionEnd`, `PreToolUse`, `PostToolUse`, `Stop`, `Notification`

### Code / Commands

```json
// C:\Users\Clandesitine\.claude\settings.json — final hook config
"hooks": {
  "SessionEnd": [{
    "matcher": "",
    "hooks": [{
      "type": "command",
      "command": "python C:\\Users\\Clandesitine\\source\\repos\\token-monitor\\src\\scripts\\auto-logger.py"
    }]
  }]
}
```

---

## SESSION METADATA

- **Total chunks**: 5
- **Qdrant collection**: knowledge
- **Primary project**: homelab
- **Stack involved**: FastAPI, Docker Compose, React, PostgreSQL, GitHub SSH, Claude Code hooks
- **Files modified**: `docker-compose.yml`, `CLAUDE.md`, `README.md`, `SETUP.md`, `RUNNING.md`, `.gitea/workflows/deploy.yml`, `src/scripts/auto-logger.py`, `src/frontend/src/services/api.ts`, `C:\Users\Clandesitine\.claude\settings.json`
- **Git branch**: main
- **Unresolved items**: Verify first real session log appears at `http://192.168.18.169:3010` after next `/clear`
- **Author**: Figur Ulul Azmi
- **Generated by**: Claude Code CLI — RAG Knowledge Capture Skill
