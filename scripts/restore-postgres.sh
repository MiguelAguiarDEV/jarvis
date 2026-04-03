#!/bin/bash
# JARVIS Postgres Restore
# Usage: ./scripts/restore-postgres.sh [backup-file]
# If no file specified, uses the latest backup.
# Backups are pg_dumpall format (all databases).

set -euo pipefail

BACKUP_DIR="/home/mx/backups/jarvis-postgres"
CONTAINER="jarvis-postgres"
PG_USER="mx"

if [ -n "${1:-}" ]; then
    BACKUP_FILE="$1"
else
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/jarvis-postgres-*.sql.gz 2>/dev/null | head -1)
fi

if [ -z "$BACKUP_FILE" ] || [ ! -f "$BACKUP_FILE" ]; then
    echo "[RESTORE] ERROR: No backup file found"
    echo "[RESTORE] Usage: $0 [path/to/backup.sql.gz]"
    exit 1
fi

# Verify container is running
if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
    echo "[RESTORE] ERROR: Container $CONTAINER is not running"
    exit 1
fi

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[RESTORE] Backup file: $BACKUP_FILE ($SIZE)"
echo "[RESTORE] WARNING: This will overwrite ALL databases in the container!"
read -p "Continue? (y/N) " confirm
[ "$confirm" = "y" ] || { echo "[RESTORE] Aborted."; exit 0; }

echo "[RESTORE] Restoring..."
gunzip -c "$BACKUP_FILE" | docker exec -i "$CONTAINER" psql -U "$PG_USER" -d postgres
echo "[RESTORE] Done. Verify with: docker exec $CONTAINER psql -U $PG_USER -l"
