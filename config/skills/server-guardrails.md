---
name: server-guardrails
description: "Safety rules for server operations. Defines confirmation requirements and safe actions."
always: true
---

# Server Guardrails

## REQUIRES explicit user confirmation
- DROP/TRUNCATE/DELETE without WHERE
- Stop Postgres container
- Remove Docker volumes
- Modify 1Password secrets
- Delete files in ~/projects/ or ~/services/
- rm -rf any directory
- Change Cloudflare DNS
- Modify firewall/SSH/sudo config

## ALWAYS safe
- Read: files, logs, status
- docker ps/logs, systemctl status
- git status/log/diff
- ls, cat, head, tail, grep
- df, free, top, htop, uptime
- svc logs, curl health endpoints

## SAFE with caution (do + report)
- Restart services (svc restart X)
- Rebuild containers (docker compose build)
- Git commit/push
- Create files/directories
- Install packages (apt, npm)
- Modify configs (keep backups)
- SELECT queries (no confirmation needed)

## When in doubt
Ask first. State the exact command and why.
