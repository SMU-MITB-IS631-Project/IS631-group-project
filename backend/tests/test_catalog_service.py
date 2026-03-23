import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from app.services.catalog_service import CatalogService
from app.services.errors import ServiceError
from app.models.card_catalogue import CardCatalogue
from app.models.card_catalogue import CardBonusRuleUpdate, CardRewardUpdatePayload
from app.models.card_catalogue import CardCatalogueCreate, BankEnum, BenefitTypeEnum, StatusEnum
from app.models.card_bonus_category import BonusCategory, CardBonusCategory
from app.models.user_owned_cards import UserOwnedCard

@pytest.fixture
def mock_db():
    return Mock()

@pytest.fixture
def catalog_service(mock_db):
    return CatalogService(db=mock_db)

def test_get_all_card_catalogue_success(catalog_service, mock_db):
    # Arrange
    mock_db.query.return_value.all.return_value = [
        CardCatalogue(card_id=1, bank="DBS", card_name="DBS Altitude",benefit_type="miles", base_benefit_rate="1.5", status="valid"),
        CardCatalogue(card_id=2, bank="CITI", card_name="CITI PremierMiles", benefit_type="miles", base_benefit_rate="1.2", status="valid"),
        CardCatalogue(card_id=3, bank="UOB", card_name="UOB ONE Miles", benefit_type="cashback", base_benefit_rate="0.005", status="valid")
    ]

    # Act
    result = catalog_service.get_catalog()

    # Assert
    assert len(result) == 3
    assert result[0].card_name == "DBS Altitude"
    assert result[1].bank == "CITI"
    assert result[2].benefit_type == "cashback"
    # Ensure the correct calls were made
    mock_db.query.assert_called_once_with(CardCatalogue)
    mock_db.query.return_value.all.assert_called_once()


def test_get_all_card_catalogue_empty_result(catalog_service, mock_db):
    mock_db.query.return_value.all.return_value = []

    result = catalog_service.get_catalog()

    assert result == []
    mock_db.query.assert_called_once_with(CardCatalogue)
    mock_db.query.return_value.all.assert_called_once()


@pytest.mark.parametrize(
    "raw_value, expected",
    [
        ("1.5000", "1.5"),
        (Decimal("0.0000"), "0"),
        (2, "2"),
        ("3.1415900", "3.14159"),
    ],
)
def test_decimal_to_string_normalizes_values(catalog_service, raw_value, expected):
    assert catalog_service._decimal_to_string(raw_value) == expected


def test_diff_snapshots_detects_added_removed_and_changed_categories(catalog_service):
    old_snapshot = {
        "base_benefit_rate": "1",
        "bonus_rules": {
            "Food": {
                "bonus_benefit_rate": "2",
                "bonus_cap_in_dollar": 100,
                "bonus_minimum_spend_in_dollar": 10,
            },
            "Transport": {
                "bonus_benefit_rate": "3",
                "bonus_cap_in_dollar": 200,
                "bonus_minimum_spend_in_dollar": 20,
            },
        },
    }
    new_snapshot = {
        "base_benefit_rate": "1.5",
        "bonus_rules": {
            "Food": {
                "bonus_benefit_rate": "2.5",
                "bonus_cap_in_dollar": 150,
                "bonus_minimum_spend_in_dollar": 10,
            },
            "Entertainment": {
                "bonus_benefit_rate": "4",
                "bonus_cap_in_dollar": 500,
                "bonus_minimum_spend_in_dollar": 0,
            },
        },
    }

    changes = catalog_service._diff_snapshots(old_snapshot, new_snapshot)

    assert changes["base_benefit_rate"] == {"old": "1", "new": "1.5"}
    assert changes["bonus_rules"]["added_categories"] == ["Entertainment"]
    assert changes["bonus_rules"]["removed_categories"] == ["Transport"]
    assert changes["bonus_rules"]["changed_categories"]["Food"] == {
        "bonus_benefit_rate": {"old": "2", "new": "2.5"},
        "bonus_cap_in_dollar": {"old": 100, "new": 150},
    }


def test_snapshot_card_rewards_serializes_bonus_rows(catalog_service):
    card = CardCatalogue(card_id=1, card_name="Card", base_benefit_rate=Decimal("1.5000"))
    bonus_rows = [
        CardBonusCategory(
            card_id=1,
            bonus_category=BonusCategory.Transport,
            bonus_benefit_rate=Decimal("3.2500"),
            bonus_cap_in_dollar=999,
            bonus_minimum_spend_in_dollar=20,
        )
    ]

    snapshot = catalog_service._snapshot_card_rewards(card, bonus_rows)

    assert snapshot == {
        "base_benefit_rate": "1.5",
        "bonus_rules": {
            "Transport": {
                "bonus_benefit_rate": "3.25",
                "bonus_cap_in_dollar": 999,
                "bonus_minimum_spend_in_dollar": 20,
            }
        },
    }


