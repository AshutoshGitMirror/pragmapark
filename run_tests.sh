#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────
# run_tests.sh — Run ALL tests (unit + e2e) in one command.
#
# Design:
#   Phase 1 — Unit/integration tests (no server needed).
#              Each test function gets a fresh SQLite DB via
#              conftest.py fixture; DATABASE_URL is NOT exported
#              so conftest.setdefault picks its own temp file.
#
#   Phase 2 — Start API server on :8989 with a separate DB.
#              This avoids rate-limit interference from e2e
#              session fixtures leaking into unit tests.
#
#   Phase 3 — E2E Playwright tests against the live server.
#              Kill server when done (trap on EXIT).
# ──────────────────────────────────────────────────────────

SERVER_PID=""
cleanup() {
  [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null
  echo "[run_tests] server stopped"
}
trap cleanup EXIT

FAILED=0

# ── Phase 1: Unit / integration tests ──
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Phase 1 — Unit & Integration Tests             ║"
echo "║  (no server needed, fresh DB per test function) ║"
echo "╚══════════════════════════════════════════════════╝"

# Explicitly unset so conftest.setdefault picks its own temp file
unset DATABASE_URL

PRAGMA_ENV=testing .venv/bin/python -m pytest tests/test_*.py -x --tb=short --no-header -q -p no:cacheprovider || FAILED=1

# ── Phase 2: Start server for e2e ──
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Phase 2 — Starting E2E server on :8989         ║"
echo "╚══════════════════════════════════════════════════╝"

E2E_DB="sqlite:////tmp/e2e_test.$$.db"
export DATABASE_URL="$E2E_DB"
export PRAGMA_ENV=testing

.venv/bin/python -m uvicorn src.api:app --host 0.0.0.0 --port 8989 &
SERVER_PID=$!

for i in $(seq 1 12); do
  if curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8989/ 2>/dev/null | grep -q 200; then
    echo "[run_tests] Server is up (PID=$SERVER_PID)"
    break
  fi
  sleep 2
done

# ── Phase 3: E2E tests ──
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  Phase 3 — E2E Tests                            ║"
echo "╚══════════════════════════════════════════════════╝"

PRAGMA_ENV=testing .venv/bin/python -m pytest tests/e2e/ -x --tb=short --no-header -q -p no:cacheprovider || FAILED=1

# ── Report ──
echo ""
echo "─────────────────────────────────────────────────────"
if [ "$FAILED" -eq 0 ]; then
  echo "  ALL TESTS PASSED"
else
  echo "  SOME TESTS FAILED"
  exit 1
fi
echo "─────────────────────────────────────────────────────"
