# plan.md — Repair Plan for the Pragma Repository

## Goal

Fix the repository so that the code, the docs, the demo frontpage, the legacy dashboard, and the backend all agree on the same product vision.

The product vision has six layers:

1. IoT sensor fusion
2. ML occupancy forecasting
3. Blockchain transaction recording
4. RL dynamic pricing
5. Digital twin simulation
6. Actuator control

The repo currently contains many bugs, duplicated implementations, unclear contracts, accessibility regressions, and mismatches between docs and code. This plan tells the repair agent exactly how to fix them.

## Reading rule for the agent

Treat every symbol literally.

- `X` means exactly `X`.
- `not X` means the opposite of `X`.
- A missing value means `unknown`, not the opposite.
- A fallback means fallback only.
- A demo component means demo only.
- A marketing page means marketing only.
- A dashboard means operational UI only.
- If a behavior is not proved by code, tests, or docs, do not invent it.

## Execution rule

Do the work in this order:

1. Freeze the current behavior with tests or snapshots.
2. Fix backend contracts and money/state flow.
3. Fix frontend API contracts.
4. Fix accessibility and duplicate UI scaffolding.
5. Fix documentation drift.
6. Remove dead code and repeated code.
7. Run the full verification suite.
8. Repeat until no remaining issue is explainable by a test failure, code path, or doc mismatch.

Do not make parallel speculative edits across unrelated subsystems. A route change must be followed by its client adapter, types, tests, and docs before moving on.

---

# Phase 0 — Build a reliable issue map

## 0.1 Make one issue index

Create one internal issue index with these columns:

- ID
- File path
- Line span
- Category
- Root cause
- Fix owner area
- Verification method
- Status

Every issue from the review must be assigned to exactly one category:

- backend logic
- API contract
- persistence / migration
- state machine
- pricing / prediction
- blockchain / ledger
- demo frontend
- accessibility
- duplication / DRY
- documentation / vision drift
- test gap
- deployment / config

## 0.2 Group by dependency

Sort issues in this order:

1. correctness of money and state
2. correctness of API contract
3. persistence and migration correctness
4. backend status / readiness / background jobs
5. frontend data contract correctness
6. accessibility and UX correctness
7. duplication and refactor work
8. docs and copy alignment

If one issue depends on another, fix the dependency first.

## 0.3 Freeze a baseline

Before changing code, record the current state:

- run the backend tests
- run the frontend build
- capture the existing failing tests
- record any runtime warnings
- record any type errors
- record any route schema mismatches
- record any accessibility failures you can detect automatically

The purpose of the baseline is to prove that later changes improved the repo instead of silently changing behavior.

---

# Phase 1 — Fix the backend money and state flow first

This phase is first because it affects correctness of funds, reservations, and session state. If this layer is wrong, the demo and docs do not matter.

## 1.1 Prebook flow must be atomic

File: `src/api/routes/micro/prebooks.py`

Fix the prebook flow so that reservation, wallet deduction, and record creation succeed or fail together.

Required method:

1. Validate request input before mutating state.
2. Check wallet balance before reserving the slot.
3. Reserve the slot only after wallet funds are known to be sufficient.
4. Create the prebook record only after both reservation and wallet deduction succeed.
5. Record booking fee and deposit separately.
6. Commit once, not in multiple partial steps.
7. On failure, undo reservation and undo wallet changes.
8. Do not leave any confirmed or reserved record behind after a failed request.

Cross-check:
- balance must never decrease unless the record exists
- slot reservation must never survive a rejected request
- prebook id, slot id, lot id, and user id must be saved together

## 1.2 Confirm flow must create a session or fail cleanly

File: `src/api/routes/micro/prebooks.py`

Fix both confirm branches.

Required method:

1. If confirmation succeeds, create the session.
2. If confirmation falls back to another slot, create the session for the fallback slot.
3. If session creation fails, do not mark the prebook confirmed.
4. If a refund is due, refund exactly the correct amount.
5. Do not return the original price if a fallback slot has a different price.
6. Do not use truthiness for money fields. Use explicit `is not None`.

Cross-check:
- confirmed prebook must always have a session
- confirmed fallback must use fallback slot identity and fallback price
- refund amounts must match deposit rules exactly

## 1.3 Cancel flow must release both DB and in-memory reservation state

File: `src/api/routes/micro/prebooks.py`

Required method:

1. Call the release method on the slot state engine.
2. Check the return value of the release call.
3. Update the DB record only after the state engine release succeeds.
4. If the release fails, keep the record unchanged and return an error.
5. If the refund logic runs, log the transaction.

Cross-check:
- a cancelled prebook must not remain reserved in memory
- a cancelled prebook must not remain reserved in the database
- no refund must occur twice

## 1.4 Session settlement must use the real linked prebook and lot

File: `src/api/routes/sessions.py`

Required method:

1. Link session settlement to a stable identifier.
2. Include `lot_id` in every lookup.
3. Never rely on slot index alone.
4. Settle charge and deposit against the same prebook record.
5. If actual charge is larger than deposit, handle the extra debit explicitly.
6. If actual charge is smaller than deposit, refund only the difference.
7. Do not use a page slice as a global total.

Cross-check:
- same driver plus same slot index in a different lot must never match
- deposit delta must equal deposit minus actual charge
- settlement must be idempotent

## 1.5 No-show behavior must be explicit

Files: `src/api/server.py`, `src/api/routes/micro/prebooks.py`

Required method:

1. Define no-show expiry in one place.
2. When a prebook expires, mark it as no-show or forfeited.
3. Do not label a no-show as a normal cancellation.
4. Do not refund a no-show deposit.
5. Record the exact reason in the transaction log.

Cross-check:
- no-show must not be recoverable as a normal cancel
- deposit must be forfeited only once
- state machine and DB state must agree

## 1.6 Pricing and prediction overrides must be consistent

