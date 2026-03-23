from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.models.transaction import (
    TransactionCategory,
    TransactionChannel,
    TransactionCreate,
    TransactionStatus,
    UserTransaction,
)
from app.models.user_profile import UserProfile
from app.services.errors import ServiceError
from app.services.transaction_service import TransactionService


@pytest.fixture
def mock_db():
    return Mock()


@pytest.fixture
def transaction_service(mock_db):
    return TransactionService(db=mock_db)


def _build_transaction(
    *,
    txn_id: int = 10,
    user_id: int = 1,
    card_id: int = 101,
    amount_sgd: Decimal = Decimal("12.50"),
    item: str = "GrabFood",
    channel: TransactionChannel = TransactionChannel.online,
    category: TransactionCategory | None = TransactionCategory.food,
    is_overseas: bool = False,
    txn_date: date = date(2026, 2, 18),
    status: TransactionStatus = TransactionStatus.Active,
) -> UserTransaction:
    return UserTransaction(
        id=txn_id,
        user_id=user_id,
        card_id=card_id,
        amount_sgd=amount_sgd,
        item=item,
        channel=channel,
        category=category,
        is_overseas=is_overseas,
        transaction_date=txn_date,
        status=status,
    )


def test_resolve_user_id_numeric_string_returns_int(transaction_service):
    assert transaction_service._resolve_user_id("12") == 12


def test_resolve_user_id_prefixed_string_returns_int(transaction_service):
    assert transaction_service._resolve_user_id("u_007") == 7


def test_resolve_user_id_username_found_returns_profile_id(transaction_service, mock_db):
    expected_profile = UserProfile(id=3, username="alice", password_hash="pw")
    mock_db.query.return_value.filter.return_value.first.return_value = expected_profile

    resolved = transaction_service._resolve_user_id("alice")

    assert resolved == 3
    mock_db.query.assert_called_once_with(UserProfile)
    mock_db.query.return_value.filter.return_value.first.assert_called_once()


def test_resolve_user_id_username_not_found_raises_service_error(transaction_service, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ServiceError) as exc_info:
        transaction_service._resolve_user_id("missing-user")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOT_FOUND"


def test_parse_card_id_accepts_int_and_numeric_string(transaction_service):
    assert transaction_service._parse_card_id(101) == 101
    assert transaction_service._parse_card_id("101") == 101


def test_parse_card_id_invalid_raises_service_error(transaction_service):
    with pytest.raises(ServiceError) as exc_info:
        transaction_service._parse_card_id("abc")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_transaction_to_dict_formats_response(transaction_service):
    transaction = _build_transaction(
        txn_id=88,
        user_id=4,
        card_id=200,
        amount_sgd=Decimal("50.00"),
        category=TransactionCategory.entertainment,
        status=TransactionStatus.DeletedWithCard,
    )

    data = transaction_service._transaction_to_dict(transaction)

    assert data["id"] == "88"
    assert data["date"] == "2026-02-18"
    assert data["amount_sgd"] == 50.0
    assert data["card_id"] == "200"
    assert data["channel"] == "online"
    assert data["category"] == "entertainment"
    assert data["status"] == "deleted_with_card"
    assert data["user_id"] == "u_004"


def test_create_transaction_success(transaction_service, mock_db):
    payload = TransactionCreate(
        card_id=101,
        amount_sgd=Decimal("12.50"),
        item="Lunch",
        channel=TransactionChannel.online,
        category=TransactionCategory.food,
        is_overseas=False,
        date=date(2026, 2, 18),
    )

    transaction_service._resolve_user_id = Mock(return_value=1)
    transaction_service._card_exists_in_wallet = Mock(return_value=True)

    created_record = _build_transaction(
        txn_id=501,
        user_id=1,
        card_id=101,
        amount_sgd=Decimal("12.50"),
        item="Lunch",
        channel=TransactionChannel.online,
        category=TransactionCategory.food,
        txn_date=date(2026, 2, 18),
        status=TransactionStatus.Active,
    )

    def refresh_side_effect(record):
        record.id = created_record.id
        record.status = TransactionStatus.Active

    mock_db.refresh.side_effect = refresh_side_effect

    result = transaction_service.create_transaction("1", payload)

    assert result["id"] == "501"
    assert result["item"] == "Lunch"
    assert result["card_id"] == "101"
    assert result["status"] == "active"
    transaction_service._resolve_user_id.assert_called_once_with("1")
    transaction_service._card_exists_in_wallet.assert_called_once_with(1, 101)
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()


