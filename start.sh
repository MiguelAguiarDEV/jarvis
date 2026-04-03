#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

op run --env-file=.env.tpl -- docker compose up -d --build "$@"
