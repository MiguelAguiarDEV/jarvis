#!/bin/bash
# JARVIS Postgres Backup
# Runs pg_dumpall from the postgres container, compresses, rotates.
# Backs up ALL databases (mnemo + postgres) so nothing is missed.

set -euo pipefail

BACKUP_DIR="/home/mx/backups/jarvis-postgres"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_FILE="$BACKUP_DIR/jarvis-postgres-$TIMESTAMP.sql.gz"
CONTAINER="jarvis-postgres"
PG_USER="mx"

mkdir -p "$BACKUP_DIR"

# Verify container is running
if ! docker inspect -f '{{.State.Running}}' "$CONTAINER" 2>/dev/null | grep -q true; then
    echo "[BACKUP] ERROR: Container $CONTAINER is not running"
    exit 1
fi

echo "[BACKUP] Starting postgres backup at $(date)"
docker exec "$CONTAINER" pg_dumpall -U "$PG_USER" | gzip > "$BACKUP_FILE"

# Validate the archive
if ! gunzip -t "$BACKUP_FILE" 2>/dev/null; then
    echo "[BACKUP] ERROR: Backup file is corrupt: $BACKUP_FILE"
    exit 1
fi

SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
echo "[BACKUP] Done: $BACKUP_FILE ($SIZE)"

# Rotate old backups
find "$BACKUP_DIR" -name "jarvis-postgres-*.sql.gz" -mtime +$RETENTION_DAYS -delete
REMAINING=$(ls -1 "$BACKUP_DIR"/jarvis-postgres-*.sql.gz 2>/dev/null | wc -l)
echo "[BACKUP] Retained $REMAINING backups (last ${RETENTION_DAYS} days)"
