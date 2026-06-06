from pydantic import BaseModel
from typing import Optional


class SystemHealthResponse(BaseModel):
    status: str
    transactions_last_hour: int
    occupancy_updates_last_5min: int
    layers: dict
    is_demo: Optional[bool] = False


class LotSummary(BaseModel):
    lot_id: str
    name: str
    address: Optional[str] = ""
    city: Optional[str] = ""
    total_slots: int
    latitude: Optional[float] = 0
    longitude: Optional[float] = 0
    base_price: float
    price_cap: float = 200.0
    current_occupancy: float = 0
    available_slots: int = 0
    revenue_today: float = 0
    status: str = "Available"


class OccupancyTrend(BaseModel):
    hour: int
    rate: float


class RevenueDay(BaseModel):
    date: str
    revenue: float


class AlertItem(BaseModel):
    id: int
    type: str = "info"
    severity: str = "info"
    message: str
    lot_id: Optional[str] = None
    created_at: str = ""
    resolved: bool = False


class LotPerformanceItem(BaseModel):
    lot_id: str
    name: str
    occupancy: float = 0
    revenue: float = 0
    efficiency: float = 0


class SystemMetric(BaseModel):
    metric: str
    value: float
    unit: str
    status: str = "healthy"


class HourlyOccupancy(BaseModel):
    hour: int
    rate: float
    lot_id: Optional[str] = None


class AnalyticsResponse(BaseModel):
    hourly_occupancy: list[HourlyOccupancy] = []
    lot_comparison: list[LotPerformanceItem] = []
    system_performance: list[SystemMetric] = []


class DashboardResponse(BaseModel):
    total_lots: int
    total_slots: int
    avg_occupancy: float
    total_revenue: float
    total_transactions: int
    system_health: Optional[SystemHealthResponse] = None
    occupancy_trend: list[OccupancyTrend] = []
    revenue_7d: list[RevenueDay] = []
    lots: list[LotSummary] = []
    alerts: list[AlertItem] = []
    is_demo: Optional[bool] = False
