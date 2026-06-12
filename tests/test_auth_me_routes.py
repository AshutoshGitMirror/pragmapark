class TestAuthMe:
    def test_me_requires_auth(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    def test_me_returns_user_info(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@pragma.io"
        assert data["full_name"] == "Test User"
        assert data["role"] in ("driver", "admin", "lot_owner", "city_planner")
        assert isinstance(data["id"], int)
        assert isinstance(data.get("organization"), str)

    def test_me_works_with_admin(self, client, admin_headers):
        resp = client.get("/api/v1/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "admin@pragma.io"
        assert data["role"] == "admin"

    def test_me_matches_auth_user_schema(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        from src.api.schemas.auth import AuthUser

        validated = AuthUser(**resp.json())
        assert validated.id > 0
        assert validated.role

    def test_me_invalid_token_rejected(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert resp.status_code in (401, 403)