def test_create_transaction_invalid_card_raises_service_error(transaction_service):
    payload = TransactionCreate(
        card_id=999,
        amount_sgd=Decimal("12.50"),
        item="Lunch",
        channel=TransactionChannel.online,
        is_overseas=False,
        date=date(2026, 2, 18),
    )

    transaction_service._resolve_user_id = Mock(return_value=1)
    transaction_service._card_exists_in_wallet = Mock(return_value=False)

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.create_transaction("1", payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_get_user_transactions_returns_rows_desc_by_default(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)

    base_query = Mock()
    filtered_query = Mock()
    ordered_query = Mock()

    mock_db.query.return_value = base_query
    base_query.filter.return_value = filtered_query
    filtered_query.order_by.return_value = ordered_query
    ordered_query.all.return_value = [
        _build_transaction(txn_id=2, txn_date=date(2026, 2, 20)),
        _build_transaction(txn_id=1, txn_date=date(2026, 2, 10)),
    ]

    rows = transaction_service.get_user_transactions("1")

    assert [row["id"] for row in rows] == ["2", "1"]
    filtered_query.order_by.assert_called_once()
    ordered_query.all.assert_called_once()


def test_get_transaction_by_id_not_found_returns_none(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    row = transaction_service.get_transaction_by_id(10, "1")

    assert row is None


def test_update_transaction_status_success(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)
    existing = _build_transaction(txn_id=10, status=TransactionStatus.Active)
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    updated = transaction_service.update_transaction_status("1", 10, "deleted_with_card")

    assert updated["id"] == "10"
    assert updated["status"] == "deleted_with_card"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(existing)


def test_update_transaction_status_invalid_value_raises_service_error(transaction_service):
    transaction_service._resolve_user_id = Mock(return_value=1)

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.update_transaction_status("1", 10, "invalid_status")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_bulk_update_transaction_status_success_returns_count(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)
    mock_db.query.return_value.filter.return_value.update.return_value = 2

    count = transaction_service.bulk_update_transaction_status("1", [10, 11], "deleted_with_card")

    assert count == 2
    mock_db.commit.assert_called_once()


def test_update_transaction_non_nullable_field_none_raises_service_error(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)
    existing = _build_transaction(txn_id=10)
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.update_transaction("1", 10, {"item": None})

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_update_transaction_success(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)
    transaction_service._card_exists_in_wallet = Mock(return_value=True)

    existing = _build_transaction(txn_id=10, item="Old Item", amount_sgd=Decimal("12.50"))
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    updated = transaction_service.update_transaction(
        "1",
        10,
        {
            "item": "Updated Item",
            "amount_sgd": Decimal("20.00"),
            "category": TransactionCategory.fashion,
        },
    )

    assert updated["item"] == "Updated Item"
    assert updated["amount_sgd"] == 20.0
    assert updated["category"] == "fashion"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(existing)


def test_delete_transaction_success(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)
    existing = _build_transaction(txn_id=10)
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    deleted = transaction_service.delete_transaction("1", 10)

    assert deleted["id"] == "10"
    mock_db.delete.assert_called_once_with(existing)
    mock_db.commit.assert_called_once()


def test_delete_transaction_not_found_raises_service_error(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.delete_transaction("1", 999)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOT_FOUND"


def test_update_transactions_by_card_id_success(transaction_service, mock_db):
    transaction_service._resolve_user_id = Mock(return_value=1)
    mock_db.query.return_value.filter.return_value.update.return_value = 3

    count = transaction_service.update_transactions_by_card_id("1", 101, "deleted_with_card")

    assert count == 3
    mock_db.commit.assert_called_once()


def test_update_transactions_by_card_id_invalid_status_raises_service_error(transaction_service):
    transaction_service._resolve_user_id = Mock(return_value=1)

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.update_transactions_by_card_id("1", 101, "bad_status")

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"
