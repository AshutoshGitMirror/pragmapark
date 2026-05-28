import logging
import asyncio
from datetime import datetime, timedelta, timezone

from src.constants import (
    RESERVATION_ACTIVE,
    RESERVATION_EXPIRED,
    DATA_RETENTION_DAYS,
)
from src.api.database import get_db_cm

logger = logging.getLogger(__name__)


def _periodic_loop(name, interval_s, fn, retries=0, lock=None, use_executor=False):
    async def _run():
        loop = asyncio.get_running_loop()
        while True:
            await asyncio.sleep(interval_s)
            if lock and lock.locked():
                continue
            for attempt in range(retries + 1):
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
        from src.api.database import SlotStateLog, MicroSlot
        from src.micro.predictor import slot_predictor

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
            db.commit()
    except Exception as e:
        logger.warning("Slot transition log failed: %s", e)


def _do_mining():
    from src.pipeline.orchestrator import pipeline as p

    if p.ledger.pending_transactions:
        block = p.ledger.mine_pending()
        p.ledger.save_to_file(p.bc_path)
        logger.info(
            "Background miner: mined block %d (%d tx)",
            block.index,
            len(block.transactions),
        )


def _do_cleanup():
    from src.api.database import (
        OccupancyRecord,
        TokenBlacklist,
        PredictionMetric,
        SlotReservation,
    )

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
                "Cleanup: removed %d occupancy, %d predictions, %d expired tokens, %d expired reservations",
                deleted_occ,
                deleted_pred,
                expired,
                expired_res,
            )


def _do_outbox():
    from src.pipeline.orchestrator import pipeline as p
    from src.api.ledger_outbox import process_pending

    with get_db_cm() as db:
        try:
            processed = process_pending(db, p)
            if processed:
                logger.info("Outbox flush processed %d pending ledger entries", processed)
        except Exception as e:
            db.rollback()
            logger.error("event=periodic.outbox.failed error=%s", e)
            raise


_last_ingest_hash: str = ""


def _do_ingest():
    from src.pipeline.orchestrator import pipeline as p
    from src.api.database import ParkingLot, OccupancyRecord

    global _last_ingest_hash
    with get_db_cm() as db:
        rows = (
            db.query(ParkingLot.lot_id, ParkingLot.total_slots)
            .order_by(ParkingLot.lot_id)
            .all()
        )
        current_hash = str([(r.lot_id, r.total_slots) for r in rows])
        if current_hash == _last_ingest_hash:
            return
        _last_ingest_hash = current_hash
        for row in rows:
            db.add(OccupancyRecord(**p.simulate_ingest(db, row)))
        db.commit()
        logger.info("event=periodic.ingest.completed lots=%d", len(rows))
