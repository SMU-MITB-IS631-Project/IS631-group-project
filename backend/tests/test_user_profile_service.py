import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.db.db import Base  # noqa: E402
from app.exceptions import ServiceException  # noqa: E402
from app.models.user_owned_cards import UserOwnedCard  # noqa: F401,E402
from app.models.transaction import UserTransaction  # noqa: F401,E402
from app.models.user_profile import BenefitsPreference  # noqa: E402
from app.services.user_profile_service import UserProfileService  # noqa: E402


@pytest.fixture
def mockdb():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        yield db


def test_create_user_profile_success(mockdb):
    service = UserProfileService(mockdb)
    created = service.create_user_profile(
        username="alice",
        email="alice@example.com",
        cognitosub="sub-alice",
        name="Alice",
        benefits_preference=BenefitsPreference.cashback,
    )

    assert created.id is not None
    assert created.username == "alice"
    assert created.email == "alice@example.com"
    assert created.cognito_sub == "sub-alice"
    assert created.name == "Alice"
    assert created.benefits_preference == BenefitsPreference.cashback


def test_create_user_profile_default_preference(mockdb):
    service = UserProfileService(mockdb)
    created = service.create_user_profile(
        username="bob",
        email="bob@example.com",
        cognitosub="sub-bob",
    )

    assert created.benefits_preference == BenefitsPreference.no_preference


def test_create_user_profile_with_empty_email_hits_no_email_branch(mockdb):
    service = UserProfileService(mockdb)
    created = service.create_user_profile(
        username="charlie",
        email=None,
        cognitosub="sub-charlie",
    )

    assert created.id is not None
    assert created.email is None
    assert created.username == "charlie"


def test_create_user_profile_conflict_same_cognito_sub(mockdb):
    service = UserProfileService(mockdb)
    service.create_user_profile(
        username="alice",
        email="alice@example.com",
        cognitosub="shared-sub",
    )

    with pytest.raises(ServiceException) as exc_info:
        service.create_user_profile(
            username="alice2",
            email="alice2@example.com",
            cognitosub="shared-sub",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "User profile already exists for this Cognito user."


def test_create_user_profile_conflict_username(mockdb):
    service = UserProfileService(mockdb)
    service.create_user_profile(
        username="alice",
        email="alice@example.com",
        cognitosub="sub-alice",
    )

    with pytest.raises(ServiceException) as exc_info:
        service.create_user_profile(
            username="alice",
            email="other@example.com",
            cognitosub="sub-other",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Username already exists."


def test_create_user_profile_conflict_email(mockdb):
    service = UserProfileService(mockdb)
    service.create_user_profile(
        username="alice",
        email="same@example.com",
        cognitosub="sub-alice",
    )

    with pytest.raises(ServiceException) as exc_info:
        service.create_user_profile(
            username="bob",
            email="same@example.com",
            cognitosub="sub-bob",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Email already exists."


def test_create_user_profile_integrity_error_rolls_back_and_raises_service_exception(mockdb):
    service = UserProfileService(mockdb)
    integrity_error = IntegrityError("INSERT", {"username": "alice"}, Exception("duplicate"))

    with patch.object(mockdb, "commit", side_effect=integrity_error):
        with patch.object(mockdb, "rollback", wraps=mockdb.rollback) as rollback_spy:
            with pytest.raises(ServiceException) as exc_info:
                service.create_user_profile(
                    username="alice",
                    email="alice@example.com",
                    cognitosub="sub-alice",
                )

            assert exc_info.value.status_code == 409
            assert exc_info.value.detail == "Username or email already exists."
            rollback_spy.assert_called_once()


def test_get_user_profile_found(mockdb):
    service = UserProfileService(mockdb)
    service.create_user_profile(
        username="alice",
        email="alice@example.com",
        cognitosub="sub-alice",
        name="Alice",
    )

    user = service.get_user_profile("sub-alice")

    assert user is not None
    assert user.username == "alice"
    assert user.name == "Alice"


def test_get_user_profile_not_found(mockdb):
    service = UserProfileService(mockdb)

    user = service.get_user_profile("missing-sub")

    assert user is None


def test_update_user_profile_name_and_preference(mockdb):
    service = UserProfileService(mockdb)
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

    assert updated.name == "After"
    assert updated.benefits_preference == BenefitsPreference.miles


def test_update_user_profile_partial_update(mockdb):
    service = UserProfileService(mockdb)
    service.create_user_profile(
        username="alice",
        email="alice@example.com",
        cognitosub="sub-alice",
        name="KeepName",
        benefits_preference=BenefitsPreference.cashback,
    )

    updated = service.update_user_profile(cognitosub="sub-alice", name=None, benefits_preference=None)

    assert updated.name == "KeepName"
    assert updated.benefits_preference == BenefitsPreference.cashback


def test_update_user_profile_not_found(mockdb):
    service = UserProfileService(mockdb)

    with pytest.raises(ServiceException) as exc_info:
        service.update_user_profile(cognitosub="missing-sub", name="NoUser")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found."


def test_delete_user_profile_success(mockdb):
    service = UserProfileService(mockdb)
    service.create_user_profile(
        username="alice",
        email="alice@example.com",
        cognitosub="sub-alice",
    )

    service.delete_user_profile("sub-alice")

    assert service.get_user_profile("sub-alice") is None


def test_delete_user_profile_not_found(mockdb):
    service = UserProfileService(mockdb)

    with pytest.raises(ServiceException) as exc_info:
        service.delete_user_profile("missing-sub")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "User not found."
