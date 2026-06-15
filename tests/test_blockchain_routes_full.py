import pytest
from src.pipeline.orchestrator import pipeline
from src.api.schemas import BlockListResponse, PoolDetailResponse


@pytest.fixture(autouse=True)
def _ensure_genesis():
    pass


class TestBlockchainBlocks:
    def test_blocks_no_auth_required(self, client):
        resp = client.get("/api/v1/blockchain/blocks")
        assert resp.status_code == 200
        data = resp.json()
        assert "blocks" in data
        assert "total" in data
        assert isinstance(data["blocks"], list)
        assert data["total"] >= 1

    def test_blocks_has_first_block(self, client, admin_headers):
        resp = client.get("/api/v1/blockchain/blocks", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["blocks"]) >= 1
        first = data["blocks"][0]
        assert "index" in first
        assert "timestamp" in first
        assert "transactions" in first
        assert "previous_hash" in first
        assert "hash" in first

    def test_blocks_genesis_has_no_previous(self, client, admin_headers):
        resp = client.get("/api/v1/blockchain/blocks", headers=admin_headers)
        assert resp.status_code == 200
        blocks = resp.json()["blocks"]
        genesis = blocks[-1]
        assert genesis["index"] == 0

    def test_blocks_newest_first(self, client, admin_headers):
        resp = client.get("/api/v1/blockchain/blocks", headers=admin_headers)
        assert resp.status_code == 200
        blocks = resp.json()["blocks"]
        indices = [b["index"] for b in blocks]
        assert indices == sorted(indices, reverse=True)

    def test_blocks_matches_pydantic_schema(self, client, admin_headers):
        resp = client.get("/api/v1/blockchain/blocks", headers=admin_headers)
        assert resp.status_code == 200
        validated = BlockListResponse(**resp.json())
        assert validated.total >= 1
        assert len(validated.blocks) == validated.total


class TestBlockchainMine:
    def test_mine_requires_admin(self, client, auth_headers):
        resp = client.post("/api/v1/blockchain/mine", headers=auth_headers)
        assert resp.status_code == 403

    def test_mine_requires_auth(self, client):
        resp = client.post("/api/v1/blockchain/mine")
        assert resp.status_code in (401, 403)

    def test_mine_no_pending_returns_400(self, client, admin_headers):
        resp = client.post("/api/v1/blockchain/mine", headers=admin_headers)
        assert resp.status_code == 400
        assert "pending" in resp.text.lower()

    def test_mine_with_pending_succeeds(self, client, admin_headers):
        pipeline.ledger.add_transaction(
            {
                "driver_id": "test_mine_driver",
                "lot_id": "mine_test_lot",
                "action": "session_fee",
                "price": 5.0,
                "duration_minutes": 30,
            }
        )
        resp = client.post("/api/v1/blockchain/mine", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "block_index" in data
        assert "hash" in data
        assert data["block_index"] > 0
        assert len(data["hash"]) == 64

    def test_mine_increases_chain_length(self, client, admin_headers):
        before = len(pipeline.ledger.chain)
        pipeline.ledger.add_transaction(
            {
                "driver_id": "test_mine_driver2",
                "lot_id": "mine_test_lot2",
                "action": "payment",
                "price": 3.0,
                "duration_minutes": 15,
            }
        )
        client.post("/api/v1/blockchain/mine", headers=admin_headers)
        assert len(pipeline.ledger.chain) == before + 1


class TestBlockchainPool:
    POOL_ID = "test_pool_1"

    def test_get_pool_requires_admin(self, client, auth_headers):
        resp = client.get(
            f"/api/v1/blockchain/pool/{self.POOL_ID}", headers=auth_headers
        )
        assert resp.status_code == 403

    def test_get_pool_requires_auth(self, client):
        resp = client.get(f"/api/v1/blockchain/pool/{self.POOL_ID}")
        assert resp.status_code in (401, 403)

    def test_get_nonexistent_pool_returns_404(self, client, admin_headers):
        resp = client.get(
            "/api/v1/blockchain/pool/nonexistent_pool", headers=admin_headers
        )
        assert resp.status_code == 404

    def test_create_pool_requires_admin(self, client, auth_headers):
        resp = client.post(
            "/api/v1/blockchain/pool/create",
            json={
                "pool_id": self.POOL_ID,
                "total_spots": 100,
                "owner": "admin@test.com",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_create_pool_returns_created(self, client, admin_headers):
        resp = client.post(
            "/api/v1/blockchain/pool/create",
            json={
                "pool_id": self.POOL_ID,
                "total_spots": 100,
                "owner": "admin@test.com",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "created"
        assert data["pool_id"] == self.POOL_ID
        assert data["total_spots"] == 100

    def test_create_duplicate_pool_returns_409(self, client, admin_headers):
        client.post(
            "/api/v1/blockchain/pool/create",
            json={
                "pool_id": "dup_pool",
                "total_spots": 50,
                "owner": "dup@test.com",
            },
            headers=admin_headers,
        )
        resp = client.post(
            "/api/v1/blockchain/pool/create",
            json={
                "pool_id": "dup_pool",
                "total_spots": 50,
                "owner": "dup@test.com",
            },
            headers=admin_headers,
        )
        assert resp.status_code == 409

    def test_create_then_get_pool(self, client, admin_headers):
        pid = "roundtrip_pool"
        client.post(
            "/api/v1/blockchain/pool/create",
            json={"pool_id": pid, "total_spots": 200, "owner": "rt@test.com"},
            headers=admin_headers,
        )
        resp = client.get(
            f"/api/v1/blockchain/pool/{pid}", headers=admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["pool_id"] == pid
        assert data["total_spots"] == 200

    def test_get_pool_matches_pydantic_schema(self, client, admin_headers):
        pid = "schema_pool"
        client.post(
            "/api/v1/blockchain/pool/create",
            json={
                "pool_id": pid,
                "total_spots": 75,
                "owner": "schema@test.com",
            },
            headers=admin_headers,
        )
        resp = client.get(
            f"/api/v1/blockchain/pool/{pid}", headers=admin_headers
        )
        assert resp.status_code == 200
        validated = PoolDetailResponse(**resp.json())
        assert validated.pool_id == pid
