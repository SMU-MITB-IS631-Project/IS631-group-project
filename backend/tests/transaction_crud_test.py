"""Test suite for Transaction CRUD endpoints (POST, GET, PUT, DELETE)"""
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


# Ensure `backend/` is on sys.path so `import app...` works
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import Base  # noqa: E402
from app.dependencies.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user_profile import UserProfile, BenefitsPreference  # noqa: E402
from app.models.card_catalogue import CardCatalogue, BankEnum, BenefitTypeEnum, StatusEnum  # noqa: E402
from app.models.user_owned_cards import UserOwnedCard, UserOwnedCardStatus  # noqa: E402
from app.models.transaction import UserTransaction, TransactionChannel, TransactionCategory, TransactionStatus  # noqa: E402


class TransactionCRUDTests(unittest.TestCase):
    """Test Transaction CRUD operations"""

    def setUp(self):
        """Set up test database with sample data"""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=engine)
        self.Session = sessionmaker(bind=engine)

        # Create test data
        with self.Session() as db:
            # User profile
            db.add(
                UserProfile(
                    id=1,
                    username="testuser",
                    benefits_preference=BenefitsPreference.cashback,
                )
            )
            # Card in catalog
            db.add(
                CardCatalogue(
                    card_id=10,
                    bank=BankEnum.DBS,
                    card_name="Test Card",
                    benefit_type=BenefitTypeEnum.CASHBACK,
                    base_benefit_rate=Decimal("0.01"),
                    status=StatusEnum.VALID,
                )
            )
            # User owns this card
            db.add(UserOwnedCard(user_id=1, card_id=10, status=UserOwnedCardStatus.Active))
            
            # Existing transaction for GET tests
            db.add(
                UserTransaction(
                    id=100,
                    user_id=1,
                    card_id=10,
                    amount_sgd=Decimal("50.00"),
                    item="Test Transaction",
                    channel=TransactionChannel.online,
                    category=TransactionCategory.food,
                    is_overseas=False,
                    transaction_date=date(2026, 3, 1),
                    status=TransactionStatus.Active,
                )
            )
            db.commit()

        # Override DB dependency
        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        """Clean up"""
        app.dependency_overrides.clear()

    # ========== POST TESTS ==========

    def test_create_transaction_success(self):
        """Test creating a new transaction"""
        resp = self.client.post(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "card_id": 10,
                    "amount_sgd": 120.50,
                    "item": "GrabFood",
                    "channel": "online",
                    "category": "Food",
                    "is_overseas": False,
                    "date": "2026-03-04",
                }
            },
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.json()
        self.assertIn("transaction", data)
        txn = data["transaction"]
        self.assertEqual(txn["item"], "GrabFood")
        self.assertEqual(float(txn["amount_sgd"]), 120.50)
        self.assertEqual(txn["card_id"], "10")
        self.assertEqual(txn["channel"], "online")
        self.assertEqual(txn["status"], "active")

    def test_create_transaction_invalid_card(self):
        """Test creating transaction with card not in wallet"""
        resp = self.client.post(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "card_id": 999,  # Non-existent card
                    "amount_sgd": 50.00,
                    "item": "Test",
                    "channel": "online",
                    "is_overseas": False,
                }
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        error = data.get("error") or data.get("detail", {}).get("error", {})
        self.assertEqual(error.get("code"), "VALIDATION_ERROR")
        self.assertIn("not found in user wallet", error.get("message", ""))

    def test_create_transaction_no_user_header(self):
        """Test creating transaction without x-user-id header"""
        resp = self.client.post(
            "/api/v1/transactions",
            json={
                "transaction": {
                    "card_id": 10,
                    "amount_sgd": 50.00,
                    "item": "Test",
                    "channel": "online",
                    "is_overseas": False,
                }
            },
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "UNAUTHORIZED")

    def test_create_transaction_null_required_field(self):
        """Test that Pydantic rejects null for required fields on CREATE"""
        resp = self.client.post(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "card_id": 10,
                    "amount_sgd": 50.00,
                    "item": None,  # Required field - Pydantic should reject
                    "channel": "online",
                    "is_overseas": False,
                }
            },
        )
        self.assertEqual(resp.status_code, 400)  # Validation error
        data = resp.json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")

    # ========== GET TESTS ==========

    def test_list_transactions(self):
        """Test listing all transactions for a user"""
        resp = self.client.get(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("transactions", data)
        self.assertGreaterEqual(len(data["transactions"]), 1)
        # Should contain the transaction from setUp
        txn = data["transactions"][0]
        self.assertEqual(txn["item"], "Test Transaction")

    def test_list_transactions_no_user_header(self):
        """Test listing transactions without user header"""
        resp = self.client.get("/api/v1/transactions")
        self.assertEqual(resp.status_code, 401)

    # ========== PUT (FULL UPDATE) TESTS ==========

    def test_update_transaction_success(self):
        """Test updating transaction fields"""
        resp = self.client.put(
            "/api/v1/transactions/100",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "item": "Updated Item",
                    "amount_sgd": 75.00,
                    "category": "Fashion",
                }
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("transaction", data)
        txn = data["transaction"]
        self.assertEqual(txn["item"], "Updated Item")
        self.assertEqual(float(txn["amount_sgd"]), 75.00)
        self.assertEqual(txn["category"].lower(), "fashion")
        # Unchanged fields should remain
        self.assertEqual(txn["channel"], "online")

    def test_update_transaction_accepts_lowercase_category(self):
        """Frontend sends lowercase category labels; update should still pass."""
        resp = self.client.put(
            "/api/v1/transactions/100",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "item": "Updated Item Lowercase Category",
                    "category": "food",
                }
            },
        )
        self.assertEqual(resp.status_code, 200)
        txn = resp.json()["transaction"]
        self.assertEqual(txn["item"], "Updated Item Lowercase Category")
        self.assertEqual(txn["category"], "food")

    def test_update_transaction_not_found(self):
        """Test updating non-existent transaction"""
        resp = self.client.put(
            "/api/v1/transactions/999",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "item": "Updated",
                }
            },
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        error = data.get("error") or data.get("detail", {}).get("error", {})
        self.assertEqual(error.get("code"), "NOT_FOUND")

    def test_update_transaction_invalid_card(self):
        """Test updating transaction with invalid card_id"""
        resp = self.client.put(
            "/api/v1/transactions/100",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "card_id": 999,  # Card not in wallet
                }
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        error = data.get("error") or data.get("detail", {}).get("error", {})
        self.assertEqual(error.get("code"), "VALIDATION_ERROR")

    def test_update_transaction_clear_nullable_field(self):
        """Test clearing a nullable field (category) by setting to null"""
        # First verify the transaction has a category
        list_resp = self.client.get(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
        )
        txn_before = [t for t in list_resp.json()["transactions"] if t["id"] == "100"][0]
        self.assertEqual(txn_before["category"], "food")

        # Clear the category by setting to null
        resp = self.client.put(
            "/api/v1/transactions/100",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "category": None,
                }
            },
        )
        self.assertEqual(resp.status_code, 200)
        txn = resp.json()["transaction"]
        self.assertIsNone(txn["category"])

    def test_update_transaction_null_non_nullable_field(self):
        """Test that setting non-nullable field to null raises error"""
        resp = self.client.put(
            "/api/v1/transactions/100",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "item": None,  # item is non-nullable
                }
            },
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        error = data.get("error") or data.get("detail", {}).get("error", {})
        self.assertEqual(error.get("code"), "VALIDATION_ERROR")
        self.assertIn("cannot be null", error.get("message", ""))

    # ========== PUT (STATUS ONLY) TESTS ==========

    def test_update_transaction_status(self):
        """Test updating only transaction status"""
        resp = self.client.put(
            "/api/v1/transactions/100/status",
            headers={"x-user-id": "1"},
            json={"status": "deleted_with_card"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        txn = data["transaction"]
        self.assertEqual(txn["status"], "deleted_with_card")
        # Other fields unchanged
        self.assertEqual(txn["item"], "Test Transaction")

    def test_update_status_invalid_value(self):
        """Test updating status with invalid value"""
        resp = self.client.put(
            "/api/v1/transactions/100/status",
            headers={"x-user-id": "1"},
            json={"status": "invalid_status"},
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        error = data.get("error") or data.get("detail", {}).get("error", {})
        self.assertEqual(error.get("code"), "VALIDATION_ERROR")

    # ========== DELETE TESTS ==========

    def test_delete_transaction_success(self):
        """Test deleting a transaction"""
        resp = self.client.delete(
            "/api/v1/transactions/100",
            headers={"x-user-id": "1"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("transaction", data)
        # Should return the deleted transaction
        self.assertEqual(data["transaction"]["id"], "100")

        # Verify it's actually deleted by trying to GET it
        list_resp = self.client.get(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
        )
        transactions = list_resp.json()["transactions"]
        self.assertEqual(len([t for t in transactions if t["id"] == "100"]), 0)

    def test_delete_transaction_not_found(self):
        """Test deleting non-existent transaction"""
        resp = self.client.delete(
            "/api/v1/transactions/999",
            headers={"x-user-id": "1"},
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        error = data.get("error") or data.get("detail", {}).get("error", {})
        self.assertEqual(error.get("code"), "NOT_FOUND")

    def test_delete_transaction_no_user_header(self):
        """Test deleting without user header"""
        resp = self.client.delete("/api/v1/transactions/100")
        self.assertEqual(resp.status_code, 401)

    # ========== FULL CRUD FLOW TEST ==========

    def test_full_crud_flow(self):
        """Test complete CRUD lifecycle: Create → Read → Update → Delete"""
        # 1. CREATE
        create_resp = self.client.post(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "card_id": 10,
                    "amount_sgd": 200.00,
                    "item": "CRUD Test",
                    "channel": "offline",
                    "category": "Entertainment",
                    "is_overseas": False,
                }
            },
        )
        self.assertEqual(create_resp.status_code, 201)
        created_id = create_resp.json()["transaction"]["id"]

        # 2. READ (verify it exists)
        list_resp = self.client.get(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
        )
        transactions = list_resp.json()["transactions"]
        found = [t for t in transactions if t["id"] == created_id]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["item"], "CRUD Test")

        # 3. UPDATE
        update_resp = self.client.put(
            f"/api/v1/transactions/{created_id}",
            headers={"x-user-id": "1"},
            json={
                "transaction": {
                    "item": "CRUD Test Updated",
                    "amount_sgd": 250.00,
                }
            },
        )
        self.assertEqual(update_resp.status_code, 200)
        self.assertEqual(update_resp.json()["transaction"]["item"], "CRUD Test Updated")

        # 4. DELETE
        delete_resp = self.client.delete(
            f"/api/v1/transactions/{created_id}",
            headers={"x-user-id": "1"},
        )
        self.assertEqual(delete_resp.status_code, 200)

        # 5. VERIFY DELETED
        verify_resp = self.client.get(
            "/api/v1/transactions",
            headers={"x-user-id": "1"},
        )
        final_transactions = verify_resp.json()["transactions"]
        still_exists = [t for t in final_transactions if t["id"] == created_id]
        self.assertEqual(len(still_exists), 0)


if __name__ == "__main__":
    unittest.main()
