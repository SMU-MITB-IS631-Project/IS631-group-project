"""create card_catalogue table

Revision ID: 6223ac20df34
Revises: c9e4a2a7d1b0
Create Date: 2026-02-15 17:28:53.742337

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6223ac20df34'
down_revision: Union[str, None] = 'c9e4a2a7d1b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
