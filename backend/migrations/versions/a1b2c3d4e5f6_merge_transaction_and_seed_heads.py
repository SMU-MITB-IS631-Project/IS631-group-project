"""Merge transaction status and seed data heads

Revision ID: a1b2c3d4e5f6
Revises: 609472f13781, 8e6d0b130081
Create Date: 2026-03-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = ('609472f13781', '8e6d0b130081')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # This is a merge migration - no schema changes
    pass


def downgrade() -> None:
    # This is a merge migration - no schema changes
    pass
