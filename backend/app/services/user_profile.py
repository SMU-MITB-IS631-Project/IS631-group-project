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

# Best-effort re-exports for legacy symbols. If the underlying implementation
# does not provide them, define placeholders that fail loudly when called.
try:
    SessionLocal = _user_profile_impl.SessionLocal  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - only hit if symbol is truly missing
    def SessionLocal(*args, **kwargs):  # type: ignore[func-returns-value]
        """Legacy compatibility placeholder for SessionLocal.

        The real implementation is expected to live in `user_profile_service`.
        """
        raise NotImplementedError(
            "SessionLocal is not available in app.services.user_profile; "
            "ensure it is defined in app.services.user_profile_service."
        )

try:
    hash_password = _user_profile_impl.hash_password  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - only hit if symbol is truly missing
    def hash_password(*args, **kwargs):
        """Legacy compatibility placeholder for hash_password."""
        raise NotImplementedError(
            "hash_password is not available in app.services.user_profile; "
            "ensure it is defined in app.services.user_profile_service."
        )

try:
    get_users = _user_profile_impl.get_users  # type: ignore[attr-defined]
except AttributeError:  # pragma: no cover - only hit if symbol is truly missing
    def get_users(*args, **kwargs):
        """Legacy compatibility placeholder for get_users."""
        raise NotImplementedError(
            "get_users is not available in app.services.user_profile; "
            "ensure it is defined in app.services.user_profile_service."
        )

__all__ = ["UserProfileService", "SessionLocal", "hash_password", "get_users"]
