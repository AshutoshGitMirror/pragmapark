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


def process_pending(db, pipeline, max_items: int = 200) -> int:
    pending = db.query(LedgerOutbox).filter(
        LedgerOutbox.status == OUTBOX_PENDING,
    ).order_by(LedgerOutbox.id.asc()).limit(max_items).all()
    if not pending:
        return 0
    now = datetime.now(timezone.utc)
    processed = []
    for item in pending:
        try:
            tx = json.loads(item.payload)
        except Exception:
            logger.error("event=outbox.json.parse.failed item_id=%d tx_hash=%s", item.id, item.tx_hash)
            item.status = OUTBOX_FAILED
            item.processed_at = now
            continue
        tx_hash = item.tx_hash or tx.get("tx_hash")
        if tx_hash and pipeline.ledger.has_tx_hash(tx_hash):
            processed.append(item)
            continue
        pipeline.add_ledger_transaction(tx)
    if not pipeline.flush_ledger():
        db.rollback()
        return 0
    for item in pending:
        if item.status == OUTBOX_PENDING or item in processed:
            item.status = OUTBOX_DELIVERED
            item.processed_at = now
    db.commit()
    return len(pending)
