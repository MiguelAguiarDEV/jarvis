#!/usr/bin/env bash
# JARVIS Stack — Start all services
set -euo pipefail
cd "$(dirname "$0")"

BUILD_FLAG=""
USE_OP=false

for arg in "$@"; do
  case "$arg" in
    --build) BUILD_FLAG="--build" ;;
    --op) USE_OP=true ;;
  esac
done

if $USE_OP && command -v op &>/dev/null; then
    echo "[JARVIS] Starting with 1Password secrets..."
    op run --env-file=.env.tpl -- docker compose up -d $BUILD_FLAG
elif [[ -f .env ]]; then
    echo "[JARVIS] Starting with .env file..."
    docker compose --env-file .env up -d $BUILD_FLAG
else
    echo "[JARVIS] ERROR: No .env file found. Use --op flag or create .env"
    exit 1
fi

echo ""
echo "[JARVIS] Waiting for services..."
sleep 5
docker compose ps
echo ""
echo "[JARVIS] Health:"
curl -sf http://100.71.66.54:8080/health && echo " athena OK" || echo " athena FAIL"
curl -sf http://100.71.66.54:3001 > /dev/null && echo " nexus OK" || echo " nexus FAIL"
echo "[JARVIS] Stack ready."
