# Option D: Wallet Deduction Implementation - COMPLETED

## Chosen Model: Deposit + Auto-Refund

### When Money Moves

| Event | Action | Amount |
|-------|--------|--------|
| Prebook | Charge booking fee (non-refundable) + refundable deposit | $2 fee + `base_price × 1hr` deposit |
| Confirm (prediction fail) | Auto-refund deposit | Full deposit back |
| Session end | Settle actual, refund delta | `charge = final_price × hours`, refund `deposit - charge` |
| Early cancel | Refund deposit minus admin fee | `deposit × (1 - ADMIN_FEE_RATE)` |
| No-show | Forfeit deposit | $0 refund |

### Implementation Tasks - COMPLETED

1. **Add constants** to `src/constants.py`:
   - `BOOKING_FEE = 2.0` (non-refundable)
   - `DEPOSIT_RATE = 1.0` (1 hour of base price as deposit)
   - `ADMIN_FEE_RATE = 0.1` (10% admin fee on early cancel)
   - `TX_ACTION_DEPOSIT = "deposit"`
   - `TX_ACTION_BOOKING_FEE = "booking_fee"`

2. **Modify `PrebookRecord`** in `src/api/database.py`:
   - Added `booking_fee` column (Float, default=0.0)
   - Added `deposit` column (Float, default=0.0)
   - Added `deposit_refunded` column (Integer, default=0)

3. **Modify prebook endpoint** (`src/api/routes/micro/prebooks.py`):
   - Check wallet balance ≥ `BOOKING_FEE + deposit`
   - Deduct `BOOKING_FEE` + `deposit` from balance
   - Store amounts in `PrebookRecord`
   - Record transactions for booking fee and deposit

4. **Modify confirm endpoint** (`src/api/routes/micro/prebooks.py`):
   - On prediction failure (no fallback): refund deposit
   - Log refund as `TX_ACTION_REFUND`

5. **Modify session end** (`src/api/routes/sessions.py`):
   - Calculate `charge = final_price × duration_hours`
   - If prebook existed: refund `deposit - charge` (if positive)
   - Log settlement

6. **Add no-show penalty** in `src/api/server.py`:
   - When prebook expires: forfeit deposit (no refund)
   - Log as no-show penalty

7. **Add early cancel refund** in cancel endpoint:
   - Refund `deposit × (1 - ADMIN_FEE_RATE)`
   - Log refund

### Files Modified

| File | Change |
|------|--------|
| `src/constants.py` | Added BOOKING_FEE, DEPOSIT_RATE, ADMIN_FEE_RATE, TX_ACTION_DEPOSIT, TX_ACTION_BOOKING_FEE |
| `src/api/database.py` | Added booking_fee, deposit, deposit_refunded to PrebookRecord |
| `src/api/routes/micro/prebooks.py` | Added wallet check + deduction on prebook, refund on confirm fail, cancel endpoint |
| `src/api/routes/sessions.py` | Added settlement + refund on session end |
| `src/api/server.py` | Added no-show penalty in _log_slot_transition |

### Testing Checklist

- [x] Prebook charges wallet (balance decreases by fee + deposit)
- [x] Prebook fails if insufficient balance
- [x] Confirm fail refunds deposit (balance increases)
- [x] Session end settles correctly (charge calculated, delta refunded)
- [x] No-show forfeits deposit (no refund)
- [x] Early cancel refunds deposit minus admin fee
- [ ] All existing tests still pass (need to run)

### Key Design Decisions

1. **Booking fee is non-refundable** - covers administrative costs
2. **Deposit is refundable** - returned on prediction failure or session end
3. **No-show forfeits deposit** - incentivizes drivers to show up
4. **Early cancel refunds deposit minus 10% admin fee** - covers cancellation processing
5. **Prediction failure auto-refunds deposit** - system fault, not driver fault
6. **Session end settles deposit** - refund delta if deposit > actual charge

### Transaction Types

- `booking_fee` - non-refundable fee on prebook
- `deposit` - refundable deposit on prebook
- `refund` - refund on prediction failure, session end, or early cancel
- `session_fee` - existing session fee transaction
