---
name: server-guardrails
description: "Safety rules for server operations. Defines what requires confirmation, what is safe, and caution actions."
always: true
---

# Server Guardrails

## NEVER do without explicit user confirmation
- Delete databases or tables (DROP, TRUNCATE, DELETE FROM without WHERE)
- Stop Postgres container
- Remove Docker volumes
- Modify 1Password secrets
- Delete files in ~/projects/ or ~/services/
- Run rm -rf on any directory
- Change Cloudflare DNS records
- Modify firewall rules
- Change SSH keys or sudo config

## ALWAYS safe to do
- Read files, logs, status
- docker ps, docker logs
- systemctl status
- git status, git log, git diff
- ls, cat, head, tail, grep
- df, free, top, htop, uptime
- svc logs <service>
- curl to health endpoints

## SAFE with caution (do it but report what you did)
- Restart services (svc restart X)
- Rebuild containers (docker compose build)
- Git commit and push
- Create files and directories
- Install packages (apt, npm)
- Modify config files (keep backups)
- Run database queries (SELECT only without confirmation)

## When in doubt
Ask the user before executing. Say exactly what command you plan to run and why.