Files: `src/micro/predictor.py`, `src/micro/pricing.py`, `src/features/engine.py`, `src/api/routes/pricing.py`

Required method:

1. Make the feature builder use one shared feature definition for train and inference.
2. Remove misleading names such as `hour_sq` when the value is not a square.
3. Keep the same feature order in training and inference.
4. Keep the same price modifier order in pricing and slot evaluation.
5. Use explicit constants for reserved and prebooked overrides.
6. Do not let a placeholder fallback hide a missing data bug.
7. For any fallback price or fallback occupancy, clearly mark the field as fallback in the response.

Cross-check:
- train and inference feature vectors must have the same fields and order
- a reserved slot override must be deliberate, not accidental
- fallback data must be labeled fallback in code and in the UI

---

# Phase 2 — Fix persistence, migrations, and background jobs

## 2.1 Make migrations truthful

Files: `alembic/versions/*`, `src/api/database.py`

Required method:

1. Keep every migration reversible if possible.
2. Do not let migration helpers silently swallow real failures.
3. If a migration changes a column width, backfill and validate the existing data.
4. If a migration adds a column used by logic, update the model and the route at the same time.
5. If a model and a migration disagree, trust the migration history and fix the model to match the actual schema.

Cross-check:
- database schema must match ORM fields
- all new fields must have default behavior defined
- old data must still load

## 2.2 Make background jobs state-safe

Files: `src/api/server.py`, `src/api/ledger_outbox.py`, `src/api/utils.py`, `src/api/workers.py`

Required method:

1. Background jobs must not mutate state without a corresponding DB record or log row.
2. If a job can run twice, it must be idempotent.
3. If a job can fail halfway, it must record the failure and leave a recoverable state.
4. Do not use a hash of lot size alone to decide whether a new ingest is needed.
5. Do not use `max(id)` when the intent is latest time.
6. Do not return a count that is only the count of the current batch.

Cross-check:
- repeated background execution must not create duplicate side effects
- one failure must not poison the next run
- job logs must be enough to reconstruct state

## 2.3 Make reservation cleanup consistent

Files: `src/micro/state_engine.py`, `src/api/utils.py`, `src/api/server.py`

Required method:

1. Use one reservation TTL rule.
2. Use one expiration clock rule.
3. Clean up both DB and in-memory state using the same criteria.
4. If one path expires a reservation, the other path must see the same result.
5. Remove any forced minimum remaining time that makes expired items look alive.

Cross-check:
- an expired reservation must look expired everywhere
- cleanup must be deterministic in tests

---

# Phase 3 — Fix API contracts and data shape drift

## 3.1 Make every route and client pair agree on the same schema

Files: `src/api/routes/*`, `demo/app/src/api/client.ts`, `demo/app/src/api/types.ts`

Required method:

1. For every backend route, write down the request schema.
2. For every frontend call, map that request schema exactly.
3. If the frontend currently invents fields, remove the invention or rename it to a derived display field.
4. If the backend expects a full request body, the frontend must send a full request body.
5. If the backend returns a count, do not replace it with a page length.
6. If the backend returns a price, do not rewrite it client-side unless the UI field is clearly marked as derived.

Cross-check:
- no client function may send a payload shape that the route does not accept
- no route may return a shape that the client type cannot represent
- generated TypeScript types must match the backend contract

## 3.2 Fix pagination semantics

Files: `src/api/routes/lots.py`, `src/api/routes/sessions.py`, `src/api/routes/payments.py`, `src/api/routes/revenue.py`, `src/api/routes/micro/slots.py`

Required method:

1. Total counts must mean total counts.
2. Page size must mean page size.
3. Current occupancy must come from the latest record over the full dataset, not the last row on a page.
4. Every paginated list must have a deterministic order.
5. Do not let an empty page mean zero capacity if the lot has capacity.

Cross-check:
- totals must stay stable when page size changes
- sorting must be deterministic across repeated calls
- page-local slicing must never change global metrics

## 3.3 Fix health and status endpoints

Files: `src/api/routes/admin.py`, `src/api/server.py`, `src/api/routes/blockchain.py`, `src/api/routes/driver.py`

Required method:

1. Health endpoints must inspect actual state.
2. Do not hardcode operational status.
3. Readiness must mean readiness for serving traffic.
4. A status endpoint must not mutate data.
5. A driver endpoint must not rely on a slot index when the engine uses a slot ID.

Cross-check:
- status should be a read-only query
- health should fail when the subsystem fails
- health should not say operational by default

---

# Phase 4 — Fix frontend demo contract, fallback data, and accessibility

The demo is a marketing frontpage. It must stay a demo. It must not lie about live state. It must also be keyboard usable and deterministic.

## 4.1 Make fallback data deterministic

Files: `demo/app/src/api/fallbackData.ts`, `demo/app/src/components/*`

Required method:

1. Remove `Math.random()` from static fallback fixtures.
2. Remove `Date.now()` from static fallback fixtures.
3. Precompute stable fallback values.
4. If some content is intentionally synthetic, label it synthetic.
5. If a value is derived from a random simulation, keep it isolated from the static demo fixture file.

Cross-check:
- reloading the demo must not change the fallback dataset unless the code changed
- screenshots must be stable across runs

## 4.2 Fix warmup and fallback state handling

Files: `demo/app/src/components/layout/WarmupContext.tsx`, `demo/app/src/components/layout/WarmupOverlay.tsx`, `demo/app/src/hooks/useApi.ts`

Required method:

1. Make the polling option actually work or delete it.
2. Make warmup state updates use current state, not stale captured state.
3. Wire the skip event to a real state transition.
4. Do not render a dead “ready” step that can never appear.
5. Do not expose callbacks that nothing calls.

Cross-check:
- the skip button must visibly change state
- the warmup overlay must disappear for the correct reason
- the hook must either poll or not advertise polling

## 4.3 Fix every clickable non-button element

