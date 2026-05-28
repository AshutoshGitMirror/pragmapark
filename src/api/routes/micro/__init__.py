from fastapi import APIRouter

from .slots import router as slots_router
from .zones import router as zones_router
from .reservations import router as reservations_router
from .prebooks import router as prebooks_router
from .admin import router as admin_router
from .helpers import (
    _reserve_limiter,
    _release_limiter,
    _slot_list_limiter,
    _prebook_limiter,
)

router = APIRouter(prefix="/api/v1/micro", tags=["Micro Slot"])
router.include_router(slots_router)
router.include_router(zones_router)
router.include_router(reservations_router)
router.include_router(prebooks_router)
router.include_router(admin_router)

__all__ = [
    "router",
    "_reserve_limiter",
    "_release_limiter",
    "_slot_list_limiter",
    "_prebook_limiter",
]
