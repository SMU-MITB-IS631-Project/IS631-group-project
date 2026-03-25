from datetime import date
from decimal import Decimal
from unittest.mock import Mock

import pytest

from app.models.transaction import (
    TransactionCategory,
    TransactionChannel,
    TransactionCreate,
    TransactionStatus,
    TransactionUpdate,
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


def test_resolve_user_sub_missing_raises_unauthorized(transaction_service):
    with pytest.raises(ServiceError) as exc_info:
        transaction_service._resolve_user_sub(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "UNAUTHORIZED"


def test_resolve_user_sub_found_returns_profile_id(transaction_service, mock_db):
    expected_profile = UserProfile(id=3, username="alice", password_hash="pw", cognito_sub="sub-123")
    mock_db.query.return_value.filter.return_value.first.return_value = expected_profile

    resolved = transaction_service._resolve_user_sub("sub-123")

    assert resolved == 3
    mock_db.query.assert_called_once_with(UserProfile)
    mock_db.query.return_value.filter.return_value.first.assert_called_once()


def test_resolve_user_sub_not_found_raises_service_error(transaction_service, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ServiceError) as exc_info:
        transaction_service._resolve_user_sub("missing-sub")

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
    assert data["user_id"] == 4


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

    transaction_service._resolve_user_sub = Mock(return_value=1)
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
    transaction_service._resolve_user_sub.assert_called_once_with("1")
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

    transaction_service._resolve_user_sub = Mock(return_value=1)
    transaction_service._card_exists_in_wallet = Mock(return_value=False)

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.create_transaction("1", payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_get_user_transactions_returns_rows_desc_by_default(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)

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
    transaction_service._resolve_user_sub = Mock(return_value=1)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    row = transaction_service.get_transaction_by_id(10, "1")

    assert row is None


def test_update_transaction_success(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)
    transaction_service._card_exists_in_wallet = Mock(return_value=True)

    existing = _build_transaction(txn_id=10, item="Old Item", amount_sgd=Decimal("12.50"))
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    updated = transaction_service.update_transaction(
        "1",
        10,
        TransactionUpdate(
            item="Updated Item",
            amount_sgd=Decimal("20.00"),
            category=TransactionCategory.fashion,
        ),
    )

    assert updated["item"] == "Updated Item"
    assert updated["amount_sgd"] == 20.0
    assert updated["category"] == "fashion"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(existing)


def test_update_transaction_updates_channel_overseas_and_date(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)

    existing = _build_transaction(
        txn_id=11,
        channel=TransactionChannel.online,
        is_overseas=False,
        txn_date=date(2026, 2, 18),
    )
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    updated = transaction_service.update_transaction(
        "1",
        11,
        TransactionUpdate(
            channel=TransactionChannel.offline,
            is_overseas=True,
            transaction_date=date(2026, 2, 25),
        ),
    )

    assert updated["channel"] == "offline"
    assert updated["is_overseas"] is True
    assert updated["date"] == "2026-02-25"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(existing)


def test_delete_transaction_success(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)
    existing = _build_transaction(txn_id=10)
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    deleted = transaction_service.delete_transaction("1", 10)

    assert deleted["id"] == "10"
    mock_db.delete.assert_called_once_with(existing)
    mock_db.commit.assert_called_once()


def test_delete_transaction_not_found_raises_service_error(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.delete_transaction("1", 999)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOT_FOUND"


def test_card_exists_in_wallet_returns_true_when_record_exists(transaction_service, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = (101,)

    exists = transaction_service._card_exists_in_wallet(1, 101)

    assert exists is True


def test_card_exists_in_wallet_returns_false_when_record_missing(transaction_service, mock_db):
    mock_db.query.return_value.filter.return_value.first.return_value = None

    exists = transaction_service._card_exists_in_wallet(1, 999)

    assert exists is False


def test_get_user_transactions_returns_rows_asc_when_requested(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)

    base_query = Mock()
    filtered_query = Mock()
    ordered_query = Mock()

    mock_db.query.return_value = base_query
    base_query.filter.return_value = filtered_query
    filtered_query.order_by.return_value = ordered_query
    ordered_query.all.return_value = [
        _build_transaction(txn_id=1, txn_date=date(2026, 2, 10)),
        _build_transaction(txn_id=2, txn_date=date(2026, 2, 20)),
    ]

    rows = transaction_service.get_user_transactions("1", sort_by_date_desc=False)

    assert [row["id"] for row in rows] == ["1", "2"]
    filtered_query.order_by.assert_called_once()
    ordered_query.all.assert_called_once()


def test_update_transaction_not_found_raises_service_error(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.update_transaction("1", 999, TransactionUpdate(item="Updated"))

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOT_FOUND"


def test_update_transaction_card_id_not_in_wallet_raises_service_error(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)
    transaction_service._parse_card_id = Mock(return_value=202)
    transaction_service._card_exists_in_wallet = Mock(return_value=False)

    existing = _build_transaction(txn_id=10, card_id=101)
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    with pytest.raises(ServiceError) as exc_info:
        transaction_service.update_transaction("1", 10, TransactionUpdate(card_id=202))

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_update_transaction_card_id_changed_and_valid_wallet_updates_card_id(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)
    transaction_service._parse_card_id = Mock(return_value=202)
    transaction_service._card_exists_in_wallet = Mock(return_value=True)

    existing = _build_transaction(txn_id=10, card_id=101)
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    updated = transaction_service.update_transaction("1", 10, TransactionUpdate(card_id=202, item="New"))

    assert updated["card_id"] == "202"
    assert updated["item"] == "New"
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(existing)


def test_get_user_transactions_returns_rows_without_order_when_sort_flag_is_none(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)

    base_query = Mock()
    filtered_query = Mock()

    mock_db.query.return_value = base_query
    base_query.filter.return_value = filtered_query
    filtered_query.all.return_value = [
        _build_transaction(txn_id=3, txn_date=date(2026, 2, 15)),
    ]

    rows = transaction_service.get_user_transactions("1", sort_by_date_desc=None)

    assert [row["id"] for row in rows] == ["3"]
    filtered_query.order_by.assert_not_called()
    filtered_query.all.assert_called_once()


def test_update_transaction_card_id_same_value_skips_wallet_lookup(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)
    transaction_service._parse_card_id = Mock(return_value=101)
    transaction_service._card_exists_in_wallet = Mock(return_value=True)

    existing = _build_transaction(txn_id=10, card_id=101, item="Old")
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    updated = transaction_service.update_transaction("1", 10, TransactionUpdate(card_id=101, item="Same Card"))

    assert updated["card_id"] == "101"
    assert updated["item"] == "Same Card"
    transaction_service._card_exists_in_wallet.assert_called_once_with(1, 101)


def test_get_transaction_by_id_success_returns_row(transaction_service, mock_db):
    transaction_service._resolve_user_sub = Mock(return_value=1)
    existing = _build_transaction(txn_id=44, user_id=1, item="Bus Fare")
    mock_db.query.return_value.filter.return_value.first.return_value = existing

    row = transaction_service.get_transaction_by_id(44, "sub-1")

    assert row is not None
    assert row["id"] == "44"
    assert row["item"] == "Bus Fare"
