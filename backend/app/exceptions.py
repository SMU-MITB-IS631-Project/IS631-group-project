from app.services.errors import ServiceError


def _default_code_for_status(status_code: int) -> str:
    if status_code == 400:
        return "VALIDATION_ERROR"
    if status_code == 401:
        return "UNAUTHORIZED"
    if status_code == 403:
        return "FORBIDDEN"
    if status_code == 404:
        return "NOT_FOUND"
    if status_code == 409:
        return "CONFLICT"
    if status_code >= 500:
        return "INTERNAL_SERVER_ERROR"
    return "ERROR"


class ServiceException(ServiceError):
    """Backward-compatible shim.

    Older code raises ServiceException(status_code, detail). Newer code uses ServiceError.
    This class keeps the old attributes (`status_code`, `detail`) but behaves like a
    ServiceError so the app's centralized exception handler can format responses.
    """

    def __init__(self, status_code: int, detail: str):
        self.detail = detail
        super().__init__(
            status_code=status_code,
            code=_default_code_for_status(status_code),
            message=detail,
            details={},
        )