Files: `demo/app/src/components/revenue/RevenueIntelligence.tsx`, `demo/app/src/components/slots/MicroSlotGrid.tsx`, `demo/app/src/components/blockchain/BlockchainLedger.tsx`, and any other interactive demo card

Required method:

1. Any clickable control must be a button or a semantic interactive element.
2. Add `role`, `tabIndex`, and keyboard handlers when a native element cannot be used.
3. Add visible or programmatic labels to form fields.
4. Make overlays and tooltips reachable by keyboard.
5. Respect reduced-motion preferences.

Cross-check:
- every click target must be operable by keyboard
- screen reader users must receive a label
- focus must be visible and logical

## 4.4 Replace repeated animation scaffolding

Files: `demo/app/src/components/*`, `demo/app/src/hooks/useScrollReveal.ts`

Required method:

1. Create one shared reveal hook or one shared reveal wrapper.
2. Use it everywhere the same `setTimeout(() => setVisible(true), 100)` pattern appears.
3. Remove component-specific copies of that pattern.
4. Preserve the visual timing, but make the code shared.

Cross-check:
- no duplicate reveal timers should remain
- reveal behavior must still look the same
- a single fix must affect all reveal sections

## 4.5 Make the demo copy truthful

Files: `demo/app/src/components/hero/Hero.tsx`, `demo/app/src/components/terminal/LiveTerminal.tsx`, `demo/app/src/components/blockchain/BlockchainLedger.tsx`, `demo/app/src/components/digital-twin/DigitalTwinSection.tsx`

Required method:

1. If data is simulated, say simulated.
2. If data is fallback, say fallback.
3. If a metric is synthetic, say synthetic.
4. Do not say “real-time” unless the value comes from the live backend path.
5. Do not say “real data” if the component is using random generation.

Cross-check:
- no marketing line may claim live truth when the code uses fallback truth
- no component may present synthetic data as operational data

## 4.6 Make the demo API client a thin adapter

Files: `demo/app/src/api/client.ts`, `demo/app/src/api/types.ts`

Required method:

1. Keep the client as a pure translator between backend schema and UI schema.
2. Do not let it invent backend fields.
3. Do not let it silently remap critical semantics.
4. If the UI wants a convenience field, derive it in a clearly named display helper.
5. Keep every request and response type aligned with the backend.

Cross-check:
- a client function should be readable as a one-to-one mapping
- no hidden transformation should change business meaning
- type changes on the backend must trigger type changes in the client

---

# Phase 5 — Fix vision drift and documentation mismatch

## 5.1 Make the docs agree with the code

Files: `README.md`, `plan.md`, `pragma-whitepaper.typ`, `demo/app/src/components/architecture/ArchitectureDiagram.tsx`

Required method:

1. Decide the single canonical architecture.
2. Make the README, whitepaper, and diagram say the same thing.
3. If a layer exists in the docs, it must exist in code or be explicitly described as planned.
4. If a layer exists in code, it must appear in the docs.

Cross-check:
- layer count must be identical everywhere
- layer names must be identical everywhere
- the actuator layer must not disappear from one doc and remain in another

## 5.2 Make the demo a marketing page, not an accidental ops console

Files: `demo/app/src/components/*`

Required method:

1. Keep the demo visually rich.
2. Keep it lightweight.
3. Do not turn it into the dashboard.
4. Do not show operational controls that can affect real state unless they are clearly mocked.
5. Do not duplicate the driver app.

Cross-check:
- marketing sections stay marketing sections
- operational sections stay read-only unless they are explicitly simulated
- the demo must not become a second dashboard

---

# Phase 6 — Remove dead code, duplicate code, and confusing code

## 6.1 Deduplicate state and render logic

Files: repeated across `demo/app/src/components/*`, `src/api/routes/*`, `src/dashboard/static/js/pragma.js`

Required method:

1. Find repeated code first.
2. Extract shared helpers second.
3. Delete duplicates last.
4. Keep the shared helper small and obvious.
5. Do not abstract so far that the code becomes harder to read.

Cross-check:
- each extracted helper must reduce duplication in at least two places
- no helper should hide business logic that needs to be visible
- shared helpers must have tests if they encode policy

## 6.2 Remove dead endpoints and dead callbacks

Files: `demo/app/src/components/layout/WarmupContext.tsx`, `src/api/server.py`, any route or component that is referenced nowhere

Required method:

1. Delete unused callbacks.
2. Delete handlers that are not reachable.
3. Delete commands that are not wired.
4. If removal is risky, mark the code deprecated and add a tracking issue first.

Cross-check:
- every exported function should have a real caller
- every route should have a real consumer or a clear reason to exist

---

# Phase 7 — Test strategy and verification gates

## 7.1 Add tests for every fixed bug class

Required test types:

- unit tests for pure helpers
- route tests for request/response shape
- integration tests for money and reservation flow
- regression tests for fallback and restart recovery
- frontend build tests for the demo
- accessibility checks for interactive demo widgets
- snapshot tests where the UI is intentionally static

## 7.2 Add explicit regression tests for the biggest bugs

These tests are mandatory:

1. prebook succeeds and balance changes correctly
2. prebook fails and leaves no reserved state
3. confirm fallback creates session and uses fallback price
4. cancel releases both DB and in-memory state
5. session settlement uses the correct lot and prebook
6. pagination totals stay constant across page sizes
7. fallback demo data stays stable across reloads
8. clickable demo widgets work with keyboard
9. architecture docs and architecture diagram agree on layer count
10. the frontend API client can call every backend route it claims to call

## 7.3 Verification commands

Use the repo’s own scripts first.

- Backend: run `./run_tests.sh`
- Frontend demo: run `npm run build` inside `demo/app`
- If lint scripts exist, run them too
- If typecheck scripts exist, run them too
- If accessibility tooling exists, run it on the demo
- If formatting tools exist, run them after the code is stable

Do not mark any phase complete until the verification step is green.

