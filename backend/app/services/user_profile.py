"""Backward-compatible import path.

Some tests and legacy code import `app.services.user_profile`.
The implementation lives in `app.services.user_profile_service`.
"""

from .user_profile_service import UserProfileService

__all__ = ["UserProfileService"]
