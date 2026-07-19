import logging

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.auth import get_current_user
from src.api.schemas.routing import RouteRequest, RouteResponse
from src.routing.router import route as compute_route

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/routing", tags=["Routing"])


@router.post("/route", response_model=RouteResponse)
def routing_route(
    body: RouteRequest,
    user: dict = Depends(get_current_user),
):
    """Shortest drive/walk route between two coordinates in Mumbai.

    Used by the driver map to draw a polyline from the driver's location
    to a chosen shared residential slot or commercial lot.
    """
    try:
        res = compute_route(
            (body.origin.lat, body.origin.lng),
            (body.destination.lat, body.destination.lng),
            body.mode,
        )
    except Exception:
        logger.exception("event=routing.route.failed user=%s", user.get("sub"))
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Routing failed")

    if not res["found"]:
        return RouteResponse(
            found=False,
            distance_m=0.0,
            duration_s=0.0,
            geometry=[],
            message=res.get("message"),
        )

    return RouteResponse(
        found=True,
        distance_m=round(float(res["distance_m"]), 1),
        duration_s=round(float(res["duration_s"]), 1),
        geometry=[{"lat": p[0], "lng": p[1]} for p in res["geometry"]],
    )