---

# Phase 8 — Acceptance criteria

The repo is done only when all of the following are true:

1. Prebook, confirm, cancel, and session settlement are correct and test-covered.
2. Wallet changes match the documented deposit model.
3. Backend routes and frontend client types agree.
4. Pagination totals and current metrics are correct.
5. Demo fallback data is deterministic.
6. Demo interactive controls are keyboard accessible.
7. Demo copy does not claim live truth when the data is fallback or synthetic.
8. The architecture in README, whitepaper, and diagram is identical.
9. Duplicate animation and reveal scaffolding is removed.
10. No route or component relies on a hidden assumption that is not written in code or tests.
11. Every major issue class from the audit has either been fixed or explicitly reclassified as intentional design.
12. The full verification suite passes.

---

# Change order the agent must follow

Use this order for actual edits:

1. fix DB/schema and backend money flow
2. fix backend state machines
3. fix API contracts
4. fix demo fallback data
5. fix accessibility
6. remove duplicate UI patterns
7. fix docs
8. run verification
9. repeat only if verification finds more issues

Do not start with refactors. Do not start with docs. Do not start with visual polish. Correctness first.

---

# Appendix A — Issue-by-issue remediation map

Use this appendix as the exact work queue. Fix the items in order. Do not skip ahead. Do not merge unrelated items unless the shared code path is the same.

Format per item:

- What to change
- Why it is wrong
- How to verify the fix

## Backend and API issues

