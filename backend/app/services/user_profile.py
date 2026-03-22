"""Backward-compatible import path.

Some tests and legacy code import `app.services.user_profile`.
The implementation lives in `app.services.user_profile_service`.

This module re-exports `UserProfileService` and selected legacy symbols
(`SessionLocal`, `hash_password`, `get_users`) so that older import paths
continue to work.
"""

from . import user_profile_service as _user_profile_impl

# Always re-export UserProfileService.
UserProfileService = _user_profile_impl.UserProfileService

# Backward-compatible exports for legacy symbols.
# If the concrete implementations exist in `user_profile_service`, re-export
# them directly. Otherwise, provide compatibility stubs that raise
# NotImplementedError only when called so that tests and legacy code can
# still import or monkeypatch these names without failing at import time.

if hasattr(_user_profile_impl, "SessionLocal"):
    SessionLocal = _user_profile_impl.SessionLocal  # type: ignore[attr-defined]
else:
    def SessionLocal(*args, **kwargs):  # type: ignore[func-returns-value]
        """Compatibility stub for legacy SessionLocal."""
        raise NotImplementedError(
            "SessionLocal is not available in this build; this is a "
            "backward-compatibility stub."
        )

if hasattr(_user_profile_impl, "hash_password"):
    hash_password = _user_profile_impl.hash_password  # type: ignore[attr-defined]
else:
    def hash_password(*args, **kwargs):
        """Compatibility stub for legacy hash_password."""
        raise NotImplementedError(
            "hash_password is not available in this build; this is a "
            "backward-compatibility stub."
        )

if hasattr(_user_profile_impl, "get_users"):
    get_users = _user_profile_impl.get_users  # type: ignore[attr-defined]
else:
    def get_users(*args, **kwargs):
        """Compatibility stub for legacy get_users."""
        raise NotImplementedError(
            "get_users is not available in this build; this is a "
            "backward-compatibility stub."
        )

__all__ = ["UserProfileService", "SessionLocal", "hash_password", "get_users"]
