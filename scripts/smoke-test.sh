#!/usr/bin/env bash
# Smoke test the deployed system through the dispatcher (the API gateway).
#
# Opens a temporary "kubectl port-forward" to the dispatcher Service, then
# checks one request per important path:
#   gateway health -> register/login (auth-service + Mongo) -> 401 without a
#   token -> create and list a product (JWT check, access profile, product-service)
set -euo pipefail

NAMESPACE="product-order"
LOCAL_PORT="${LOCAL_PORT:-8080}"
BASE_URL="http://localhost:${LOCAL_PORT}"
# "alice" has write access in k8s/config/access-profiles.json.
USERNAME="alice"
PASSWORD="smoke-test-password"

pass() { printf '  [PASS] %s\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; exit 1; }

# request METHOD PATH [BODY] [TOKEN] -> prints body, sets global STATUS
request() {
  local method="$1" path="$2" body="${3:-}" token="${4:-}"
  local args=(-s -o /tmp/smoke_body -w '%{http_code}' -X "$method" "${BASE_URL}${path}")
  [[ -n "$body" ]] && args+=(-H 'Content-Type: application/json' -d "$body")
  [[ -n "$token" ]] && args+=(-H "Authorization: Bearer ${token}")
  STATUS="$(curl "${args[@]}")"
  BODY="$(cat /tmp/smoke_body)"
}

echo "==> Port-forwarding svc/dispatcher to localhost:${LOCAL_PORT}"
kubectl -n "$NAMESPACE" port-forward svc/dispatcher "${LOCAL_PORT}:8000" >/tmp/port-forward.log 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT

for _ in $(seq 1 30); do
  curl -s -o /dev/null "${BASE_URL}/health" && break
  sleep 1
done

echo "==> Smoke tests against ${BASE_URL}"

request GET /health
[[ "$STATUS" == 200 ]] && pass "GET /health -> 200" || fail "GET /health -> $STATUS $BODY"

# 409 means the user exists from an earlier run, which is fine.
request POST /auth/register "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}"
[[ "$STATUS" == 200 || "$STATUS" == 409 ]] && pass "POST /auth/register -> $STATUS" || fail "register -> $STATUS $BODY"

request POST /auth/login "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}"
[[ "$STATUS" == 200 ]] || fail "POST /auth/login -> $STATUS $BODY"
TOKEN="$(printf '%s' "$BODY" | sed -n 's/.*"token":"\([^"]*\)".*/\1/p')"
[[ -n "$TOKEN" ]] && pass "POST /auth/login -> 200, got JWT" || fail "no token in login response: $BODY"

request GET /products
[[ "$STATUS" == 401 ]] && pass "GET /products without token -> 401" || fail "expected 401, got $STATUS $BODY"

PRODUCT_NAME="smoke-$(date +%s)"
request POST /products "{\"name\":\"${PRODUCT_NAME}\",\"price\":9.99,\"stock\":5}" "$TOKEN"
[[ "$STATUS" == 200 || "$STATUS" == 201 ]] && pass "POST /products -> $STATUS" || fail "create product -> $STATUS $BODY"

request GET /products "" "$TOKEN"
[[ "$STATUS" == 200 && "$BODY" == *"$PRODUCT_NAME"* ]] \
  && pass "GET /products -> 200, new product listed" \
  || fail "list products -> $STATUS $BODY"

echo "==> All smoke tests passed"
