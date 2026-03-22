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

# Only export the symbols that are actually implemented here.
# Legacy symbols like `SessionLocal`, `hash_password`, and `get_users` are
# no longer re-exported from this module to avoid exposing non-functional
# placeholders that raise NotImplementedError at runtime.

__all__ = ["UserProfileService"]
