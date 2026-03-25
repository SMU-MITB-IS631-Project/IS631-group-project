import requests
import json
from fastapi.testclient import TestClient
from tests.test_transactions_integration import app, USER_HEADERS, _create_transaction, _transaction_payload

client = TestClient(app)
first = _create_transaction(client, _transaction_payload(item="First txn", date="2026-02-15"))
second = _create_transaction(client, _transaction_payload(item="Second txn", date="2026-02-16"))

response = client.put(
    "/api/v1/transactions/bulk/status",
    json={
        "transaction_ids": [int(first["id"]), int(second["id"])],
        "status": "deleted_with_card",
    },
    headers=USER_HEADERS,
)
print("BULK RESPONSE:", response.json())
