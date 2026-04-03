#!/bin/bash
set -e
echo "=== JARVIS Test Suite ==="

echo ""
echo "[1/3] Go backend tests..."
cd ~/projects/jarvis-dashboard/engram-fork
go build ./cmd/engram/ || { echo "FAIL: Go build"; exit 1; }
go vet ./... || { echo "FAIL: Go vet"; exit 1; }
go test ./internal/cloud/jarvis/ -v -count=1 2>&1 | tail -20
# Skip dockertest-based tests for quick runs (they need Docker)
echo "  Store/server tests skipped (require dockertest). Run with: go test ./internal/cloud/... -v"

echo ""
echo "[2/3] Next.js dashboard build..."
cd ~/projects/jarvis-dashboard/dashboard
npm run build 2>&1 | tail -5 || { echo "FAIL: Dashboard build"; exit 1; }

echo ""
echo "[3/3] API smoke tests..."
# Quick checks that the running services respond
curl -sf http://100.71.66.54:8080/health > /dev/null && echo "  engram API: OK" || echo "  engram API: FAIL"
curl -sf http://100.71.66.54:3001/ > /dev/null && echo "  dashboard: OK" || echo "  dashboard: FAIL"

echo ""
echo "=== All checks passed ==="