1. **Prebook modifiers use an empty slot list** — Pass the real slot list into `compute_modifiers`. Why: empty input makes ranking ignore the request context. Verify: a test with two different slot sets produces different modifiers.
2. **Prebook id is truncated too aggressively** — Use the full UUID or a database-generated primary key. Why: 16 hex characters are a needless collision risk. Verify: uniqueness test over many generated ids.
3. **Every prebook gets `ranked_order=0`** — Store the real rank from the scoring step. Why: a constant rank makes fallback ordering meaningless. Verify: ordered fallback selection changes when scores change.
4. **Slot is reserved before wallet validation** — Validate funds before mutating slot state. Why: rejected requests must not leave reserved state behind. Verify: failed prebook leaves no DB row and no in-memory reservation.
5. **Timezone handling is stripped during prebook** — Keep timezone-aware datetimes end to end. Why: naive timestamps can shift the booking window. Verify: a time zone regression test compares before and after.
6. **Epoch time is mixed with monotonic time** — Use one clock family inside the state engine. Why: mixed clocks break restart recovery. Verify: restart recovery works after a controlled time shift.
7. **Recovery converts naive datetime with `timestamp()`** — Normalize the datetime before conversion. Why: naive timestamps are ambiguous and locale-dependent. Verify: recovery behaves the same in UTC and local time tests.
8. **Confirm branch marks confirmed before session creation** — Create the session first, then mark confirmed only after success. Why: confirmed state without a session is broken settlement state. Verify: session creation failure leaves the prebook unconfirmed.
9. **Fallback confirmation does not create a session** — Call the same session creation path used by the normal confirm branch. Why: fallback confirmation must produce a real session. Verify: fallback confirm returns a real session id.
10. **Fallback price is not used in fallback confirmation** — Return the fallback slot price, not the original slot price. Why: pricing must match the slot that was actually booked. Verify: fallback slot with different price returns the fallback amount.
11. **Refund and no-show states are collapsed** — Give refund, cancel, and no-show separate states. Why: these are different business events. Verify: each path writes a distinct status row.
12. **A failed confirmation can still leave a confirmed record** — Wrap the whole confirm flow in one transaction or compensating rollback. Why: partial success is unsafe for money state. Verify: induced session failure leaves no confirmed record.
13. **List prebooks performs repeated slot and lot lookups** — Prefetch the joined data in one query. Why: repeated lookups are slow and noisy. Verify: query count drops in a route test.
14. **Truthiness is used for numeric response fields** — Use explicit `is not None` checks. Why: zero is a valid value, not missing data. Verify: zero-valued fields survive the response.
15. **Cancel ignores the release return value** — Check the release call and abort on failure. Why: DB and in-memory state must not diverge. Verify: a forced release failure keeps the prebook unchanged.
16. **Cancel can refund twice if retried** — Add idempotency to the cancel path. Why: repeated requests must not double-pay. Verify: two cancel calls produce one refund.
17. **Session lookup ignores `lot_id`** — Include the lot in every settlement lookup. Why: same slot index in another lot is not the same booking. Verify: two lots with same slot index never collide.
18. **Session settlement has no debit path for overcharge** — Add an explicit debit or settlement rule for charge above deposit. Why: money flow must balance in both directions. Verify: overcharge test records the extra charge.
19. **Session settlement uses page-local state** — Link settlement to stable ids only. Why: page slices are presentation data, not business identity. Verify: pagination changes do not affect settlement.
20. **Session settlement mixes mutation and outbox work** — Move settlement orchestration into a service layer. Why: route handlers should be thin. Verify: route tests still pass after the orchestration is extracted.
21. **Sessions API returns page length as total count** — Return a real total query count. Why: totals must not change when page size changes. Verify: total stays stable across different page sizes.
22. **Payments API returns page length as total count** — Compute total count independently from the page slice. Why: page size is not a total. Verify: totals remain constant across pagination.
23. **Lots API uses current page to compute current occupancy** — Compute current occupancy from the latest whole-dataset record. Why: page-local data can mislead. Verify: changing page number does not change current occupancy.
24. **Lots list queries have no deterministic order** — Add an explicit `order_by`. Why: pagination without sorting is unstable. Verify: repeated calls return the same order.
25. **Lot update does not reconcile active state** — After config changes, rebuild dependent derived state. Why: changing slot count without reconciliation causes drift. Verify: active sessions still map to valid slots.
26. **Revenue average divides by row count, not days** — Group by day first, then average. Why: multiple records per day distort the metric. Verify: a two-row single-day fixture gives the right average.
27. **Revenue truncates rows silently at 1000** — Expose pagination or a warning. Why: silent truncation hides data loss. Verify: the API reports that results were truncated.
28. **Revenue counts all users as drivers** — Filter by role. Why: admin and owner rows are not drivers. Verify: role mix fixture returns only drivers in the count.
29. **Blockchain tx hash is derived from pending length** — Use a real unique id or hash of immutable content plus nonce. Why: list length is not unique. Verify: repeated submissions do not collide.
30. **Blockchain route is too open** — Restrict status and pool endpoints to the intended role set. Why: operational state should not be broadly exposed. Verify: a non-authorized role gets a rejected response.
31. **Admin health labels every subsystem operational** — Probe each subsystem or remove the label. Why: a hardcoded health response is not health. Verify: forced subsystem failure flips the response.
32. **Admin system occupancy is a single latest row** — Compute an aggregate occupancy metric. Why: one row is not the system. Verify: multiple lot data changes the metric predictably.
33. **Auth register forces the driver role only** — Route role selection through explicit admin or invite flows. Why: role creation must match the intended onboarding flow. Verify: non-driver roles cannot be created accidentally.
34. **Auth rate limits are process-local only** — Back them with shared storage or document the limitation. Why: process-local limits reset on restart and scale badly. Verify: two workers enforce the same limit.
35. **Logout blacklist uses TTL not token lifetime** — Store the actual remaining token expiry. Why: revocation windows should be exact. Verify: a revoked token stays revoked for its real remaining lifetime.
36. **Get-me repeats the DB lookup already done by auth** — Return the auth-resolved user object when available. Why: duplicated lookups waste work. Verify: one request performs one user query.
37. **Migration helper swallows Alembic failures** — Fail hard unless a fallback is explicitly approved. Why: silent migration failures hide schema drift. Verify: an induced migration error stops startup.
38. **Schema width mismatch for lot id** — Align the column width with the actual identifier length used by the app. Why: truncation breaks audit rows. Verify: a long lot id round-trips unchanged.
39. **Latest occupancy uses `max(id)` instead of latest time** — Sort by timestamp or updated_at. Why: backfilled rows can become the wrong “latest”. Verify: a backfill test still returns the newest timestamp.
40. **Reservation cleanup uses inconsistent clocks** — Use one TTL source for DB and in-memory cleanup. Why: expired items must look expired everywhere. Verify: expiry tests pass in one place and fail in another only if expected.
41. **In-memory rate limiter is not shared** — Move it behind a shared store or mark it dev only. Why: multi-worker deployments bypass process-local limits. Verify: two workers enforce one global limit.
42. **Periodic ingest uses structural hash only** — Include actual freshness or occupancy changes in the dedupe key. Why: real updates can stop flowing. Verify: occupancy changes create new ingest rows.
43. **Background loop has no graceful stop path** — Add cancellation handling. Why: unhandled shutdown makes jobs flaky. Verify: stop and restart without orphan tasks.
44. **Outbox count returns pending length, not processed length** — Return separate processed and skipped counts. Why: metrics must report truth, not a batch size. Verify: processed count matches the actual delivery count.
45. **Outbox rollback can discard progress silently** — Make flush retry and failure handling explicit. Why: partial success needs visible recovery. Verify: retry test resumes from the failed item.
46. **No-show handling is not explicit enough** — Split no-show, cancel, and expiry states. Why: each event has different money behavior. Verify: each event produces the right ledger row.
47. **Wallet top-up creates balance changes without a transaction row** — Write a transaction record for every balance mutation. Why: balance without ledger is not auditable. Verify: every top-up has a matching row.
48. **Wallet balance lookup assumes one user id shape** — Normalize the token payload and user object id fields. Why: shape drift can break balance queries. Verify: both token formats resolve to the same user.
49. **Ingestion divides by `max(total_slots, 1)`** — Reject invalid zero-slot input instead of masking it. Why: invalid config should fail, not be hidden. Verify: zero-slot input returns a validation error.
50. **Ingestion silently reuses the last price** — Make the reuse rule explicit or remove it. Why: hidden carry-forward rules hide data bugs. Verify: stale price use is observable in tests.
51. **Driver lot availability uses hardcoded fallback occupancy** — Return a labeled fallback value or an error. Why: fake occupancy can mislead users. Verify: missing data path is clearly labeled.
52. **Driver slot count uses slot index instead of slot id** — Query by the engine’s real key. Why: the wrong key returns the wrong state. Verify: a test with same index in different lots passes.
53. **Pricing route hardcodes default zone data** — Look up the actual zone or return a controlled error. Why: fake defaults hide data bugs. Verify: missing zone fails loudly.
54. **Digital twin route ignores pipeline state** — Pull from the real pipeline snapshot first. Why: simulation should be tied to actual state when possible. Verify: changing pipeline inputs changes the result.
55. **MARL training uses random capacities each time** — Use seeded or persisted training data. Why: training must be reproducible. Verify: the same seed returns the same training output.
56. **MARL training is only in memory** — Persist the trained artifact or document it as ephemeral demo-only behavior. Why: restart should not erase claimed training. Verify: restart behavior matches the documented design.
57. **Prediction route uses synthetic fallback data too freely** — Mark fallback outputs as fallback in the response. Why: users must know whether the number is real or simulated. Verify: fallback path is visibly labeled.
58. **Feature builder input shape differs between train and inference** — Share one feature definition object. Why: train and inference must not drift. Verify: both code paths produce the same ordered feature list.
59. **`hour_sq` is a misleading feature name** — Rename it to its real meaning. Why: names should match values. Verify: tests and docs use the same term.
60. **Prediction overrides for reserved and prebooked slots are blunt** — Put the override values behind named constants and tests. Why: implicit magic numbers are hard to audit. Verify: override behavior is covered by tests.
61. **Blockchain ledger validation is too shallow** — Validate transaction schema and chain continuity. Why: ledger status without schema checks is weak. Verify: malformed block data fails validation.
62. **Mining copies pending transactions without locking** — Protect the pending queue or use a transactional snapshot. Why: concurrent mutation can corrupt the block contents. Verify: concurrent mine tests do not lose transactions.
63. **Genesis block timestamp is wall-clock dependent** — Make genesis deterministic in tests. Why: chain identity should not drift on every run. Verify: repeated test runs get the same genesis hash.
64. **IPFS content ids are truncated too much** — Use the full content id or a collision-resistant reference. Why: truncated ids collide more easily. Verify: repeated content never maps to different objects.
65. **IPFS eviction is blind to pin status** — Never evict pinned objects. Why: pinned data must stay pinned. Verify: pinned items survive eviction.
66. **Session service mixes business rules and transport work** — Move pricing and settlement into smaller service helpers. Why: route code becomes impossible to reason about when it does everything. Verify: helper unit tests cover the extracted logic.
67. **Session service outbox payload can disagree with response** — Build payload and response from one canonical result object. Why: response drift confuses clients. Verify: payload and response fields match exactly.
68. **Session service stale-session cleanup is age-only** — Use lifecycle state as well as age. Why: age alone can cancel the wrong session. Verify: fresh active sessions stay active.
69. **Lot summary helpers use the wrong fallback occupancy defaults** — Standardize fallback values in one helper. Why: the app should not invent different defaults in different places. Verify: all endpoints return the same fallback policy.
70. **Current occupancy defaults differ across modules** — Choose one fallback policy or one error policy. Why: inconsistent defaults cause contradictory dashboards. Verify: the same missing data gives the same outcome everywhere.

