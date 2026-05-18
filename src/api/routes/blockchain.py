from fastapi import APIRouter
from src.blockchain import BlockchainLedger, ParkingPool, RevenueShareContract

router = APIRouter(prefix="/api/v1/blockchain", tags=["Blockchain"])

_ledger = BlockchainLedger(difficulty=2)
_pools: dict = {}


@router.get("/status")
async def chain_status():
    return {
        "chain_length": len(_ledger.chain),
        "chain_valid": _ledger.validate_chain(),
        "last_block_hash": _ledger.last_block.hash,
        "pending_transactions": len(_ledger.pending_transactions),
        "total_blocks": len(_ledger.chain),
    }


@router.post("/transaction")
async def add_transaction(driver_id: str, lot_id: str, action: str,
                           price: float, duration_minutes: int = 60):
    tx = {
        "driver_id": driver_id,
        "lot_id": lot_id,
        "action": action,
        "price": price,
        "duration_minutes": duration_minutes,
    }
    block_idx = _ledger.add_transaction(tx)
    return {"tx_hash": f"tx_{len(_ledger.pending_transactions)}",
            "block_index": block_idx, "status": "pending"}


@router.post("/mine")
async def mine_block():
    block = _ledger.mine_pending()
    return {
        "block_index": block.index,
        "hash": block.hash,
        "transactions": len(block.transactions),
        "nonce": block.nonce,
        "timestamp": block.timestamp,
    }


@router.get("/pool/{pool_id}")
async def get_pool(pool_id: str):
    pool = _pools.get(pool_id)
    if pool is None:
        return {"error": "Pool not found"}
    return pool.to_dict()


@router.post("/pool/create")
async def create_pool(pool_id: str, total_spots: int, owner: str = "city"):
    _pools[pool_id] = ParkingPool(pool_id, total_spots, owner)
    return {"status": "created", "pool_id": pool_id, "total_spots": total_spots}
