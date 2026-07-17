"""Sensor API-key authentication.

Each CV/physical sensor is issued a long random API key (``X-Sensor-Key``
header). Keys are stored hashed (SHA-256); the plaintext is shown once at
creation / rotation. A sensor is bound to exactly one lot and one owner
(the lot owner), so a key never grants cross-lot or cross-tenant access.
"""

import hashlib
import secrets
from typing import Optional

from src.api.database import Sensor


def generate_sensor_key() -> str:
    """Return a new high-entropy sensor API key (plaintext)."""
    return secrets.token_urlsafe(32)


def hash_sensor_key(key: str) -> str:
    """Return the storage form (SHA-256 hex) of a sensor key."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def resolve_sensor(api_key: Optional[str], db) -> Optional[Sensor]:
    """Resolve an active Sensor from a raw API key, or None.

    The key is hashed and matched against ``api_key_hash``; inactive
    sensors never resolve.
    """
    if not api_key:
        return None
    return (
        db.query(Sensor)
        .filter(Sensor.api_key_hash == hash_sensor_key(api_key))
        .filter(Sensor.active.is_(True))
        .first()
    )
