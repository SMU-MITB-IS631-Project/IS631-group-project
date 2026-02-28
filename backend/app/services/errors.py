from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ServiceError(Exception):
    """Consistent service-layer exception with HTTP-friendly metadata."""

    status_code: int
    code: str
    message: str
    details: Dict[str, Any]

    def __str__(self) -> str:  # pragma: no cover - convenience for logging
        return f"{self.status_code} {self.code}: {self.message} | {self.details}"
