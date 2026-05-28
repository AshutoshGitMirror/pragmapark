from typing import Dict, Optional

from pydantic import BaseModel, Field


class MARLRequest(BaseModel):
    num_zones: int = Field(4, ge=1, le=100)
    episodes: int = Field(200, ge=1, le=10000)


class MARLResponse(BaseModel):
    status: str
    num_zones: int
    episodes: int
    final_reward: float
    validation: Dict


class MARLStatusResponse(BaseModel):
    status: str
    num_zones: Optional[int] = None
    episodes_completed: Optional[int] = None
    mean_reward: Optional[float] = None
    validation: Optional[dict] = None