## Demo frontend issues

71. **Fallback demo data is randomized** — Replace randomness with fixed fixtures. Why: static demo data must not change on reload. Verify: screenshots are stable across refreshes.
72. **Fallback data uses current time at module load** — Remove `Date.now()` from static fixtures. Why: static demo data should be reproducible. Verify: two loads produce the same values.
73. **Polling option is advertised but ignored** — Implement polling or remove the option. Why: the hook must not promise behavior it does not deliver. Verify: poll interval changes cause visible refreshes.
74. **Warmup state uses stale captured values** — Read the latest state inside the effect. Why: stale closures make the waiting message wrong. Verify: elapsed text updates every second.
75. **Warmup skip event is not wired to a real transition** — Connect the event to the provider state. Why: a dead button is misleading. Verify: the button hides the overlay.
76. **Warmup ready step can never appear** — Remove the dead step or make it visible before unmount. Why: unreachable UI is confusing. Verify: the ready state is either visible or removed.
77. **Hero hardcodes the live backend URL** — Read it from configuration. Why: hardcoding breaks deployment portability. Verify: env override changes the target.
78. **Hero copy claims live truth during fallback** — Label fallback content as fallback. Why: marketing copy must not lie about data source. Verify: simulated mode shows simulated labels.
79. **Metric ticker numbers are hardcoded** — Drive them from real state or derived demo fixtures. Why: static numbers drift from the rest of the page. Verify: metric changes follow the underlying source.
80. **Three-globe animation ignores reduced motion** — Add a reduced-motion path. Why: motion-sensitive users need a calmer path. Verify: reduced-motion mode disables animation.
81. **Animated sections duplicate the same reveal timer** — Centralize the reveal logic. Why: copy-paste animation code causes drift. Verify: one change updates all sections.
82. **Blockchain ledger uses random blocks and hashes** — Decide whether it is a simulator and label it as such. Why: random operational-looking data is misleading. Verify: the simulator label is visible.
83. **Blockchain ledger inputs have placeholders only** — Add visible labels. Why: placeholders are not accessible labels. Verify: screen readers announce the fields.
84. **Revenue heatmap cells are clickable divs** — Use buttons or add full keyboard semantics. Why: pointer-only widgets exclude keyboard users. Verify: Enter and Space activate cells.
85. **Slot grid cells are clickable divs** — Same fix as the heatmap. Why: a grid must be operable by keyboard. Verify: focus order and activation work.
86. **Testimonials auto-rotate without user control** — Add pause, stop, or manual controls. Why: auto-rotating content can distract and trap attention. Verify: rotation can be stopped.
87. **Live terminal is synthetic but labeled live** — Change the copy or the implementation. Why: the UI should match the data source. Verify: the label matches the source.
88. **Footer links use `#`** — Replace with real targets or remove them. Why: fake links are broken affordances. Verify: every link goes somewhere meaningful.
89. **Digital twin section uses random scenario output** — Make simulation deterministic or label it clearly as generated. Why: users need to know what is simulated. Verify: the same input gives the same output.
90. **Prediction engine hardcodes headline metrics** — Derive them from the data source or label them as sample metrics. Why: fake metrics become stale. Verify: metric updates are data-driven.
91. **Demo client remaps session counts into transaction counts** — Keep semantics explicit in the adapter. Why: renamed fields need clear names. Verify: field names and labels match the source.
92. **Demo client remaps users to drivers** — Expose derived display fields only when clearly named. Why: a projection is not the same as a raw count. Verify: the UI label says what the value really is.
93. **Demo client invents a single pricing zone object** — Preserve the backend list shape. Why: collapsed shapes hide real API structure. Verify: multiple zones can render without code changes.
94. **Demo client sends the wrong scenario payload** — Match the backend request schema exactly. Why: contract mismatch breaks the route. Verify: route tests accept the client payload.
95. **Demo client sends no MARL training body** — Send the required training request fields. Why: empty payloads break the route contract. Verify: the backend accepts the client request.
96. **Demo client hardcodes the admin demo account** — Route login through config or fixture auth only. Why: credentials should not be buried in the UI adapter. Verify: swapping the fixture updates the login path.
97. **Interactive cards are not keyboard reachable** — Add focus, role, and keyboard handlers. Why: accessibility requires more than click handlers. Verify: Tab reaches every interactive card.
98. **Some inputs have no visible labels** — Add labels or accessible name attributes. Why: labels are required for form usability. Verify: screen reader reads the correct field name.
99. **The demo relies on random geometry and random logs** — Freeze demo-mode randomness or isolate it under a clearly marked simulator toggle. Why: demo screenshots should be repeatable. Verify: two loads match.
100. **The demo presents fallback and live data without a clear boundary** — Add explicit live/fallback banners. Why: users should know the source of truth. Verify: source is visible in the UI.

