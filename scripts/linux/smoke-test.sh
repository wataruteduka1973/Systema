#!/usr/bin/env bash
# Smoke-test a running Docker Compose deployment from the host (production mode).
#
#   scripts/linux/smoke-test.sh example.com [http://127.0.0.1:8000]
#
# Requests carry the given Host and X-Forwarded-Proto: https, as the HTTPS reverse proxy would
# send them. Checks the HTTP->HTTPS redirect, the top page, a hashed static file, an unknown host,
# check_release inside the web container and that the scheduler service is running.
set -euo pipefail

cd "$(dirname "$0")/../.."
host="${1:?usage: $0 <public host> [base url]}"
base="${2:-http://127.0.0.1:8000}"
failures=0

check() {
    local label="$1" expected="$2" actual="$3"
    if [ "$actual" = "$expected" ]; then
        echo "PASS $label"
    else
        echo "FAIL $label (expected $expected, got $actual)"
        failures=$((failures + 1))
    fi
}

status() { curl -s -o /dev/null -w "%{http_code}" "$@"; }

check "http redirects to https" 301 "$(status -H "Host: $host" "$base/taskle/")"
page="$(mktemp)"
trap 'rm -f "$page"' EXIT
check "top page" 200 "$(curl -s -o "$page" -w "%{http_code}" -H "Host: $host" -H "X-Forwarded-Proto: https" "$base/taskle/")"
asset="$(grep -o '/static/CSS/theme\.[0-9a-f]*\.css' "$page" | head -1 || true)"
check "hashed static file" 200 "$(status -H "Host: $host" -H "X-Forwarded-Proto: https" "$base${asset:-/static/missing}")"
check "unknown host rejected" 400 "$(status -H "Host: unknown.invalid" -H "X-Forwarded-Proto: https" "$base/taskle/")"

if docker compose exec -T web python manage.py check_release; then
    echo "PASS check_release"
else
    echo "FAIL check_release"
    failures=$((failures + 1))
fi
check "scheduler running" running "$(docker compose ps --format '{{.State}}' scheduler)"

if [ "$failures" -gt 0 ]; then
    echo "$failures check(s) failed"
    exit 1
fi
echo "All smoke checks passed"
