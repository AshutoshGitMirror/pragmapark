from pydantic import BaseModel


class DashboardResponse(BaseModel):
    total_lots: int
    total_users: int
    total_revenue: float
    total_transactions: int
    system_occupancy: float


class SystemHealthResponse(BaseModel):
    status: str
    transactions_last_hour: int
    occupancy_updates_last_5min: int
    layers: dict
