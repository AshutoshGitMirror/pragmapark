# Pragmapark — Bug Report

## CRITICAL: Render Free Tier OOM (Blocks Most Live Testing)

- **Symptom**: Service returns 502 Bad Gateway after ~3-5 minutes. First requests work (auth, lots listing), then service crashes.
- **Root cause**: Memory usage peaks at 487-530MB on Render free tier (512MB limit). Loading `xgboost` + `scikit-learn` + RF ensemble + pandas/numpy simultaneously exceeds the limit. Linux OOM-killer terminates the process.
- **Evidence**: Metrics show memory climbing from 2MB → 210MB (DB/deps) → 487MB (ML models) → 530MB (OOM threshold). Process restarts at ~50MB, cycle repeats.
- **Impact**: All ML-dependent routes (predict, pricing, blockchain, digital-twin, marl, micro/slots, sessions/wallet) return 502. Basic CRUD (auth, lots listing) works briefly until OOM.
- **Fix options**: 
  - A) Upgrade Render plan to `pro` ($7 → ~$25/mo, 2GB RAM) or higher
  - B) Lazy-load ML models on first request instead of at startup
  - C) Replace XGBoost with a lighter model (sklearn-only)
  - D) Use a separate Render service for ML (microservices)

---

## AUTH ISSUES

### Bug 1: `driver@test.com` login returns 401
- **Endpoint**: `POST /api/v1/auth/login`
- **Request**: `{"email": "driver@test.com", "password": "driver123"}`
- **Response**: `{"detail":"Invalid credentials"}`
- **Likely cause**: Seed data may not have this user on the deployed Postgres DB. Check `scripts/seed_data.py:51` — driver accounts include `driver@example.com`, `alice@example.com`, `bob@example.com` but NOT `driver@test.com`.

---

## LOT ID ISSUES

### Bug 2: `London01` returns 404
- **Endpoint**: `GET /api/v1/lots/London01`
- **Response**: 404 `{"detail":"Lot not found"}`
- **Likely cause**: Live Postgres DB has different lot IDs than seed script. The API lists 21 lots but lot IDs are auto-generated or use a different naming convention on the deployed DB.

---

## ML ROUTES (Blocked by OOM)

### Bug 3: All prediction/pricing routes return 502
- **Endpoints**: `POST /predict/occupancy`, `GET /predict/health`, `POST /pricing/adjust`, `GET /pricing/zones`
- **Cause**: OOM (see critical above). ML model loading at startup hits 487MB+, exceeding 512MB limit.

### Bug 4: All blockchain routes return HTML 502
- **Endpoints**: All `/blockchain/*`, `/digital-twin/*`, `/marl/*`, `/micro/*`, `/sessions/*`, `/wallet/*`
- **Cause**: OOM cascade — once memory is exhausted, all routes return 502 via Render proxy.

### Bug 5: `POST /lots (create)` returns empty 500
- **Request**: Valid `POST /api/v1/lots` with all required fields
- **No error body returned** — likely OOM-related crash during DB write

---

## TEST SCRIPT ISSUES

### Bug 6: Auth register requires 8+ char password
- **Pydantic validation**: `password` field validated with `min_length=8`
- **Fix**: Use passwords ≥8 characters in test (test script used `"test123"` which is 7 chars)

### Bug 7: Driver token retrieval fails without fallback
- **Test script** assumes `driver@test.com` exists on all deployments
- **Fix**: Create a test driver account on-the-fly via `/register` before testing driver-specific routes
