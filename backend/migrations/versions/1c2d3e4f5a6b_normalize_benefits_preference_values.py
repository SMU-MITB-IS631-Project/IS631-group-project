"""normalize benefits_preference values

Revision ID: 1c2d3e4f5a6b
Revises: ec4a6dd546f7
Create Date: 2026-03-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "1c2d3e4f5a6b"
down_revision: Union[str, None] = "ec4a6dd546f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize legacy enum values to current SQLAlchemy Enum member names.
    op.execute("UPDATE user_profile SET benefits_preference = 'cashback' WHERE benefits_preference = 'Cashback'")
    op.execute("UPDATE user_profile SET benefits_preference = 'miles' WHERE benefits_preference = 'Miles'")
    op.execute(
        "UPDATE user_profile "
        "SET benefits_preference = 'no_preference' "
        "WHERE benefits_preference IN ('No_preference', 'No preference')"
    )


def downgrade() -> None:
    # Best-effort rollback back to legacy values.
    op.execute("UPDATE user_profile SET benefits_preference = 'Cashback' WHERE benefits_preference = 'cashback'")
    op.execute("UPDATE user_profile SET benefits_preference = 'Miles' WHERE benefits_preference = 'miles'")
    op.execute("UPDATE user_profile SET benefits_preference = 'No_preference' WHERE benefits_preference = 'no_preference'")
