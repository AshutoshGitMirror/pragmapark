import logging
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Path
from src.blockchain.pool_manager import pool_manager
from src.api.auth import get_current_user
from src.api.utils import require_admin, DBRateLimiter
from src.pipeline.orchestrator import pipeline
from src.api.schemas import (
    BlockchainStatusResponse,
    TransactionRequest,
    TransactionResponse,
    PoolCreateRequest,
    PoolCreateResponse,
    PoolDetailResponse,
    MineBlockResponse,
    BlockListResponse,
    BlockData,
)

router = APIRouter(prefix="/api/v1/blockchain", tags=["Blockchain"])

logger = logging.getLogger(__name__)


@router.get("/status", response_model=BlockchainStatusResponse)
async def chain_status():
    return BlockchainStatusResponse(
        chain_length=len(pipeline.ledger.chain),
        chain_valid=pipeline.ledger.validate_chain(),
        last_block_hash=pipeline.ledger.last_block.hash,
        pending_transactions=len(pipeline.ledger.pending_transactions),
    )


@router.get("/blocks", response_model=BlockListResponse)
async def list_blocks():
    """Return all blocks from the ledger, newest first."""
    blocks = [
        BlockData(
            index=b.index,
            timestamp=b.timestamp,
            transactions=b.transactions,
            previous_hash=b.previous_hash,
            nonce=b.nonce,
            hash=b.hash,
        )
        for b in reversed(pipeline.ledger.chain)
    ]
    return BlockListResponse(blocks=blocks, total=len(blocks))


_bc_rate_limiter = DBRateLimiter(max_calls=10, window=60.0, prefix="bc_tx")


@router.post("/transaction", response_model=TransactionResponse)
async def add_transaction(
    body: TransactionRequest, user: dict = Depends(get_current_user)
):
    if not _bc_rate_limiter.check(f"tx:{user.get('sub', '')}"):
        raise HTTPException(429, "Too many transactions — rate limited")
    token_sub = user.get("sub")
    if body.driver_id != token_sub and user.get("role") != "admin":
        raise HTTPException(403, "driver_id must match authenticated user")
    tx = {
        "driver_id": body.driver_id,
        "lot_id": body.lot_id,
        "action": body.action,
        "price": body.price,
        "duration_minutes": body.duration_minutes,
    }
    tx_hash = hashlib.sha256(
        json.dumps(tx, sort_keys=True, default=str).encode()
    ).hexdigest()
    tx["tx_hash"] = tx_hash
    block_idx = pipeline.add_ledger_transaction(tx)
    return TransactionResponse(
        tx_hash=tx_hash,
        block_index=block_idx,
        status="pending",
    )


@router.post("/mine", response_model=MineBlockResponse)
async def mine_block(user: dict = Depends(get_current_user)):
    require_admin(user)
    if not pipeline.ledger.pending_transactions:
        raise HTTPException(400, "No pending transactions to mine")
    return MineBlockResponse(**pipeline.mine_ledger())


@router.get("/pool/{pool_id}", response_model=PoolDetailResponse)
async def get_pool(
    pool_id: str = Path(..., pattern=r"^[a-zA-Z0-9_-]{1,50}$"),
    user: dict = Depends(get_current_user),
):
    require_admin(user)
    pool = pool_manager.get(pool_id)
    if pool is None:
        raise HTTPException(404, "Pool not found")
    return PoolDetailResponse(**pool.to_dict())


@router.post("/pool/create", response_model=PoolCreateResponse)
async def create_pool(
    body: PoolCreateRequest, user: dict = Depends(get_current_user)
):
    require_admin(user)
    try:
        pool_manager.create(body.pool_id, body.total_spots, body.owner)
    except ValueError:
        raise HTTPException(409, "Pool already exists")
    return PoolCreateResponse(
        status="created", pool_id=body.pool_id, total_spots=body.total_spots
    )
