import sys
import unittest
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import Base  # noqa: E402
from app.services.errors import ServiceError  # noqa: E402
from app.models.card_catalogue import (  # noqa: E402
	BankEnum,
	BenefitTypeEnum,
	CardCatalogue,
	StatusEnum,
)
from app.models.transaction import UserTransaction  # noqa: F401,E402
from app.models.user_owned_cards import (  # noqa: E402
	UserOwnedCard,
	UserOwnedCardCreate,
	UserOwnedCardStatus,
	UserOwnedCardUpdate,
)
from app.models.user_profile import BenefitsPreference, UserProfile  # noqa: E402
from app.services.user_card_service import UserCardManagementService  # noqa: E402


class UserCardServiceTests(unittest.TestCase):
	def setUp(self):
		engine = create_engine(
			"sqlite:///:memory:",
			connect_args={"check_same_thread": False},
			poolclass=StaticPool,
		)
		Base.metadata.create_all(bind=engine)
		self.Session = sessionmaker(bind=engine)

		with self.Session() as db:
			db.add(
				UserProfile(
					id=1,
					username="alice",
					email="alice@example.com",
					cognito_sub="sub-alice",
					benefits_preference=BenefitsPreference.no_preference,
				)
			)
			db.add(
				CardCatalogue(
					card_id=101,
					bank=BankEnum.DBS,
					card_name="Card 101",
					benefit_type=BenefitTypeEnum.cashback,
					base_benefit_rate=1.0,
					status=StatusEnum.valid,
				)
			)
			db.add(
				CardCatalogue(
					card_id=102,
					bank=BankEnum.CITI,
					card_name="Card 102",
					benefit_type=BenefitTypeEnum.miles,
					base_benefit_rate=1.2,
					status=StatusEnum.valid,
				)
			)
			db.commit()

	def test_get_user_id_by_cognito_sub_found(self):
		with self.Session() as db:
			service = UserCardManagementService(db)
			user_id = service.get_user_id_by_cognito_sub("sub-alice")

			self.assertEqual(user_id, 1)

	def test_get_user_id_by_cognito_sub_not_found(self):
		with self.Session() as db:
			service = UserCardManagementService(db)
			user_id = service.get_user_id_by_cognito_sub("missing-sub")

			self.assertIsNone(user_id)

	def test_get_user_cards_empty(self):
		with self.Session() as db:
			service = UserCardManagementService(db)
			cards = service.get_user_cards("sub-alice")

			self.assertEqual(cards, [])

	def test_get_user_cards_user_not_found(self):
		with self.Session() as db:
			service = UserCardManagementService(db)

			with self.assertRaises(ServiceError) as context:
				service.get_user_cards("missing-sub")

			self.assertEqual(context.exception.status_code, 404)
			self.assertEqual(context.exception.message, "User not found.")

	def test_add_user_card_success(self):
		with self.Session() as db:
			service = UserCardManagementService(db)
			card_data = UserOwnedCardCreate(
				card_id=101,
				card_expiry_date=date(2028, 12, 31),
				billing_cycle_refresh_date=date(2026, 4, 30),
				billing_cycle_refresh_day_of_month=15,
			)

			created = service.add_user_card("sub-alice", 101, card_data)

			self.assertIsNotNone(created.id)
			self.assertEqual(created.user_id, 1)
			self.assertEqual(created.card_id, 101)
			self.assertEqual(created.card_expiry_date, date(2028, 12, 31))
			self.assertEqual(created.billing_cycle_refresh_date, date(2026, 4, 30))
			self.assertEqual(created.billing_cycle_refresh_day_of_month, 15)
			self.assertEqual(created.status, UserOwnedCardStatus.Active)

	def test_add_user_card_duplicate(self):
		with self.Session() as db:
			service = UserCardManagementService(db)
			payload = UserOwnedCardCreate(card_id=101)
			service.add_user_card("sub-alice", 101, payload)

			with self.assertRaises(ServiceError) as context:
				service.add_user_card("sub-alice", 101, payload)

			self.assertEqual(context.exception.status_code, 400)
			self.assertEqual(context.exception.message, "User already owns this card.")

	def test_add_user_card_user_not_found(self):
		with self.Session() as db:
			service = UserCardManagementService(db)

			with self.assertRaises(ServiceError) as context:
				service.add_user_card("missing-sub", 101, UserOwnedCardCreate(card_id=101))

			self.assertEqual(context.exception.status_code, 404)
			self.assertEqual(context.exception.message, "User not found.")

	def test_update_user_card_success(self):
		with self.Session() as db:
			service = UserCardManagementService(db)
			service.add_user_card("sub-alice", 101, UserOwnedCardCreate(card_id=101))

			updated = service.update_user_card(
				"sub-alice",
				101,
				UserOwnedCardUpdate(
					card_expiry_date=date(2029, 1, 31),
					billing_cycle_refresh_date=date(2026, 5, 31),
					status=UserOwnedCardStatus.Inactive,
				),
			)

			self.assertEqual(updated.card_expiry_date, date(2029, 1, 31))
			self.assertEqual(updated.billing_cycle_refresh_date, date(2026, 5, 31))
			self.assertEqual(updated.status, UserOwnedCardStatus.Inactive)

	def test_update_user_card_ignores_non_model_field(self):
		with self.Session() as db:
			service = UserCardManagementService(db)
			created = service.add_user_card("sub-alice", 101, UserOwnedCardCreate(card_id=101))
			original_day = created.billing_cycle_refresh_day_of_month

			updated = service.update_user_card(
				"sub-alice",
				101,
				UserOwnedCardUpdate(billing_cycle_day_of_month=27),
			)

			self.assertEqual(updated.billing_cycle_refresh_day_of_month, original_day)

	def test_update_user_card_not_found(self):
		with self.Session() as db:
			service = UserCardManagementService(db)

			with self.assertRaises(ServiceError) as context:
				service.update_user_card("sub-alice", 999, UserOwnedCardUpdate(status=UserOwnedCardStatus.Closed))

			self.assertEqual(context.exception.status_code, 404)
			self.assertEqual(context.exception.message, "User does not own this card.")

	def test_remove_user_card_success(self):
		with self.Session() as db:
			service = UserCardManagementService(db)
			service.add_user_card("sub-alice", 102, UserOwnedCardCreate(card_id=102))

			service.remove_user_card("sub-alice", 102)

			remaining = db.query(UserOwnedCard).filter(UserOwnedCard.user_id == 1, UserOwnedCard.card_id == 102).first()
			self.assertIsNone(remaining)

	def test_remove_user_card_not_found(self):
		with self.Session() as db:
			service = UserCardManagementService(db)

			with self.assertRaises(ServiceError) as context:
				service.remove_user_card("sub-alice", 102)

			self.assertEqual(context.exception.status_code, 404)
			self.assertEqual(context.exception.message, "User does not own this card.")


if __name__ == "__main__":
	unittest.main()
