#!/bin/bash
# Scans the server and outputs a markdown knowledge file
# Called periodically or on demand by JARVIS

OUTPUT="/home/mx/projects/jarvis-dashboard/config/skills/server-knowledge.md"

cat > "$OUTPUT" << 'FRONTMATTER'
---
name: server-knowledge
description: "Auto-generated server state: system info, Docker services, network, secrets vault locations."
always: true
---
FRONTMATTER

cat >> "$OUTPUT" << HEADER
# Server Knowledge (auto-generated)
> Last scan: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
HEADER

echo "" >> "$OUTPUT"
echo "## System Info" >> "$OUTPUT"
echo "- Hostname: $(hostname)" >> "$OUTPUT"
echo "- OS: $(cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2 | tr -d '"')" >> "$OUTPUT"
echo "- Kernel: $(uname -r)" >> "$OUTPUT"
echo "- CPU: $(nproc) cores" >> "$OUTPUT"
echo "- RAM: $(free -h | awk '/Mem:/ {print $2}') total, $(free -h | awk '/Mem:/ {print $3}') used" >> "$OUTPUT"
echo "- Disk: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 " used)"}')" >> "$OUTPUT"
echo "- Uptime: $(uptime -p)" >> "$OUTPUT"
echo "- Tailscale IP: $(tailscale ip -4 2>/dev/null || echo 'N/A')" >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "## Docker Services" >> "$OUTPUT"
echo "| Name | Status | Ports | Image |" >> "$OUTPUT"
echo "|------|--------|-------|-------|" >> "$OUTPUT"
docker ps --format '| {{.Names}} | {{.Status}} | {{.Ports}} | {{.Image}} |' 2>/dev/null >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "## Systemd Services (custom)" >> "$OUTPUT"
for svc in opencode-serve cloudflared smbd; do
  status=$(systemctl is-active $svc 2>/dev/null)
  echo "- $svc: $status" >> "$OUTPUT"
done

echo "" >> "$OUTPUT"
echo "## Directory Structure" >> "$OUTPUT"
echo '```' >> "$OUTPUT"
echo "~/projects/" >> "$OUTPUT"
ls -1 ~/projects/ 2>/dev/null | sed 's/^/  /' >> "$OUTPUT"
echo "~/services/" >> "$OUTPUT"
ls -1 ~/services/ 2>/dev/null | sed 's/^/  /' >> "$OUTPUT"
echo "~/personal-knowledgebase/" >> "$OUTPUT"
ls -1 ~/personal-knowledgebase/ 2>/dev/null | sed 's/^/  /' >> "$OUTPUT"
echo '```' >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "## Public URLs" >> "$OUTPUT"
echo "- Dashboard: https://jarvis.miguelaguiar.dev" >> "$OUTPUT"
echo "- Mnemo API: https://mnemo.miguelaguiar.dev" >> "$OUTPUT"
echo "- Portfolio: https://miguelaguiar.dev" >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "## Service Management" >> "$OUTPUT"
echo "- Start/stop services: \`~/services/svc up|down|restart|logs <name>\`" >> "$OUTPUT"
echo "- Services use 1Password for secrets: \`.env.tpl\` with \`op://\` references" >> "$OUTPUT"
echo "- Rebuild: \`cd ~/services/<name> && docker compose build --no-cache\`" >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "## Network" >> "$OUTPUT"
echo "- Docker network: postgres_default (shared by all services)" >> "$OUTPUT"
echo "- Tailscale: all services bind to $(tailscale ip -4 2>/dev/null || echo '100.71.66.54')" >> "$OUTPUT"
echo "- Cloudflare Tunnel: jarvis-homelab" >> "$OUTPUT"
echo "- Samba: \\\\\\\\$(tailscale ip -4 2>/dev/null || echo '100.71.66.54')\\\\jarvis (Tailscale only)" >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "## Secrets (1Password vault: Desarrollo)" >> "$OUTPUT"
echo "- jarvis-mnemo-cloud: DB URL, JWT secret, cloud API key" >> "$OUTPUT"
echo "- jarvis-dashboard: API URL, API key" >> "$OUTPUT"
echo "- jarvis-discord-bot: bot token, user ID" >> "$OUTPUT"
echo "- jarvis-opencode-server: server password" >> "$OUTPUT"
echo "- jarvis-samba: SMB credentials" >> "$OUTPUT"
echo "- cloudflare: API key, tunnel token, zone/account IDs" >> "$OUTPUT"
echo "- jarvis-postgres: DB password" >> "$OUTPUT"

echo "Server scan complete: $OUTPUT"
