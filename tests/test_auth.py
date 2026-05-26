class TestRegistration:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "new@pragma.io",
            "password": "StrongPass1!",
            "full_name": "New User",
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "access_token" in data
        assert data["user"]["email"] == "new@pragma.io"

    def test_register_weak_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "weak@pragma.io",
            "password": "short",
            "full_name": "Weak",
        })
        assert resp.status_code in (400, 422)

    def test_register_no_upper(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "noupper@pragma.io",
            "password": "alllowercase1!",
            "full_name": "No Upper",
        })
        assert resp.status_code == 400

    def test_register_no_digit(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "numb@pragma.io",
            "password": "NoDigitsHere!",
            "full_name": "No Digit",
        })
        assert resp.status_code == 400

    def test_register_duplicate_email(self, client):
        first = client.post("/api/v1/auth/register", json={
            "email": "dup@pragma.io",
            "password": "StrongPass1!",
            "full_name": "First",
        })
        assert first.status_code == 200, first.text
        resp = client.post("/api/v1/auth/register", json={
            "email": "dup@pragma.io",
            "password": "StrongPass1!",
            "full_name": "Second",
        })
        assert resp.status_code == 400


class TestLogin:
    def test_login_success(self, client):
        pre_resp = client.post("/api/v1/auth/register", json={
            "email": "login@pragma.io",
            "password": "LoginPass1!",
            "full_name": "Login User",
        })
        assert pre_resp.status_code == 200, pre_resp.text
        resp = client.post("/api/v1/auth/login", json={
            "email": "login@pragma.io",
            "password": "LoginPass1!",
        })
        assert resp.status_code == 200
        assert "access_token" in resp.json()

    def test_login_wrong_password(self, client):
        pre_resp = client.post("/api/v1/auth/register", json={
            "email": "wrongpwd@pragma.io",
            "password": "CorrectPwd1!",
            "full_name": "Wrong Pwd",
        })
        assert pre_resp.status_code == 200, pre_resp.text
        resp = client.post("/api/v1/auth/login", json={
            "email": "wrongpwd@pragma.io",
            "password": "WrongPwd1!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "ghost@pragma.io",
            "password": "GhostPwd1!",
        })
        assert resp.status_code == 401


class TestLogout:
    def test_logout_success(self, client, auth_headers):
        resp = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["message"] == "logged_out"

    def test_logout_reuses_token(self, client, auth_headers):
        client.post("/api/v1/auth/logout", headers=auth_headers)
        resp = client.post("/api/v1/auth/logout", headers=auth_headers)
        assert resp.status_code == 401
