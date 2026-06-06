from src.api.database import get_session, User, Transaction

class TestWalletRoutes:
    def test_topup_requires_auth(self, client):
        resp = client.post("/api/v1/wallet/topup", json={"amount": 10.0})
        assert resp.status_code in (401, 403)

    def test_transactions_requires_auth(self, client):
        resp = client.get("/api/v1/wallet/transactions")
        assert resp.status_code in (401, 403)

    def test_topup_success_and_transactions(self, client, auth_headers):
        # Check initial balance
        bal_resp = client.get("/api/v1/wallet", headers=auth_headers)
        assert bal_resp.status_code == 200
        initial_balance = bal_resp.json()["balance"]

        # Top up $15.50
        top_resp = client.post("/api/v1/wallet/topup", json={"amount": 15.50}, headers=auth_headers)
        assert top_resp.status_code == 200
        assert top_resp.json()["amount_added"] == 15.50
        assert top_resp.json()["balance"] == initial_balance + 15.50

        # Check balance again
        bal_resp2 = client.get("/api/v1/wallet", headers=auth_headers)
        assert bal_resp2.status_code == 200
        assert bal_resp2.json()["balance"] == initial_balance + 15.50

        # Check transactions list
        tx_resp = client.get("/api/v1/wallet/transactions", headers=auth_headers)
        assert tx_resp.status_code == 200
        txs = tx_resp.json()
        assert len(txs) >= 1
        
        # Verify the top-up transaction is in the list
        topup_tx = [t for t in txs if t["action"] == "deposit"]
        assert len(topup_tx) >= 1
        assert topup_tx[0]["amount"] == 15.50
        assert topup_tx[0]["status"] == "completed"