## Dashboard, docs, scripts, and build issues

101. **Legacy dashboard is a monolithic JavaScript file** — Split it into smaller modules. Why: one huge file is impossible to maintain. Verify: shared helpers reduce file size and duplication.
102. **Legacy dashboard uses raw `innerHTML` broadly** — Replace it with safer rendering helpers. Why: raw HTML sinks are fragile and hard to audit. Verify: rendered output still matches and tests stay green.
103. **Legacy dashboard repeats demo UI behavior** — Keep the dashboard operational and the demo marketing-only. Why: the two surfaces should not drift into the same role. Verify: each surface has different responsibilities.
104. **Legacy dashboard and demo both implement reveal logic independently** — Centralize the reveal pattern. Why: duplicate animation logic creates drift. Verify: one helper powers both surfaces if they must stay separate.
105. **Legacy templates use fake links** — Replace `#` anchors with real navigation or remove them. Why: broken navigation is misleading. Verify: every nav action changes state or location.
106. **Legacy driver template lacks accessible labels** — Add labels and keyboard flow. Why: form controls need names. Verify: keyboard navigation works.
107. **App.py introduces a third UI surface** — Decide whether it is still needed. Why: extra surfaces increase maintenance cost and drift. Verify: only approved surfaces remain reachable.
108. **Readme and whitepaper disagree on layer count** — Make one canonical architecture statement. Why: docs must not conflict. Verify: all docs show the same layer count.
109. **Architecture diagram differs from the written docs** — Update the diagram or the prose, not both separately. Why: mixed stories confuse maintainers. Verify: the diagram and prose say the same thing.
110. **Whitepaper and code disagree on actuator semantics** — Align the implementation or explicitly mark actuator as planned. Why: the declared product vision must match reality. Verify: the code path or the doc changes together.
111. **Plan document claims completion too early** — Keep the plan in sync with the actual fix status. Why: a repair plan must not overstate completion. Verify: statuses are updated when tests pass.
112. **Generated notebook script is not production-ready** — Treat it as a utility or rewrite it cleanly. Why: notebook output is not maintainable application code. Verify: production paths do not depend on notebook magic.
113. **Data download script has no timeout or checksum check** — Add both. Why: external downloads must be validated. Verify: corrupted downloads fail.
114. **Micro seeding script is nondeterministic** — Add a seed parameter and default it. Why: repeatable seeding is required for debugging. Verify: two runs with the same seed match.
115. **Repo has three overlapping UI paths** — Keep demo, dashboard, and driver role boundaries explicit. Why: overlapping surfaces create design drift. Verify: each surface has its own contract and purpose.
116. **Money and reservation logic is spread across routes** — Move it into one service layer. Why: one business rule should have one home. Verify: route tests still pass after extraction.
117. **Fallback data is used as a silent substitute for backend failure** — Label fallback or fail visibly. Why: silent substitution makes bugs invisible. Verify: fallback is obvious in both code and UI.
118. **Several metrics are page-local instead of global** — Recompute them on the full dataset. Why: page slices are not a business source of truth. Verify: changing page size does not change totals.
119. **Several routes return presentation values instead of raw data** — Separate raw API data from UI transformations. Why: raw data should stay raw. Verify: client-side transformations are clearly named.
120. **Several endpoints silently default to fake values** — Replace fake defaults with explicit errors or explicit fallback labels. Why: silent fakes hide broken data paths. Verify: missing data is visible in tests.
121. **Some route handlers are too large** — Split them into smaller service functions. Why: large handlers hide bugs. Verify: each service function gets its own unit test.
122. **Some background jobs are not idempotent** — Add idempotency keys and duplicate checks. Why: background jobs can retry. Verify: repeated execution does not duplicate state.
123. **Some DB lookups use the wrong sort key** — Sort by the time column you actually mean. Why: id order is not the same as event time. Verify: backfilled rows still sort correctly.
124. **Some UI sections say “live” while using generated data** — Change the copy or the source. Why: truthfulness matters on the landing page. Verify: the label matches the data path.
125. **Some UI components cannot be paused or skipped** — Add controls for motion and auto-advance. Why: motion-heavy pages need user control. Verify: users can stop the motion.
126. **Some API clients send payloads that backend routes do not accept** — Align request bodies with route schemas. Why: contract mismatch breaks the whole feature. Verify: request validation passes end to end.
127. **Some counts are named like totals but are only page counts** — Rename or recompute them. Why: names must match the meaning. Verify: values stay stable across pagination.
128. **Some fallback values are returned as if they were truth** — Add a `source` or `is_fallback` flag. Why: derived data must be labeled. Verify: the UI shows the source.
129. **Some fields are inferred with truthiness instead of explicit checks** — Use explicit zero-safe checks. Why: zero is a valid value. Verify: zero survives all response paths.
130. **Some code paths create state before validation** — Reverse the order. Why: validation must happen first. Verify: rejected input leaves no new state.
131. **Some code paths commit before all side effects succeed** — Move commit to the end or use a compensating transaction design. Why: partial commits are unsafe. Verify: induced failures roll back cleanly.
132. **Some code paths mix business logic and response shaping** — Separate data mutation from presentation formatting. Why: clearer code is easier to test. Verify: pure helpers can be unit tested.
133. **Some code paths mix real and synthetic state** — Keep them in different modules or clearly label the synthetic path. Why: mixed state is hard to reason about. Verify: synthetic outputs are visibly synthetic.
134. **Some code paths overuse hardcoded constants** — Promote them to named config values. Why: hardcoded values are easy to miss and hard to change. Verify: config changes propagate predictably.
135. **Some code paths have copy-paste text labels** — Replace them with shared constants. Why: copy-paste causes drift. Verify: one label change updates every surface.
136. **Some code paths have dead branches that can never run** — Remove them. Why: dead branches confuse future readers. Verify: coverage no longer needs the dead branch.
137. **Some code paths lack tests for failure cases** — Add failure tests first. Why: the failures are the real bugs. Verify: each failure path has a regression test.
138. **Some code paths lack tests for restart recovery** — Add explicit restart and rehydrate tests. Why: the app depends on persistence and recovery. Verify: restart tests reproduce the issue and the fix.
139. **Some code paths lack tests for keyboard access** — Add keyboard navigation tests. Why: accessibility is a functional requirement. Verify: every click target also works from the keyboard.
140. **Some code paths lack tests for data truthfulness** — Add copy and source assertions where appropriate. Why: the marketing page must not claim live truth for synthetic data. Verify: fallback labels are present.
141. **Some code paths lack tests for deterministic demo rendering** — Add snapshot tests or stable-value tests. Why: demo pages should not drift unpredictably. Verify: repeated renders produce the same snapshot.
142. **Some code paths lack tests for API schema shape** — Add request and response contract tests. Why: client and server must agree. Verify: the generated client matches the backend schema.
143. **Some code paths lack tests for pagination totals** — Add page-size invariance tests. Why: totals should not change when page size changes. Verify: totals stay stable across page sizes.
144. **Some code paths lack tests for settlement correctness** — Add deposit and refund tests. Why: money flow must be exact. Verify: positive, zero, and negative deltas are all handled.
145. **Some code paths lack tests for collision resistance** — Add id generation tests. Why: short ids and count-based hashes collide. Verify: generated ids do not repeat in a stress test.
146. **Some code paths lack tests for predictable ordering** — Add sorting tests. Why: pagination and summaries need stable order. Verify: the same dataset returns the same order every time.
147. **Some code paths lack tests for explicit role rules** — Add authorization tests. Why: role boundaries matter. Verify: driver, admin, and demo roles behave differently.
148. **Some code paths lack tests for fallback labeling** — Add tests that assert `fallback` is visible in the payload or UI. Why: unlabeled fallback looks real. Verify: the label is present.
149. **Some code paths lack tests for no-show state** — Add a dedicated no-show test. Why: no-show is not the same as cancel. Verify: no-show gets the correct refund behavior.
150. **Some code paths lack tests for de-duplication of repeated UI state** — Add component-level tests around the shared reveal helper. Why: one refactor should cover all repeated cases. Verify: all affected components still render correctly.

