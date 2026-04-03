---
name: heartbeat
description: "Proactive self-evaluation checklist. Evaluated by SENTINEL every 15 min."
---

# Heartbeat Checklist

Evaluate each item. If everything is fine, respond HEARTBEAT_OK. If something needs attention, alert via notify.

## Critical (always check)
- [ ] Server health: disk > 20% free, memory > 500MB free
- [ ] Docker services: all containers healthy (postgres, athena, nexus)
- [ ] PROMETHEUS bridge: responding on :9876

## Important (check every hour)
- [ ] Pending tasks: any task stuck > 24h? Alert owner.
- [ ] Failed jobs: any delegation failed? Report error.
- [ ] Memory: last mnemo save > 6h ago? Remind to persist context.

## Nice to have (check daily)
- [ ] Git: uncommitted changes in ~/projects/jarvis-dashboard/?
- [ ] Disk cleanup: any /tmp files > 1GB?
- [ ] Docker: orphaned containers or images?

## Rules
- Use the cheapest model for heartbeat (Sonnet, never Opus)
- Keep evaluation under 500 tokens
- Only notify if actionable — suppress noise
- Log heartbeat result to traces
