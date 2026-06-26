import json
import hashlib
import logging
from datetime import datetime, timezone

from src.api.database import LedgerOutbox
from src.constants import OUTBOX_PENDING, OUTBOX_DELIVERED, OUTBOX_FAILED

logger = logging.getLogger(__name__)


def _hash_tx(tx: dict) -> str:
    raw = json.dumps(tx, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def enqueue_outbox(db, tx: dict) -> LedgerOutbox:
    tx_hash = tx.get("tx_hash") or _hash_tx(tx)
    tx["tx_hash"] = tx_hash
    payload = json.dumps(tx, sort_keys=True, default=str)
    outbox = LedgerOutbox(tx_hash=tx_hash, payload=payload)
    db.add(outbox)
    return outbox


def process_pending(db, pipeline, max_items: int = 200) -> dict:
    pending = (
        db.query(LedgerOutbox)
        .filter(
            LedgerOutbox.status == OUTBOX_PENDING,
        )
        .order_by(LedgerOutbox.id.asc())
        .limit(max_items)
        .all()
    )
    if not pending:
        # Blockchain mining is async — background worker mines pending txs
        return {"processed": 0, "skipped": 0, "failed": 0}
    now = datetime.now(timezone.utc)
    already_known = []
    to_submit = []
    failed = []
    for item in pending:
        try:
            tx = json.loads(item.payload)
        except Exception:
            logger.error(
                "event=outbox.json.parse.failed item_id=%d tx_hash=%s",
                item.id,
                item.tx_hash,
            )
            item.status = OUTBOX_FAILED
            item.processed_at = now
            failed.append(item)
            continue
        tx_hash = item.tx_hash or tx.get("tx_hash")
        if tx_hash and pipeline.ledger.has_tx_hash(tx_hash):
            already_known.append(item)
            continue
        pipeline.add_ledger_transaction(tx)
        to_submit.append(item)
    # Blockchain mining is async — background worker mines pending txs
        db.rollback()
        return {
            "processed": 0,
            "skipped": len(already_known),
            "failed": len(failed),
        }
    for item in pending:
        if item.status == OUTBOX_PENDING:
            item.status = OUTBOX_DELIVERED
            item.processed_at = now
    db.commit()
    return {
        "processed": len(to_submit),
        "skipped": len(already_known),
        "failed": len(failed),
    }
