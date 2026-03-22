from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.dependencies.db import get_db
from app.dependencies.user_context import get_x_user_id_int
from app.models.card_change_notification import CardChangeNotification

router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["notifications"],
)


def _unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "code": "UNAUTHORIZED",
                "message": "Missing or invalid user context.",
                "details": {"required_header": "x-user-id"},
            }
        },
    )


@router.get("")
def list_notifications(
    db: Session = Depends(get_db),
    user_id: int | None = Depends(get_x_user_id_int),
):
    if not user_id:
        return _unauthorized_response()

    rows = (
        db.query(CardChangeNotification)
        .filter(CardChangeNotification.user_id == int(user_id))
        .order_by(CardChangeNotification.created_date.desc())
        .all()
    )

    return {
        "notifications": [
            {
                "id": row.id,
                "user_id": row.user_id,
                "card_id": row.card_id,
                "card_name": row.card_name,
                "changed_fields": row.changed_fields,
                "effective_date": row.effective_date.isoformat(),
                "is_read": row.is_read,
                "created_date": row.created_date.isoformat() if row.created_date else None,
            }
            for row in rows
        ]
    }
