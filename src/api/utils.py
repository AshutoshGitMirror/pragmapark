from typing import Optional
import time
from fastapi import HTTPException

ADMIN_ROLES: set[str] = {"admin", "city_planner"}


class RateLimiter:
    def __init__(self, max_calls: int = 10, window: float = 60.0, cleanup_interval: float = 600.0):
        self.max_calls = max_calls
        self.window = window
        self.cleanup_interval = cleanup_interval
        self._buckets: dict[str, list[float]] = {}
        self._last_cleanup = time.monotonic()

    def check(self, key: str) -> bool:
        now = time.monotonic()
        self._maybe_cleanup(now)
        bucket = self._buckets.get(key)
        if bucket is None:
            self._buckets[key] = [now]
            return True
        cutoff = now - self.window
        bucket[:] = [t for t in bucket if t > cutoff]
        if len(bucket) >= self.max_calls:
            return False
        bucket.append(now)
        return True

    def _maybe_cleanup(self, now: float) -> None:
        if now - self._last_cleanup > self.cleanup_interval:
            cutoff = now - self.cleanup_interval
            self._buckets = {k: v for k, v in self._buckets.items() if v and v[-1] >= cutoff}
            self._last_cleanup = now


def require_role(user: dict, allowed_roles: Optional[set] = None) -> None:
    if allowed_roles is None:
        allowed_roles = ADMIN_ROLES
    if user.get("role") not in allowed_roles:
        raise HTTPException(403, "Insufficient permissions")


def require_admin(user: dict) -> None:
    require_role(user, ADMIN_ROLES)


def driver_id(user: dict) -> str:
    return user.get("sub") or user.get("email", "unknown")
