#!/usr/bin/env bash
# Smoke test for a running Arxiu stack (dev or prod).
#
# Verifies each major surface returns the expected status code with
# minimal latency. Run AFTER `make prod-up` (or `make dev-up`) and
# after `make seed`.
#
# Override BASE_URL to test a remote host:
#   BASE_URL=https://arxiu.inslaferreria.cat ./scripts/smoke.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"
ADMIN_DNI="${ADMIN_DNI:-00000000T}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Admin-Pwd-1!}"

red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
blue()  { printf "\033[36m%s\033[0m\n" "$*"; }

failed=0

# ----- health checks --------------------------------------------------
blue "== Health =="
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/healthz")
if [ "$status" = "200" ]; then
  green "  GET /healthz → 200"
else
  red   "  GET /healthz → $status"
  failed=1
fi

# ----- frontend served ------------------------------------------------
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
if [ "$status" = "200" ] || [ "$status" = "304" ]; then
  green "  GET / → $status (frontend served)"
else
  red   "  GET / → $status"
  failed=1
fi

# ----- API docs hidden in production ----------------------------------
status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/openapi.json")
if [ "$status" = "200" ]; then
  green "  OpenAPI exposed (dev mode) — OK if non-prod"
elif [ "$status" = "404" ]; then
  green "  OpenAPI hidden (prod mode) — OK"
else
  red   "  OpenAPI returned $status"
  failed=1
fi

# ----- login flow -----------------------------------------------------
blue "== Login =="
login_resp=$(
  curl -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"identifier\":\"$ADMIN_DNI\",\"password\":\"$ADMIN_PASSWORD\"}"
)
token=$(echo "$login_resp" | grep -o '"access_token":"[^"]*"' | head -1 | cut -d'"' -f4)
if [ -n "$token" ]; then
  green "  POST /auth/login → token issued"
else
  red   "  POST /auth/login failed: $login_resp"
  failed=1
fi

if [ -n "$token" ]; then
  # ----- protected endpoints ------------------------------------------
  blue "== Protected =="
  for path in /api/v1/auth/me /api/v1/dashboard /api/v1/cicles /api/v1/cursos-academics /api/v1/grups /api/v1/alumnes; do
    status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $token" "$BASE_URL$path")
    if [ "$status" = "200" ]; then
      green "  GET $path → 200"
    else
      red   "  GET $path → $status"
      failed=1
    fi
  done

  # ----- exports endpoints --------------------------------------------
  blue "== Exports =="
  # First find an existing alumne id so we can hit the export endpoint
  alumnes_json=$(curl -s -H "Authorization: Bearer $token" "$BASE_URL/api/v1/alumnes?limit=1")
  alumne_id=$(echo "$alumnes_json" | grep -o '"id":[0-9]*' | head -1 | cut -d':' -f2)
  if [ -n "$alumne_id" ]; then
    status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $token" \
      "$BASE_URL/api/v1/export/alumne/$alumne_id.xlsx")
    if [ "$status" = "200" ]; then
      green "  GET /export/alumne/$alumne_id.xlsx → 200"
    else
      red   "  GET /export/alumne/$alumne_id.xlsx → $status"
      failed=1
    fi
  else
    blue "  (no alumnes to export — seed first)"
  fi

  status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $token" "$BASE_URL/api/v1/export/audit.csv?limit=10")
  if [ "$status" = "200" ]; then
    green "  GET /export/audit.csv → 200"
  else
    red   "  GET /export/audit.csv → $status"
    failed=1
  fi

  # ----- paperera -----------------------------------------------------
  blue "== Paperera =="
  status=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer $token" "$BASE_URL/api/v1/trash")
  if [ "$status" = "200" ]; then
    green "  GET /trash → 200"
  else
    red   "  GET /trash → $status"
    failed=1
  fi
fi

echo
if [ $failed -eq 0 ]; then
  green "All smoke checks passed."
  exit 0
else
  red "Smoke FAILED — see above."
  exit 1
fi
