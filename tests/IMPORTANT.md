# IMPORTANT — Test Suite Reference

## Single Command: Run ALL Tests

```bash
bash run_tests.sh
```

That's it. The script handles everything:
1. Runs unit/integration tests first (no server needed, fresh DB per test)
2. Starts the API server on :8989 with a separate database
3. Runs e2e Playwright tests against the live server
4. Kills the server and reports pass/fail

No env vars to set, no flags to remember, no caveats.

## Why Unit Tests Must Run BEFORE the Server

The server has **in-memory rate limiters** that count registration/login attempts.
The e2e conftest has a `session, autouse=True` fixture (`_pre_register_users`) that
calls `/api/v1/auth/register`. If the server starts first, these calls fill the
rate-limit buckets. Unit tests (which use `TestClient(app)` in-process) then hit
429 "Too many registration attempts" errors.

**Fix:** Run unit tests first (no server), then start server with a *separate* DB
for e2e tests. This is what `run_tests.sh` does.

## Pitfalls That Were Fixed

### Module Name Collision: test_auth.py
`tests/test_auth.py` and `tests/e2e/test_auth.py` shared the module name `test_auth`.
The conftest's `sys.path.insert(0, ...)` made Python resolve `import test_auth` to
`tests/e2e/test_auth.py` at runtime, causing `import file mismatch` errors.

**Fix:** Renamed `tests/e2e/test_auth.py` → `tests/e2e/test_auth_e2e.py`.

### stress_test.py sys.exit() During Collection
`tests/stress_test.py:988` has `sys.exit(0 if FAIL == 0 else 1)` at module level.
Pytest collects it because `stress_test` matches the `*_test.py` glob.

**Fix:** `pytest.ini` sets `python_files = test_*.py` (only files starting with `test_`),
which excludes `stress_test.py`, `user_sim_test.py`, `the_people_vs_parking.py`,
and `persona_brenda.py` (they're simulation scripts, not tests).

### Tests Hanging During Collection
When the e2e conftest's `_pre_register_users` fixture tries to connect to a
server that isn't running, pytest hangs silently during collection with no
error message. This is because the fixture is `session, autouse=True` and
calls `http://127.0.0.1:8989/api/v1/auth/register`.

**Fix:** Always start the server before e2e tests (`run_tests.sh` handles this).

## What run_tests.sh Does (Step by Step)

1. **Phase 1 — Unit tests:** `unset DATABASE_URL` so conftest.py's `setdefault`
   picks a unique temp SQLite file. Runs `pytest tests/test_*.py` (only `test_`
   prefixed files — skips simulation scripts). Each test function gets a fresh
   schema via conftest's `autouse=True` fixture.

2. **Phase 2 — Start server:** Sets `DATABASE_URL` to a new temp file
   (`/tmp/e2e_test.$$.db`). Starts uvicorn on :8989. Waits up to 24s for 200 OK.

3. **Phase 3 — E2E tests:** Runs `pytest tests/e2e/` against the live server.
   Kills the server on completion (trap on EXIT).

## Files

| File | Purpose |
|------|---------|
| `run_tests.sh` | Single entry point for all tests |
| `pytest.ini` | Configures `python_files = test_*.py`, sets default flags |
| `tests/IMPORTANT.md` | This file — test suite reference for AI agents |
