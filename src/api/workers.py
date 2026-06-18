import logging
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import func as sa_func

from src.constants import (
    RESERVATION_ACTIVE,
    RESERVATION_EXPIRED,
    RESERVATION_NO_SHOW,
    DATA_RETENTION_DAYS,
)
from src.api.database import (
    get_db_cm,
    SlotStateLog,
    MicroSlot,
    PrebookRecord,
    OccupancyRecord,
    TokenBlacklist,
    PredictionMetric,
    SlotReservation,
    ParkingLot,
)
from src.micro.predictor import slot_predictor
from src.pipeline.orchestrator import pipeline as p
from src.api.ledger_outbox import process_pending

logger = logging.getLogger(__name__)


_stop_event = asyncio.Event()


def signal_stop():
    _stop_event.set()


def _periodic_loop(
    name, interval_s, fn, retries=0, lock=None, use_executor=False
):
    async def _run():
        loop = asyncio.get_running_loop()
        while not _stop_event.is_set():
            try:
                await asyncio.wait_for(
                    asyncio.sleep(interval_s),
                    timeout=interval_s,
                )
            except asyncio.TimeoutError:
                pass
            if _stop_event.is_set():
                break
            if lock and lock.locked():
                continue
            for attempt in range(retries + 1):
                if _stop_event.is_set():
                    break
                try:
                    if use_executor:
                        await loop.run_in_executor(None, fn)
                    elif lock:
                        async with lock:
                            fn()
                    else:
                        fn()
                    break
                except Exception as e:
                    if attempt >= retries:
                        logger.error("Periodic[%s] failed: %s", name, e)
                    else:
                        logger.warning(
                            "Periodic[%s] retry %d/%d: %s",
                            name,
                            attempt + 1,
                            retries,
                            e,
                        )
                        await asyncio.sleep(5 * (2**attempt))

    return _run


def _log_slot_transition(slot_id, prev_state, new_state, driver_id=""):
    try:
        now = datetime.now(timezone.utc)
        slot_predictor.record_transition(slot_id, prev_state, new_state, now)
        with get_db_cm() as db:
            slot = db.query(MicroSlot).filter(MicroSlot.id == slot_id).first()
            db.add(
                SlotStateLog(
                    slot_id=slot_id,
                    lot_id=slot.lot_id if slot else "",
                    previous_state=prev_state,
                    new_state=new_state,
                    driver_id=driver_id,
                    timestamp=now,
                )
            )
            if (
                prev_state in ("prebooked", "reserved")
                and new_state == "available"
            ):
                prebook = (
                    db.query(PrebookRecord)
                    .filter(
                        PrebookRecord.slot_id == slot_id,
                        PrebookRecord.status.in_(["active", "confirmed"]),
                    )
                    .order_by(PrebookRecord.created_at.desc())
                    .first()
                )
                if (
                    prebook
                    and float(prebook.deposit or 0.0) > 0
                    and not prebook.deposit_refunded
                ):
                    prebook.status = RESERVATION_NO_SHOW
                    prebook.deposit_refunded = True
                    logger.info(
                        "event=no_show.penalty slot=%s driver=%s "
                        "deposit=%.2f_forfeited",
                        slot_id,
                        prebook.driver_id,
                        float(prebook.deposit),
                    )
            db.commit()
    except Exception as e:
        logger.warning("Slot transition log failed: %s", e)


def _do_mining():
    if p.ledger.pending_transactions:
        block = p.ledger.mine_pending()
        p.ledger.save_to_file(p.bc_path)
        logger.info(
            "Background miner: mined block %d (%d tx)",
            block.index,
            len(block.transactions),
        )


def _do_cleanup():
    cutoff = datetime.now(timezone.utc) - timedelta(days=DATA_RETENTION_DAYS)
    with get_db_cm() as db:
        deleted_occ = (
            db.query(OccupancyRecord)
            .filter(OccupancyRecord.timestamp < cutoff)
            .delete()
        )
        deleted_pred = (
            db.query(PredictionMetric)
            .filter(PredictionMetric.timestamp < cutoff)
            .delete()
        )
        expired = (
            db.query(TokenBlacklist)
            .filter(TokenBlacklist.expires_at < datetime.now(timezone.utc))
            .delete()
        )
        expired_res = (
            db.query(SlotReservation)
            .filter(
                SlotReservation.status == RESERVATION_ACTIVE,
                SlotReservation.expires_at < datetime.now(timezone.utc),
            )
            .update({"status": RESERVATION_EXPIRED}, synchronize_session=False)
        )
        db.commit()
        if deleted_occ or deleted_pred or expired or expired_res:
            logger.info(
                "Cleanup: removed %d occupancy, %d predictions, "
                "%d expired tokens, %d expired reservations",
                deleted_occ,
                deleted_pred,
                expired,
                expired_res,
            )


def _do_outbox():
    with get_db_cm() as db:
        try:
            result = process_pending(db, p)
            total = result["processed"] + result["skipped"] + result["failed"]
            if total:
                logger.info(
                    "Outbox flush: %d processed, %d skipped, %d failed",
                    result["processed"],
                    result["skipped"],
                    result["failed"],
                )
        except Exception as e:
            db.rollback()
            logger.error("event=periodic.outbox.failed error=%s", e)
            raise


_last_ingest_hash: str = ""


def _do_ingest():
    global _last_ingest_hash
    with get_db_cm() as db:
        # Single query for lot data (was duplicated before)
        rows = (
            db.query(ParkingLot.lot_id, ParkingLot.total_slots)
            .order_by(ParkingLot.lot_id)
            .all()
        )
        # Use GROUP BY + MAX for cross-DB compatible latest-timestamp-per-lot
        # (DISTINCT ON is PostgreSQL-only)
        max_ts_subq = (
            db.query(
                OccupancyRecord.lot_id,
                sa_func.max(OccupancyRecord.timestamp).label("max_ts"),
            )
            .group_by(OccupancyRecord.lot_id)
            .subquery()
        )
        latest_ts_per_lot = (
            db.query(
                OccupancyRecord.lot_id,
                OccupancyRecord.timestamp,
            )
            .join(
                max_ts_subq,
                (OccupancyRecord.lot_id == max_ts_subq.c.lot_id)
                & (OccupancyRecord.timestamp == max_ts_subq.c.max_ts),
            )
            .order_by(OccupancyRecord.lot_id)
            .all()
        )
        ts_map = {r.lot_id: r.timestamp.replace(tzinfo=timezone.utc).isoformat() for r in latest_ts_per_lot}
        current_hash = str(
            [(r.lot_id, r.total_slots, ts_map.get(r.lot_id, "")) for r in rows]
        )
        if current_hash == _last_ingest_hash:
            return
        _last_ingest_hash = current_hash
        for row in rows:
            db.add(OccupancyRecord(**p.simulate_ingest(db, row)))
        db.commit()
        logger.info("event=periodic.ingest.completed lots=%d", len(rows))
