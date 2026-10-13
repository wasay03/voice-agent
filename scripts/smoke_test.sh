#!/usr/bin/env bash
# End-to-end checks against a running deployment. Creates one test patient and soft-deletes it.
#   BASE_URL=https://<service>.up.railway.app API_KEY=... ./scripts/smoke_test.sh
# With no arguments it targets http://localhost:8000 and reads API_KEY from .env.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
if [[ -z "${API_KEY:-}" && -f .env ]]; then
  API_KEY=$(grep -E '^API_KEY=' .env | cut -d= -f2-)
fi
: "${API_KEY:?set API_KEY}"

pass() { printf '  \033[32mok\033[0m   %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; exit 1; }
json() { python3 -c "import sys, json; d = json.load(sys.stdin); print($1)"; }

BODY=$(mktemp); trap 'rm -f "$BODY"' EXIT
call() {  # call <method> <path> [json-body] -> sets STATUS, response body in $BODY
  local method=$1 path=$2 data=${3:-}
  STATUS=$(curl -s -o "$BODY" -w '%{http_code}' -X "$method" "$BASE_URL$path" \
    -H "X-API-Key: $API_KEY" -H 'Content-Type: application/json' ${data:+--data "$data"})
}
expect() {  # expect <description> <status>
  [[ "$STATUS" == "$2" ]] && pass "$1 ($STATUS)" || fail "$1: expected $2, got $STATUS — $(cat "$BODY")"
}

echo "Smoke test against $BASE_URL"

call GET /healthz;              expect "liveness /healthz" 200
call GET /health;               expect "readiness /health (database reachable)" 200
STATUS=$(curl -s -o /dev/null -w '%{http_code}' "$BASE_URL/patients"); expect "no API key is rejected" 401

PHONE="682555$(printf '%04d' $((RANDOM % 10000)))"
call POST /patients "{\"first_name\":\"smoke\",\"last_name\":\"test\",\"date_of_birth\":\"1990-06-15\",
  \"sex\":\"other\",\"phone_number\":\"$PHONE\",\"address_line_1\":\"1 Test Way\",\"city\":\"fort worth\",
  \"state\":\"texas\",\"zip_code\":\"76102\"}"
expect "create patient" 201
ID=$(json 'd["data"]["patient_id"]' < "$BODY")
[[ $(json 'd["data"]["state"] + "|" + d["data"]["date_of_birth"]' < "$BODY") == "TX|06/15/1990" ]] \
  && pass "normalised state and US date format" || fail "normalisation: $(cat "$BODY")"

call GET "/patients/$ID";                       expect "get by id" 200
call GET "/patients?phone_number=($PHONE)";     expect "filter by phone (any formatting)" 200
[[ $(json 'len(d["data"])' < "$BODY") -ge 1 ]] && pass "filter finds the patient" || fail "filter returned nothing"
call PUT "/patients/$ID" '{"city":"Dallas"}';   expect "partial update" 200
call POST /patients '{"first_name":"x","phone_number":"555"}'; expect "invalid body" 422
call GET /patients/not-a-uuid;                  expect "malformed id" 400
call DELETE "/patients/$ID";                    expect "soft delete" 200
call GET "/patients/$ID";                       expect "deleted patient is gone" 404

echo "All checks passed."
