"""
Tests for ledger API endpoints.

These test the HTTP layer — status codes, response format,
and error handling. Business logic is tested in
test_ledger_service.py.
"""

from decimal import Decimal


class TestCreateAccount:

    def test_create_account_returns_201(self, client):
        response = client.post("/ledger/accounts", json={
            "code": "CASH-001",
            "name": "Cash Account",
            "account_type": "ASSET",
            "currency": "USD",
        })
        assert response.status_code == 201

    def test_create_account_returns_data(self, client):
        response = client.post("/ledger/accounts", json={
            "code": "CASH-001",
            "name": "Cash Account",
            "account_type": "ASSET",
        })
        data = response.json()
        assert data["code"] == "CASH-001"
        assert data["account_type"] == "ASSET"
        assert data["is_active"] is True

    def test_duplicate_code_returns_400(self, client):
        client.post("/ledger/accounts", json={
            "code": "CASH-001",
            "name": "Cash",
            "account_type": "ASSET",
        })
        response = client.post("/ledger/accounts", json={
            "code": "CASH-001",
            "name": "Cash Again",
            "account_type": "ASSET",
        })
        assert response.status_code == 400


class TestPostEntries:

    def _create_accounts(self, client):
        """Helper to create cash and deposit accounts."""
        r1 = client.post("/ledger/accounts", json={
            "code": "CASH",
            "name": "Cash",
            "account_type": "ASSET",
        })
        r2 = client.post("/ledger/accounts", json={
            "code": "DEP",
            "name": "Deposit",
            "account_type": "LIABILITY",
        })
        return r1.json()["id"], r2.json()["id"]

    def test_post_balanced_entries_returns_201(self, client):
        cash_id, dep_id = self._create_accounts(client)
        response = client.post("/ledger/entries", json={
            "currency": "USD",
            "entries": [
                {
                    "account_id": cash_id,
                    "entry_type": "DEBIT",
                    "amount": 500,
                    "description": "Deposit",
                },
                {
                    "account_id": dep_id,
                    "entry_type": "CREDIT",
                    "amount": 500,
                    "description": "Deposit",
                },
            ],
        })
        assert response.status_code == 201

    def test_post_entries_returns_transaction_id(self, client):
        cash_id, dep_id = self._create_accounts(client)
        response = client.post("/ledger/entries", json={
            "currency": "USD",
            "entries": [
                {
                    "account_id": cash_id,
                    "entry_type": "DEBIT",
                    "amount": 100,
                    "description": "Test",
                },
                {
                    "account_id": dep_id,
                    "entry_type": "CREDIT",
                    "amount": 100,
                    "description": "Test",
                },
            ],
        })
        data = response.json()
        assert "transaction_id" in data
        assert len(data["entries"]) == 2

    def test_unbalanced_entries_returns_400(self, client):
        cash_id, dep_id = self._create_accounts(client)
        response = client.post("/ledger/entries", json={
            "currency": "USD",
            "entries": [
                {
                    "account_id": cash_id,
                    "entry_type": "DEBIT",
                    "amount": 500,
                    "description": "Test",
                },
                {
                    "account_id": dep_id,
                    "entry_type": "CREDIT",
                    "amount": 300,
                    "description": "Test",
                },
            ],
        })
        assert response.status_code == 400


class TestGetBalance:

    def test_balance_after_deposit(self, client):
        r1 = client.post("/ledger/accounts", json={
            "code": "CASH",
            "name": "Cash",
            "account_type": "ASSET",
        })
        r2 = client.post("/ledger/accounts", json={
            "code": "DEP",
            "name": "Deposit",
            "account_type": "LIABILITY",
        })
        cash_id = r1.json()["id"]
        dep_id = r2.json()["id"]

        client.post("/ledger/entries", json={
            "currency": "USD",
            "entries": [
                {
                    "account_id": cash_id,
                    "entry_type": "DEBIT",
                    "amount": 500,
                    "description": "Deposit",
                },
                {
                    "account_id": dep_id,
                    "entry_type": "CREDIT",
                    "amount": 500,
                    "description": "Deposit",
                },
            ],
        })

        response = client.get(f"/ledger/accounts/{cash_id}/balance")
        assert response.status_code == 200
        assert float(response.json()["balance"]) == 500.0

    def test_nonexistent_account_returns_404(self, client):
        response = client.get("/ledger/accounts/999/balance")
        assert response.status_code == 404
