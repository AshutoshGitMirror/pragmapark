# Bugs Tracked During Testing

## P0 — Prebook `expires_at` Missing `Z` Suffix → Shows "Expired" Immediately
- [FIXED] API returned naive ISO datetime without timezone → browser `new Date()` parses as local time, shifts back, shows "Expired"
- Fix: Append `+ "Z"` to `isoformat()` calls in prebooks.py:135, reservations.py:76
- Also added to `/prebooks/list` endpoint via `z()` helper
- Deployed & verified: prebook shows "Active" badge, correct time

## P0 — Cancel Button Silent (No API Call)
- [FIXED] Cancel button only removes from sessionStorage cache, never called `/api/v1/micro/cancel`
- Fix: `cancelPrebookBooking()` now calls cancel API before removing from cache
- Deployed

## P0 — No GET Endpoint for Prebooks (Reload Loses Prebooks)
- [FIXED] `loadBookings()` only read from `sessionStorage("pragma_prebooks")`
- Fix: Added `GET /api/v1/micro/prebooks/list` endpoint + frontend tries API first
- Deployed & verified: page reload now shows prebook from server

## P0 — UI Ignores Server Status, Shows "Active" for Unavailable/Cancelled Prebooks
- [FIXED] `loadBookings()` rendered badge based only on time (`remaining <= 0`), ignored `pb.status`
- UI showed "Active" badge + "I'm Here Now" button for `status: "unavailable"` prebooks
- Fix: Badge text comes from `pb.status`, action buttons only show when `pb.status === "active"`
- Deployed

## P0 — In-Memory Slot State Lost on Server Restart (Deploy) → Confirm Fails 409
- [FIXED] `slot_state_engine` is in-memory dict, wiped on every Render deploy
- When user clicks "I'm Here Now", `confirm_prebook()` returns False because engine doesn't track the slot
- Fallback logic refunded deposit + returned 409 instead of confirming
- Fix: In confirm endpoint, if `confirm_prebook` fails, check if engine lost state → re-prebook the slot via `slot_state_engine.prebook()`, then retry `confirm_prebook()`
- Deployed

## P1 — Prebook `target_time` Also Returns Without `Z` Suffix
- [FIXED] Same root cause as `expires_at` — fixed in `/prebooks/list` endpoint via `z()` helper
- Deployed

## P1 — List API Returns `lot_id` Not `lot_name` (Minor)
- UI shows "DB1" instead of "Dubai Mall Lot" in booking card
- Fix: Would need to join lot name in query or add fallback
- Not critical — `lot_id` like "DB1" is still recognizable

## P2 — Speed Simulation Buttons Disappeared (1x/10x/60x)
- Noticed on reload: buttons "1x", "10x", "60x" missing from header
- Likely in the session/active screen — only visible when session is running
- Still present as "14" button (snapshot speed)

## P2 — Booking Fee ($2) Not Refunded on Unavailable Prebook → User Lost Money
- Expected behavior per design: booking fee is non-refundable admin fee
- Deposit ($40) correctly refunded on failed confirm
- Balance: $1000 → $958 (fee+deposit) → $998 (deposit refund) = $2 fee kept

## P2 — Admin Page 404
- `/admin` returns 404 — different URL path needed

## P2 — Seed Driver Passwords May Not Survive Redeploy
- `driver{1-5}@demo.io` / `demo123` — DB seeded on `create_all()`, survives redeploy if SQLite file persists
- On Render free tier, filesystem is ephemeral → seed data lost on restart

## P2 — Prebook Deposit Not Refunded on Session End (Grace Period)
- When prebook is confirmed → session starts → ended within grace period ($0 fee), the prebook deposit ($25) is NOT refunded
- User loses deposit + booking fee ($27 total) for a free session
- Root cause: end session endpoint doesn't trigger prebook deposit refund
- Fix: On session end, if session amount_charged is $0 and prebook exists, refund deposit (minus admin fee)

## P2 — Session Receipt Shows Slot #0 Instead of Proper Slot Label
- After confirming prebook for Slot A1, receipt shows "Slot #0"
- However, `slot_index` in the prebook response was correct (used in slot_state_engine)
- Likely a separate code path in session creation that uses a different slot index
- Minor display issue

## P2 — Speed Simulation Buttons (1x/10x/60x) Not Visible on Find Screen
- Only "14" speed button shows in header
- 1x/10x/60x buttons might only appear when session is active
- Or they're hidden in the a11y tree due to rendering
