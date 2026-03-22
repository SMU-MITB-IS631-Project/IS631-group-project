import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import Base  # noqa: E402
from app.exceptions import ServiceException  # noqa: E402
from app.models.user_owned_cards import UserOwnedCard  # noqa: F401,E402
from app.models.transaction import UserTransaction  # noqa: F401,E402
from app.models.user_profile import BenefitsPreference, UserProfile  # noqa: E402
from app.services.user_profile_service import UserProfileService  # noqa: E402


class UserProfileServiceTests(unittest.TestCase):
	def setUp(self):
		engine = create_engine(
			"sqlite:///:memory:",
			connect_args={"check_same_thread": False},
			poolclass=StaticPool,
		)
		Base.metadata.create_all(bind=engine)
		self.Session = sessionmaker(bind=engine)

	def test_create_user_profile_success(self):
		with self.Session() as db:
			service = UserProfileService(db)
			created = service.create_user_profile(
				username="alice",
				email="alice@example.com",
				cognitosub="sub-alice",
				name="Alice",
				benefits_preference=BenefitsPreference.cashback,
			)

			self.assertIsNotNone(created.id)
			self.assertEqual(created.username, "alice")
			self.assertEqual(created.email, "alice@example.com")
			self.assertEqual(created.cognito_sub, "sub-alice")
			self.assertEqual(created.name, "Alice")
			self.assertEqual(created.benefits_preference, BenefitsPreference.cashback)

	def test_create_user_profile_default_preference(self):
		with self.Session() as db:
			service = UserProfileService(db)
			created = service.create_user_profile(
				username="bob",
				email="bob@example.com",
				cognitosub="sub-bob",
			)

			self.assertEqual(created.benefits_preference, BenefitsPreference.no_preference)

	def test_create_user_profile_conflict_same_cognito_sub(self):
		with self.Session() as db:
			service = UserProfileService(db)
			service.create_user_profile(
				username="alice",
				email="alice@example.com",
				cognitosub="shared-sub",
			)

			with self.assertRaises(ServiceException) as context:
				service.create_user_profile(
					username="alice2",
					email="alice2@example.com",
					cognitosub="shared-sub",
				)

			self.assertEqual(context.exception.status_code, 409)
			self.assertEqual(context.exception.detail, "User profile already exists for this Cognito user.")

	def test_create_user_profile_conflict_username(self):
		with self.Session() as db:
			service = UserProfileService(db)
			service.create_user_profile(
				username="alice",
				email="alice@example.com",
				cognitosub="sub-alice",
			)

			with self.assertRaises(ServiceException) as context:
				service.create_user_profile(
					username="alice",
					email="other@example.com",
					cognitosub="sub-other",
				)

			self.assertEqual(context.exception.status_code, 409)
			self.assertEqual(context.exception.detail, "Username already exists.")

	def test_create_user_profile_conflict_email(self):
		with self.Session() as db:
			service = UserProfileService(db)
			service.create_user_profile(
				username="alice",
				email="same@example.com",
				cognitosub="sub-alice",
			)

			with self.assertRaises(ServiceException) as context:
				service.create_user_profile(
					username="bob",
					email="same@example.com",
					cognitosub="sub-bob",
				)

			self.assertEqual(context.exception.status_code, 409)
			self.assertEqual(context.exception.detail, "Email already exists.")

	def test_get_user_profile_found(self):
		with self.Session() as db:
			service = UserProfileService(db)
			service.create_user_profile(
				username="alice",
				email="alice@example.com",
				cognitosub="sub-alice",
				name="Alice",
			)

			user = service.get_user_profile("sub-alice")

			self.assertIsNotNone(user)
			self.assertEqual(user.username, "alice")
			self.assertEqual(user.name, "Alice")

	def test_get_user_profile_not_found(self):
		with self.Session() as db:
			service = UserProfileService(db)

			user = service.get_user_profile("missing-sub")

			self.assertIsNone(user)

	def test_get_all_user_profiles(self):
		with self.Session() as db:
			service = UserProfileService(db)
			service.create_user_profile("alice", "alice@example.com", "sub-alice")
			service.create_user_profile("bob", "bob@example.com", "sub-bob")

			users = service.get_all_user_profiles()

			self.assertEqual(len(users), 2)
			self.assertSetEqual({u.username for u in users}, {"alice", "bob"})

	def test_update_user_profile_name_and_preference(self):
		with self.Session() as db:
			service = UserProfileService(db)
			service.create_user_profile(
				username="alice",
				email="alice@example.com",
				cognitosub="sub-alice",
				name="Before",
				benefits_preference=BenefitsPreference.no_preference,
			)

			updated = service.update_user_profile(
				cognitosub="sub-alice",
				name="After",
				benefits_preference=BenefitsPreference.miles,
			)

			self.assertEqual(updated.name, "After")
			self.assertEqual(updated.benefits_preference, BenefitsPreference.miles)

	def test_update_user_profile_partial_update(self):
		with self.Session() as db:
			service = UserProfileService(db)
			service.create_user_profile(
				username="alice",
				email="alice@example.com",
				cognitosub="sub-alice",
				name="KeepName",
				benefits_preference=BenefitsPreference.cashback,
			)

			updated = service.update_user_profile(cognitosub="sub-alice", name=None, benefits_preference=None)

			self.assertEqual(updated.name, "KeepName")
			self.assertEqual(updated.benefits_preference, BenefitsPreference.cashback)

	def test_update_user_profile_not_found(self):
		with self.Session() as db:
			service = UserProfileService(db)

			with self.assertRaises(ServiceException) as context:
				service.update_user_profile(cognitosub="missing-sub", name="NoUser")

			self.assertEqual(context.exception.status_code, 404)
			self.assertEqual(context.exception.detail, "User not found.")

	def test_delete_user_profile_success(self):
		with self.Session() as db:
			service = UserProfileService(db)
			service.create_user_profile(
				username="alice",
				email="alice@example.com",
				cognitosub="sub-alice",
			)

			service.delete_user_profile("sub-alice")

			self.assertIsNone(service.get_user_profile("sub-alice"))

	def test_delete_user_profile_not_found(self):
		with self.Session() as db:
			service = UserProfileService(db)

			with self.assertRaises(ServiceException) as context:
				service.delete_user_profile("missing-sub")

			self.assertEqual(context.exception.status_code, 404)
			self.assertEqual(context.exception.detail, "User not found.")


if __name__ == "__main__":
	unittest.main()