def test_update_card_rewards_not_found_raises_service_error(catalog_service, mock_db):
    card_query = Mock()
    card_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = card_query

    payload = CardRewardUpdatePayload(effective_date=date(2026, 1, 1))

    with pytest.raises(ServiceError) as exc_info:
        catalog_service.update_card_rewards(card_id=999, payload=payload)

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOT_FOUND"
    assert exc_info.value.details == {"card_id": 999}
    mock_db.commit.assert_not_called()


def test_update_card_rewards_no_changes_creates_no_notifications(catalog_service, mock_db):
    card = CardCatalogue(card_id=1, card_name="DBS Altitude", base_benefit_rate=Decimal("1.5"))
    existing_bonus_rows = [
        CardBonusCategory(
            card_id=1,
            bonus_category=BonusCategory.Food,
            bonus_benefit_rate=Decimal("2.0"),
            bonus_cap_in_dollar=100,
            bonus_minimum_spend_in_dollar=0,
        )
    ]

    card_query = Mock()
    card_query.filter.return_value.first.return_value = card

    bonus_query = Mock()
    bonus_query.filter.return_value.all.side_effect = [existing_bonus_rows, existing_bonus_rows]

    def query_side_effect(model):
        if model is CardCatalogue:
            return card_query
        if model is CardBonusCategory:
            return bonus_query
        if model is UserOwnedCard.user_id:
            raise AssertionError("Owner query should not be executed when there are no changes.")
        raise AssertionError(f"Unexpected query model: {model}")

    mock_db.query.side_effect = query_side_effect

    payload = CardRewardUpdatePayload(effective_date=date(2026, 1, 1))
    result = catalog_service.update_card_rewards(card_id=1, payload=payload)

    assert result["card_id"] == 1
    assert result["card_name"] == "DBS Altitude"
    assert result["effective_date"] == "2026-01-01"
    assert result["changed_fields"] == {}
    assert result["notifications_created"] == 0
    mock_db.add.assert_not_called()
    mock_db.delete.assert_not_called()
    mock_db.commit.assert_called_once()


def test_update_card_rewards_updates_rules_and_creates_notifications(catalog_service, mock_db):
    card = CardCatalogue(card_id=1, card_name="DBS Altitude", base_benefit_rate=Decimal("1.5"))
    old_food = CardBonusCategory(
        card_id=1,
        bonus_category=BonusCategory.Food,
        bonus_benefit_rate=Decimal("2.0"),
        bonus_cap_in_dollar=100,
        bonus_minimum_spend_in_dollar=0,
    )
    old_transport = CardBonusCategory(
        card_id=1,
        bonus_category=BonusCategory.Transport,
        bonus_benefit_rate=Decimal("1.2"),
        bonus_cap_in_dollar=200,
        bonus_minimum_spend_in_dollar=20,
    )

    updated_food = CardBonusCategory(
        card_id=1,
        bonus_category=BonusCategory.Food,
        bonus_benefit_rate=Decimal("3.0"),
        bonus_cap_in_dollar=300,
        bonus_minimum_spend_in_dollar=10,
    )
    added_entertainment = CardBonusCategory(
        card_id=1,
        bonus_category=BonusCategory.Entertainment,
        bonus_benefit_rate=Decimal("4.0"),
        bonus_cap_in_dollar=400,
        bonus_minimum_spend_in_dollar=0,
    )

    card_query = Mock()
    card_query.filter.return_value.first.return_value = card

    bonus_query = Mock()
    bonus_query.filter.return_value.all.side_effect = [
        [old_food, old_transport],
        [updated_food, added_entertainment],
    ]

    owner_query = Mock()
    owner_query.filter.return_value.distinct.return_value.all.return_value = [
        Mock(user_id=10),
        Mock(user_id=11),
    ]

    def query_side_effect(model):
        if model is CardCatalogue:
            return card_query
        if model is CardBonusCategory:
            return bonus_query
        if model is UserOwnedCard.user_id:
            return owner_query
        raise AssertionError(f"Unexpected query model: {model}")

    mock_db.query.side_effect = query_side_effect

    payload = CardRewardUpdatePayload(
        base_benefit_rate=Decimal("2.0"),
        bonus_rules=[
            CardBonusRuleUpdate(
                bonus_category=BonusCategory.Food,
                bonus_benefit_rate=Decimal("3.0"),
                bonus_cap_in_dollar=300,
                bonus_minimum_spend_in_dollar=10,
            ),
            CardBonusRuleUpdate(
                bonus_category=BonusCategory.Entertainment,
                bonus_benefit_rate=Decimal("4.0"),
                bonus_cap_in_dollar=400,
                bonus_minimum_spend_in_dollar=0,
            ),
        ],
        effective_date=date(2026, 2, 1),
    )

    result = catalog_service.update_card_rewards(card_id=1, payload=payload)

    assert card.base_benefit_rate == Decimal("2.0")
    mock_db.delete.assert_called_once_with(old_transport)

    added_objects = [call.args[0] for call in mock_db.add.call_args_list]
    assert len(added_objects) == 3
    assert sum(isinstance(obj, CardBonusCategory) for obj in added_objects) == 1
    assert result["card_id"] == 1
    assert result["effective_date"] == "2026-02-01"
    assert result["notifications_created"] == 2
    assert "base_benefit_rate" in result["changed_fields"]
    assert "bonus_rules" in result["changed_fields"]
    mock_db.flush.assert_called_once()
    mock_db.commit.assert_called_once()


