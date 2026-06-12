class TestMARL:
    def test_marl_status_not_trained(self, client, admin_headers):
        resp = client.get("/api/v1/marl/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") in ("not_trained", "trained")

    def test_marl_train_requires_admin(self, client, auth_headers):
        resp = client.post(
            "/api/v1/marl/train",
            json={"num_zones": 3, "episodes": 2},
            headers=auth_headers,
        )
        assert resp.status_code == 403

    def test_marl_train_with_admin(self, client, admin_headers):
        resp = client.post(
            "/api/v1/marl/train",
            json={"num_zones": 2, "episodes": 2},
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "trained"
        assert data["num_zones"] == 2

    def test_marl_requires_auth(self, client):
        resp = client.get("/api/v1/marl/status")
        assert resp.status_code in (401, 403)

    def test_marl_status_after_train(self, client, admin_headers):
        client.post(
            "/api/v1/marl/train",
            json={"num_zones": 2, "episodes": 2},
            headers=admin_headers,
        )
        resp = client.get("/api/v1/marl/status", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "trained"
        assert data["num_zones"] == 2
