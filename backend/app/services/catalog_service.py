from decimal import Decimal
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.models.card_bonus_category import CardBonusCategory
from app.models.card_catalogue import CardCatalogue, CardRewardUpdatePayload
from app.models.card_change_notification import CardChangeNotification
from app.models.user_owned_cards import UserOwnedCard
from app.services.errors import ServiceError

class CatalogService:
    def __init__(self, db: Session):
        self.db = db

    def get_catalog(self):
        """Retrieve all cards from the database."""
        return self.db.query(CardCatalogue).all()

    def _decimal_to_string(self, value: Any) -> str:
        dec = Decimal(str(value))
        text = format(dec, "f")
        normalized = text.rstrip("0").rstrip(".")
        return normalized if normalized else "0"

    def _snapshot_card_rewards(self, card: CardCatalogue, bonus_rows: list[CardBonusCategory]) -> Dict[str, Any]:
        return {
            "base_benefit_rate": self._decimal_to_string(card.base_benefit_rate),
            "bonus_rules": {
                row.bonus_category.value: {
                    "bonus_benefit_rate": self._decimal_to_string(row.bonus_benefit_rate),
                    "bonus_cap_in_dollar": row.bonus_cap_in_dollar,
                    "bonus_minimum_spend_in_dollar": row.bonus_minimum_spend_in_dollar,
                }
                for row in bonus_rows
            },
        }

    def _diff_snapshots(self, old_snapshot: Dict[str, Any], new_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        changes: Dict[str, Any] = {}

        if old_snapshot["base_benefit_rate"] != new_snapshot["base_benefit_rate"]:
            changes["base_benefit_rate"] = {
                "old": old_snapshot["base_benefit_rate"],
                "new": new_snapshot["base_benefit_rate"],
            }

        old_rules = old_snapshot["bonus_rules"]
        new_rules = new_snapshot["bonus_rules"]

        removed_categories = sorted(set(old_rules.keys()) - set(new_rules.keys()))
        added_categories = sorted(set(new_rules.keys()) - set(old_rules.keys()))
        changed_categories: Dict[str, Any] = {}

        for category in sorted(set(old_rules.keys()) & set(new_rules.keys())):
            per_category_changes: Dict[str, Any] = {}
            old_values = old_rules[category]
            new_values = new_rules[category]
            for field_name in ("bonus_benefit_rate", "bonus_cap_in_dollar", "bonus_minimum_spend_in_dollar"):
                if old_values[field_name] != new_values[field_name]:
                    per_category_changes[field_name] = {
                        "old": old_values[field_name],
                        "new": new_values[field_name],
                    }
            if per_category_changes:
                changed_categories[category] = per_category_changes

        if removed_categories or added_categories or changed_categories:
            changes["bonus_rules"] = {
                "added_categories": added_categories,
                "removed_categories": removed_categories,
                "changed_categories": changed_categories,
            }

        return changes

    def update_card_rewards(self, card_id: int, payload: CardRewardUpdatePayload) -> Dict[str, Any]:
        card = self.db.query(CardCatalogue).filter(CardCatalogue.card_id == card_id).first()
        if not card:
            raise ServiceError(404, "NOT_FOUND", "Card not found.", {"card_id": card_id})

        bonus_rows = (
            self.db.query(CardBonusCategory)
            .filter(CardBonusCategory.card_id == card_id)
            .all()
        )
        old_snapshot = self._snapshot_card_rewards(card, bonus_rows)

        if payload.base_benefit_rate is not None:
            card.base_benefit_rate = Decimal(str(payload.base_benefit_rate))

        if payload.bonus_rules is not None:
            existing_by_category = {
                row.bonus_category.value: row
                for row in bonus_rows
            }
            incoming_by_category = {
                rule.bonus_category.value: rule
                for rule in payload.bonus_rules
            }

            for category, row in existing_by_category.items():
                if category not in incoming_by_category:
                    self.db.delete(row)

            for category, rule in incoming_by_category.items():
                existing = existing_by_category.get(category)
                if existing:
                    existing.bonus_benefit_rate = Decimal(str(rule.bonus_benefit_rate))
                    existing.bonus_cap_in_dollar = rule.bonus_cap_in_dollar
                    existing.bonus_minimum_spend_in_dollar = rule.bonus_minimum_spend_in_dollar
                else:
                    self.db.add(
                        CardBonusCategory(
                            card_id=card_id,
                            bonus_category=rule.bonus_category,
                            bonus_benefit_rate=Decimal(str(rule.bonus_benefit_rate)),
                            bonus_cap_in_dollar=rule.bonus_cap_in_dollar,
                            bonus_minimum_spend_in_dollar=rule.bonus_minimum_spend_in_dollar,
                        )
                    )

        self.db.flush()

        updated_bonus_rows = (
            self.db.query(CardBonusCategory)
            .filter(CardBonusCategory.card_id == card_id)
            .all()
        )
        new_snapshot = self._snapshot_card_rewards(card, updated_bonus_rows)
        changed_fields = self._diff_snapshots(old_snapshot, new_snapshot)

        notifications_created = 0
        if changed_fields:
            owner_user_ids = (
                self.db.query(UserOwnedCard.user_id)
                .filter(UserOwnedCard.card_id == card_id)
                .distinct()
                .all()
            )

            for owner_row in owner_user_ids:
                self.db.add(
                    CardChangeNotification(
                        user_id=owner_row.user_id,
                        card_id=card_id,
                        card_name=card.card_name,
                        changed_fields=changed_fields,
                        effective_date=payload.effective_date,
                        is_read=False,
                    )
                )
                notifications_created += 1

        self.db.commit()
        return {
            "card_id": card.card_id,
            "card_name": card.card_name,
            "effective_date": payload.effective_date.isoformat(),
            "changed_fields": changed_fields,
            "notifications_created": notifications_created,
        }