#!/bin/bash
# JARVIS — Refresh Claude API key
# 
# Uses OAuth token with org:create_api_key scope to generate
# a temporary API key for JARVIS. This key has its own rate limit pool.
#
# Prerequisites: 
#   1. Token with org:create_api_key scope in ~/.claude/.credentials.json
#   2. Or run with --login flag to do OAuth login first

set -euo pipefail

CREDS="$HOME/.claude/.credentials.json"
API_KEY_FILE="$HOME/.claude/.jarvis-api-key"

# Read current OAuth token
TOKEN=$(python3 -c "import json; print(json.load(open('$CREDS'))['claudeAiOauth']['accessToken'])")

echo "[refresh] Creating temporary API key..."

RESPONSE=$(curl -s -X POST "https://api.anthropic.com/api/oauth/claude_cli/create_api_key" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -H "anthropic-version: 2023-06-01" \
  -H "User-Agent: claude-code/2.1.88" \
  -H "anthropic-beta: oauth-2025-04-20" \
  -d '{}')

API_KEY=$(echo "$RESPONSE" | python3 -c "
import sys,json
d = json.load(sys.stdin)
if 'api_key' in d:
    print(d['api_key'])
elif 'key' in d:
    print(d['key'])
else:
    import sys
    print(f'ERROR: {json.dumps(d)[:200]}', file=sys.stderr)
    sys.exit(1)
" 2>&1)

if [[ "$API_KEY" == ERROR* ]]; then
    echo "[refresh] Failed: $API_KEY"
    exit 1
fi

echo "$API_KEY" > "$API_KEY_FILE"
echo "[refresh] API key saved to $API_KEY_FILE"
echo "[refresh] Key prefix: ${API_KEY:0:15}..."

# Test the key
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "x-api-key: $API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -X POST "https://api.anthropic.com/v1/messages" \
  -d '{"model":"claude-opus-4-6","max_tokens":5,"messages":[{"role":"user","content":"x"}]}')

echo "[refresh] Test with Opus: HTTP $STATUS"
