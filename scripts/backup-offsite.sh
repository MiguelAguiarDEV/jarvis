#!/bin/bash
# JARVIS Postgres Offsite Backup — Push to GitHub private repo
# Runs after local backup (cron 5 3 * * *)
# Retention: 7 most recent backups in the repo

set -euo pipefail

BACKUP_DIR="/home/mx/backups/jarvis-postgres"
OFFSITE_DIR="/home/mx/backups/jarvis-postgres-offsite"
RETENTION=7

echo "[OFFSITE] $(date '+%Y-%m-%d %H:%M:%S') Starting offsite backup..."

# Find latest local backup
LATEST=$(ls -t "$BACKUP_DIR"/jarvis-postgres-*.sql.gz 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then
    echo "[OFFSITE] ERROR: No local backup found"
    exit 1
fi

FILENAME=$(basename "$LATEST")
echo "[OFFSITE] Latest backup: $FILENAME ($(du -h "$LATEST" | cut -f1))"

# Copy to offsite repo
cd "$OFFSITE_DIR"
git pull --rebase --quiet 2>/dev/null || true
cp "$LATEST" "$OFFSITE_DIR/$FILENAME"

# Rotate: keep only last N backups
ls -t "$OFFSITE_DIR"/jarvis-postgres-*.sql.gz 2>/dev/null | tail -n +$((RETENTION + 1)) | while read old; do
    echo "[OFFSITE] Removing old: $(basename "$old")"
    rm "$old"
done

# Commit and push
git add -A
if git diff --cached --quiet; then
    echo "[OFFSITE] No changes to push"
else
    git commit -m "backup: $FILENAME" --quiet
    git push --quiet
    echo "[OFFSITE] Pushed to GitHub"
fi

REMAINING=$(ls -1 "$OFFSITE_DIR"/jarvis-postgres-*.sql.gz 2>/dev/null | wc -l)
echo "[OFFSITE] Done. $REMAINING backups in offsite repo."