## Final execution notes

151. Fix money and reservation logic before anything else.
152. Fix contract mismatches before visual refactors.
153. Fix accessibility before cosmetic animation work.
154. Fix deterministic demo data before screenshots or demos.
155. Fix docs after the code is stable enough to describe.
156. Do not add new abstractions unless they remove real duplication.
157. Do not rename live truth into fallback truth.
158. Do not hide failure behind random data.
159. Do not leave a route, component, or script in a state where it claims more than the code does.
160. After each cluster of changes, run the exact verification for that cluster.
161. If a verification fails, stop and fix the root cause first.
162. If a fix touches both backend and frontend, update both in the same change set.
163. If a fix touches docs, update docs only after code and tests are green.
164. If a helper is shared, give it tests.
165. If a value matters for money, make it explicit, named, and test-covered.
166. If a value matters for accessibility, make it semantic, labeled, and keyboard-safe.
167. If a value matters for truthfulness, label the source in the UI and in the response.
168. If a value matters for recovery, store enough information to reconstruct state after restart.
169. If a value matters for ordering, sort it explicitly.
170. If a value matters for totals, compute it on the full dataset, not on the current page.
171. If a value matters for identity, do not derive it from counts or slice lengths.
172. If a value is synthetic, say synthetic.
173. If a value is fallback, say fallback.
174. If a value is live, prove it from the backend path.
175. If a value is derived, name it as derived.
176. If a path can fail halfway, make the rollback behavior explicit.
177. If a path can retry, make it idempotent.
178. If a path is shared by demo and dashboard, separate the presentation from the business rule.
179. If a path is only for the demo, keep it visibly demo-only.
180. If a path is only for the dashboard, keep it operational and not marketing-heavy.
181. If a path is only for the driver app, keep it driver-specific.
182. If a file is dead, delete it.
183. If a branch is unreachable, delete it.
184. If a helper is duplicated, centralize it.
185. If a constant is magic, name it.
186. If a label is misleading, rename it.
187. If a status endpoint lies, make it real.
188. If a UI control cannot be used with a keyboard, fix it.
189. If a fallback path is silently pretending to be live, make it explicit.
190. If the docs and code disagree, the code wins until the docs are updated.
191. If a test cannot prove the bug is fixed, add the test.
192. If a fix can be made with one small service helper, prefer that over a large rewrite.
193. If a refactor does not remove duplication or drift, do not do it yet.
194. If a change affects payment, reservation, or settlement, manually inspect the diff after the test passes.
195. If a change affects demo truthfulness, inspect the rendered page after the test passes.
196. If a change affects accessibility, inspect the keyboard path after the test passes.
197. If a change affects contracts, inspect both request and response types after the test passes.
198. If a change affects persistence, inspect the restart path after the test passes.
199. If a change affects ordering or totals, inspect the full dataset behavior after the test passes.
200. The repair is complete only when the code, the docs, the demo, and the tests all tell the same story.

