import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", f"sqlite:////tmp/pragma_test_{os.getpid()}.db")
os.environ.setdefault("JWT_SECRET", "test-secret-for-testing-only")
os.environ.setdefault("MODEL_ARTIFACT_PATH", "/tmp/test-models")

from src.api.server import app
from src.api.database import Base, get_engine
from src.pipeline.orchestrator import pipeline
from src.blockchain.ledger import BlockchainLedger


import glob


def _remove_test_db():
    for f in glob.glob("/tmp/pragma_test*.db*"):
        try:
            os.remove(f)
        except OSError:
            pass


@pytest.fixture(autouse=True)
def setup_db():
    _remove_test_db()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    try:
        from src.api.server import _global_rate_limiter
        from src.api.routes.auth import _register_limiter, _login_ip_limiter, _login_account_limiter
        from src.api.routes.blockchain import _bc_rate_limiter
        from src.api.routes.micro import _reserve_limiter, _release_limiter, _slot_list_limiter
        _global_rate_limiter._buckets.clear()
        _register_limiter._buckets.clear()
        _login_ip_limiter._buckets.clear()
        _login_account_limiter._buckets.clear()
        _bc_rate_limiter._buckets.clear()
        _reserve_limiter._buckets.clear()
        _release_limiter._buckets.clear()
        _slot_list_limiter._buckets.clear()
    except ImportError:
        pass
    try:
        from src.micro.state_engine import slot_state_engine
        slot_state_engine._states.clear()
        slot_state_engine._reservations.clear()
        slot_state_engine._reservation_expiry.clear()
    except ImportError:
        pass
    yield
    engine.dispose()
    pipeline.ledger = BlockchainLedger(difficulty=2)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/v1/auth/register", json={
        "email": "test@pragma.io",
        "password": "TestPass123!",
        "full_name": "Test User",
    })
    assert resp.status_code == 200, resp.text
    token = resp.json().get("access_token", "")
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
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@pragma.io",
        "password": "AdminPass123!",
    })
    assert resp.status_code == 200, resp.text
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}
