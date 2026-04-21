---
id: 2026-04-21-token-monitor-account-display-deploy-fixes
date: 2026-04-21
source: claude-code-cli
project: homelab
topic: Token Monitor Account Display Fix - Manual Deploy - DB Cleanup
tags: [token-monitor, react, docker, vm-b1, postgresql, account-detection, fixed, homelab]
related: [auto-logger, sessionend-hook, docker-deploy]
session_type: debug
environment: homelab
git_branch: main
status: implemented
chunk_source: code
---

## CHUNK 1: Token Monitor Shows "claude" Instead of Account Name in Session History

### Context

Token Monitor frontend (React/Vite) displays session history with account labels.
The `auto-logger.py` SessionEnd hook detects account via `claude auth status` → email
local-part (e.g. `figurululazmi@gmail.com` → `figurululazmi`). The frontend
`ACCOUNT_META` map translates account IDs to display labels.

### Problem

Session history showed "claude" as the account label instead of "Claude · figurululazmi".
The `auto-logger.py` was correctly detecting and posting `account = "figurululazmi"` to
the backend, but the frontend `ACCOUNT_META` only had legacy slugs as keys:
`claude-figur` and `claude-azmi`. Since `ACCOUNT_META["figurululazmi"]` was `undefined`,
the fallback rendered `l.platform` which equals `"claude"`.

```js
// TokenMonitor.jsx line 1084 — fallback was the problem
const meta = ACCOUNT_META[l.account] || {
  color: '#888',
  label: l.platform,  // → "claude" when account not in ACCOUNT_META
};
```

### Solution

Updated `ACCOUNTS` and `ACCOUNT_META` in `src/frontend/src/TokenMonitor.jsx` to use
real auto-detected slugs as primary keys. Legacy slugs kept for backward compatibility
(existing DB rows with old IDs still render correctly).

```js
const ACCOUNTS = {
  claude: [
    { id: 'figurululazmi', label: 'Claude Pro · figurululazmi' },
    { id: 'azmi-codes', label: 'Claude Pro · azmi.codes' },
  ],
  copilot: [{ id: 'copilot-azmi', label: 'Copilot · azmi.codes' }],
};

const ACCOUNT_META = {
  'figurululazmi': { label: 'Claude · figurululazmi', color: '#9B59B6' },
  'azmi-codes':    { label: 'Claude · azmi.codes',    color: '#FF6B35' },
  'copilot-azmi':  { label: 'Copilot · azmi.codes',   color: '#0078D4' },
  // legacy backward compat
  'claude-figur':  { label: 'Claude · figurululazmi', color: '#9B59B6' },
  'claude-azmi':   { label: 'Claude · azmi.codes',    color: '#FF6B35' },
};
```

### Key Facts

- `auto-logger.py` derives account slug from `claude auth status` JSON email field: `figurululazmi@gmail.com` → `figurululazmi`
- Frontend `ACCOUNT_META` keys must match the exact account IDs stored in the DB
- Fallback label in ACCOUNT_META is `l.platform` which is hardcoded `"claude"` — misleading
- Legacy slugs `claude-figur` / `claude-azmi` were the old manually assigned IDs before auto-detection
- File: `src/frontend/src/TokenMonitor.jsx` lines 45-57

---

## CHUNK 2: Manual Deploy to VM B1 When Gitea CI Is Down

### Context

Token Monitor auto-deploys via Gitea CI on push to `main`. The repo at
`/opt/homelab/infrastructure/token-monitor` on VM B1 is owned by `root`.
User `figulazmi` has docker access but no passwordless sudo.
VM B1 has no internet access (cannot reach GitHub or Docker Hub).

### Problem

Gitea CI was not working. Manual SSH deploy failed because:
1. `git pull` requires root (`.git` dir owned by root, permission denied)
2. `sudo git pull` requires interactive password — not possible in non-interactive SSH
3. Fresh `git clone` from GitHub failed — VM B1 cannot resolve `github.com`
4. `docker compose up --build` failed — cannot pull base images from Docker Hub (no internet)

### Solution

Build frontend locally on Windows, then deploy built artifacts via `docker cp`:

```bash
# Step 1: Build locally on Windows
cd src/frontend && npm run build

# Step 2: SCP dist to VM B1
scp -r src/frontend/dist/ figulazmi@192.168.18.199:/tmp/token-ui-dist

# Step 3: Copy into running container + reload nginx
ssh figulazmi@192.168.18.199 \
  "docker cp /tmp/token-ui-dist/. token-ui:/usr/share/nginx/html/ && \
   docker exec token-ui nginx -s reload"
```

### Key Facts

