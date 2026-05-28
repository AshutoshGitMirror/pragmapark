from pydantic import BaseModel, ConfigDict, Field


class BlockchainStatusResponse(BaseModel):
    chain_length: int
    chain_valid: bool
    last_block_hash: str
    pending_transactions: int


class TransactionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    driver_id: str = Field(min_length=1, max_length=100)
    lot_id: str = Field(min_length=1, max_length=50)
    action: str = Field(min_length=1, max_length=50)
    price: float = Field(default=0.0, ge=0)  # NOTE: maps to ORM Transaction.amount
    duration_minutes: int = Field(default=60, ge=1, le=100000)


class TransactionResponse(BaseModel):
    tx_hash: str
    block_index: int
    status: str


class PoolCreateRequest(BaseModel):
    pool_id: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    total_spots: int = Field(ge=1, le=100000)
    owner: str = Field("city", max_length=100)


class PoolCreateResponse(BaseModel):
    status: str
    pool_id: str
    total_spots: int


class PoolDetailResponse(BaseModel):
    pool_id: str
    total_spots: int
    owner: str
    available: int
    active_allocations: int
    total_revenue: float
    pool_revenue: float


class MineBlockResponse(BaseModel):
    block_index: int
    hash: str
    transactions: int
    nonce: int
    timestamp: float
