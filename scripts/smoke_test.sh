#!/usr/bin/env bash
# End-to-end checks against a running deployment.
#   BASE_URL=https://<service>.onrender.com API_KEY=... ./scripts/smoke_test.sh
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }

expect_status() {  # expect_status <description> <expected> <curl args...>
  local desc=$1 expected=$2; shift 2
  local status
  status=$(curl -s -o /dev/null -w '%{http_code}' "$@")
  [[ "$status" == "$expected" ]] && pass "$desc ($status)" || fail "$desc: expected $expected, got $status"
}

echo "Smoke test against $BASE_URL"
expect_status "liveness /healthz" 200 "$BASE_URL/healthz"
expect_status "readiness /health (database reachable)" 200 "$BASE_URL/health"
expect_status "unknown route returns 404" 404 "$BASE_URL/does-not-exist"
echo "All checks passed."