- VM B1 has no internet access — Docker Hub and GitHub unreachable
- `/opt/homelab/infrastructure/token-monitor` owned by root — figulazmi cannot git pull
- `figulazmi` is in the docker group — can run all docker commands without sudo
- `docker cp` + `nginx -s reload` is sufficient for frontend-only changes (no rebuild needed)
- This method is NOT persistent — if `token-ui` container is recreated, changes are lost
- For persistent fix: need to resolve Gitea CI or grant figulazmi sudo access to the repo dir

### Caveats

Changes deployed via `docker cp` are ephemeral. If the container is recreated (e.g., `docker compose up`), the old image is used and changes are gone. Permanent fix requires either fixing Gitea CI or running `docker compose up --build` with repo write access.

---

## CHUNK 3: Duplicate Account Entries in Token Monitor Stats (Legacy vs New IDs)

### Context

After fixing frontend `ACCOUNT_META` to map both old and new account slugs to the same
display labels, the stats page showed duplicate entries for the same accounts:
"Claude · azmi.codes" appeared twice with different totals, same for "Claude · figurululazmi".

### Problem

The PostgreSQL `session_logs` table had rows with both legacy account IDs (`claude-azmi`,
`claude-figur`) and new auto-detected IDs (`azmi-codes`, `figurululazmi`). The backend
`/stats` endpoint aggregates by the raw `account` column — treating them as separate accounts.
Result: 4 rows in by_account stats instead of 2.

```
 account        | sessions
 azmi-codes     | 26
 claude-azmi    |  2      -- legacy
 claude-figur   |  1      -- legacy
 figurululazmi  | 18
```

### Solution

Direct DB UPDATE to migrate legacy IDs to new IDs:

```sql
UPDATE session_logs SET account = 'azmi-codes'    WHERE account = 'claude-azmi';
UPDATE session_logs SET account = 'figurululazmi' WHERE account = 'claude-figur';
```

Result: 2 accounts, no duplicates. `claude-azmi` (2 rows) merged into `azmi-codes` (now 28),
`claude-figur` (1 row) merged into `figurululazmi` (now 19).

### Key Facts

- Token Monitor DB: `tokenmonitor` database, user `tokenuser`, container `token-db`
- Connect: `docker exec token-db psql -U tokenuser -d tokenmonitor`
- Stats duplication caused by inconsistent account IDs in DB, not a frontend or backend bug
- Old IDs were manually set before auto-detection was implemented
- After migration, old keys in `ACCOUNT_META` still serve as display-name fallback for any edge cases

---

## CHUNK 4: 0-Token RAG Capture Sessions Polluting Session History

### Context

Token Monitor session history showed entries with 0 tokens and $0.0000 cost, labeled
"RAG Capture: [filename].md". These were created by the `--checkpoint` mode of
`auto-logger.py`, triggered via a `PostToolUse Write` hook whenever
`.claude/summaries/*.md` was written (RAG knowledge capture).

### Problem

The design intent was to create timestamp markers in Token Monitor when knowledge was
captured. In practice, these 0-token entries polluted the session history with noise
and confused the user, who did not distinguish them from failed real sessions.
There were 11 such entries in the DB.

### Solution

Two-part fix:

**1. Delete existing 0-token entries from DB:**
```sql
DELETE FROM session_logs WHERE input_tokens = 0 AND output_tokens = 0;
-- Deleted 11 rows
```

**2. Disable POST in `--checkpoint` mode of `auto-logger.py`:**
```python
def main_checkpoint():
    """No-op: 0-token checkpoint entries add noise to Token Monitor history.
    Real token usage is captured by the SessionEnd hook instead."""
    sys.exit(0)
```

### Key Facts

- All 11 zero-token sessions were RAG Capture checkpoints — none were failed real sessions
- `--checkpoint` mode is triggered by `PostToolUse Write` hook in `~/.claude/settings.json`
- The PostToolUse hook remains configured but now silently exits — no API calls made
- SessionEnd hook still fires on `/clear` or exit and logs actual token usage correctly
- File modified: `src/scripts/auto-logger.py` — `main_checkpoint()` function

---

## SESSION METADATA

- **Total chunks**: 4
- **Qdrant collection**: knowledge
- **Primary project**: homelab
- **Stack involved**: React, Vite, nginx, Docker, PostgreSQL, Python, SSH, auto-logger.py
- **Files modified**: `src/frontend/src/TokenMonitor.jsx`, `src/scripts/auto-logger.py`
- **Git branch**: main
- **Unresolved items**: Gitea CI auto-deploy not working -- needs investigation; `docker cp` deploy is ephemeral (container recreate will revert frontend changes)
- **Author**: Figur Ulul Azmi
- **Generated by**: Claude Code CLI -- RAG Knowledge Capture Skill