def test_update_card_rewards_changes_without_owners_creates_zero_notifications(catalog_service, mock_db):
    card = CardCatalogue(card_id=1, card_name="DBS Altitude", base_benefit_rate=Decimal("1.5"))

    card_query = Mock()
    card_query.filter.return_value.first.return_value = card

    bonus_query = Mock()
    bonus_query.filter.return_value.all.return_value = []

    owner_query = Mock()
    owner_query.filter.return_value.distinct.return_value.all.return_value = []

    def query_side_effect(model):
        if model is CardCatalogue:
            return card_query
        if model is CardBonusCategory:
            return bonus_query
        if model is UserOwnedCard.user_id:
            return owner_query
        raise AssertionError(f"Unexpected query model: {model}")

    mock_db.query.side_effect = query_side_effect

    payload = CardRewardUpdatePayload(base_benefit_rate=Decimal("2.0"), effective_date=date(2026, 3, 1))
    result = catalog_service.update_card_rewards(card_id=1, payload=payload)

    assert result["changed_fields"] == {"base_benefit_rate": {"old": "1.5", "new": "2"}}
    assert result["notifications_created"] == 0
    mock_db.commit.assert_called_once()


def test_create_card_success(catalog_service, mock_db):
    create_payload = CardCatalogueCreate(
        card_id=42,
        bank=BankEnum.DBS,
        card_name="DBS New Card",
        benefit_type=BenefitTypeEnum.miles,
        base_benefit_rate=Decimal("1.2"),
        status=StatusEnum.valid,
    )

    card_query = Mock()
    card_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = card_query

    created = catalog_service.create_card(create_payload)

    assert isinstance(created, CardCatalogue)
    assert created.bank == BankEnum.DBS
    assert created.card_name == "DBS New Card"
    mock_db.add.assert_called_once_with(created)
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(created)


def test_create_card_duplicate_raises_service_error(catalog_service, mock_db):
    create_payload = CardCatalogueCreate(
        card_id=7,
        bank=BankEnum.CITI,
        card_name="CITI Existing",
        benefit_type=BenefitTypeEnum.cashback,
        base_benefit_rate=Decimal("0.8"),
        status=StatusEnum.valid,
    )

    existing_card = CardCatalogue(card_id=7, bank=BankEnum.CITI, card_name="CITI Existing")
    card_query = Mock()
    card_query.filter.return_value.first.return_value = existing_card
    mock_db.query.return_value = card_query

    with pytest.raises(ServiceError) as exc_info:
        catalog_service.create_card(create_payload)

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "CARD_EXISTS"
    assert exc_info.value.details == {"bank": "BankEnum.CITI", "card_name": "CITI Existing"}
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


def test_delete_card_success(catalog_service, mock_db):
    existing_card = CardCatalogue(card_id=99, card_name="Delete Me")
    card_query = Mock()
    card_query.filter.return_value.first.return_value = existing_card
    mock_db.query.return_value = card_query

    deleted = catalog_service.delete_card(99)

    assert deleted is True
    mock_db.delete.assert_called_once_with(existing_card)
    mock_db.commit.assert_called_once()


def test_delete_card_not_found_returns_false(catalog_service, mock_db):
    card_query = Mock()
    card_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = card_query

    deleted = catalog_service.delete_card(500)

    assert deleted is False
    mock_db.delete.assert_not_called()
    mock_db.commit.assert_not_called()