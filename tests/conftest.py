import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uuid
_SESSION_UID = uuid.uuid4().hex[:12]
_DEFAULT_URL = f"sqlite:////tmp/pragma_test_{os.getpid()}_{_SESSION_UID}.db"
os.environ.setdefault("DATABASE_URL", _DEFAULT_URL)
os.environ.setdefault("JWT_SECRET", "test-secret-for-testing-only")
os.environ.setdefault("MODEL_ARTIFACT_PATH", "/tmp/test-models")

from src.api.server import app
from src.api.database import Base, get_engine
from src.pipeline.orchestrator import pipeline
from src.blockchain.ledger import BlockchainLedger


def _clear_rate_limiters():
    try:
        from src.api.server import _global_rate_limiter
        _global_rate_limiter._buckets.clear()
    except Exception:
        pass
    try:
        from src.api.routes.auth import _register_limiter, _login_ip_limiter, _login_account_limiter
        _register_limiter._buckets.clear()
        _login_ip_limiter._buckets.clear()
        _login_account_limiter._buckets.clear()
    except Exception:
        pass
    try:
        from src.api.routes.blockchain import _bc_rate_limiter
        _bc_rate_limiter._buckets.clear()
    except Exception:
        pass
    try:
        from src.api.routes.micro.helpers import _reserve_limiter, _release_limiter, _slot_list_limiter
        _reserve_limiter._buckets.clear()
        _release_limiter._buckets.clear()
        _slot_list_limiter._buckets.clear()
    except Exception:
        pass


@pytest.fixture(autouse=True)
def setup_db():
    import src.api.database as _db_mod
    if _db_mod._engine is not None:
        _db_mod._engine.dispose()
    _db_mod._engine = None
    _db_mod._Session = None
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _clear_rate_limiters()
    try:
        from src.micro.state_engine import slot_state_engine
        slot_state_engine._states.clear()
        slot_state_engine._reservations.clear()
        slot_state_engine._reservation_expiry.clear()
    except Exception:
        pass
    yield
    engine.dispose()
    pipeline.ledger = BlockchainLedger(difficulty=2)


@pytest.fixture
def client():
    return TestClient(app)


def _register_or_login(client, email, password, full_name):
    resp = client.post("/api/v1/auth/register", json={
        "email": email, "password": password, "full_name": full_name,
    })
    if resp.status_code == 200:
        return resp.json().get("access_token", "")
    if resp.status_code == 400 and "already registered" in resp.text:
        resp = client.post("/api/v1/auth/login", json={
            "email": email, "password": password,
        })
        if resp.status_code == 429:
            _clear_rate_limiters()
            resp = client.post("/api/v1/auth/login", json={
                "email": email, "password": password,
            })
    assert resp.status_code == 200, f"auth failed ({resp.status_code}): {resp.text}"
    return resp.json().get("access_token", "")


@pytest.fixture
def auth_headers(client):
    token = _register_or_login(client, "test@pragma.io", "TestPass123!", "Test User")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(client):
    from src.api.database import get_session, User
    from src.api.auth import hash_password
    db = get_session()
    try:
        admin = db.query(User).filter(User.email == "admin@pragma.io").first()
        if not admin:
            admin = User(
                email="admin@pragma.io",
                hashed_password=hash_password("AdminPass123!"),
                full_name="Admin",
                role="admin",
            )
            db.add(admin)
            db.commit()
            db.refresh(admin)
    finally:
        db.close()
    token = _register_or_login(client, "admin@pragma.io", "AdminPass123!", "Admin")
    return {"Authorization": f"Bearer {token}"}
