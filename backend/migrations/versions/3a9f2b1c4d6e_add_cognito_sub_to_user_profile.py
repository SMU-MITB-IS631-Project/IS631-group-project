"""add cognito_sub to user_profile

Revision ID: 3a9f2b1c4d6e
Revises: 2b7d9e1f4c3a, e7f8a9b0c1d2
Create Date: 2026-03-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "3a9f2b1c4d6e"
down_revision: Union[str, tuple[str, str], None] = ("2b7d9e1f4c3a", "e7f8a9b0c1d2")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    column_names = [col["name"] for col in inspector.get_columns("user_profile")]
    if "cognito_sub" not in column_names:
        op.add_column("user_profile", sa.Column("cognito_sub", sa.String(), nullable=True))

    index_names = [idx["name"] for idx in inspector.get_indexes("user_profile")]
    if "ix_user_profile_cognito_sub" not in index_names:
        op.create_index("ix_user_profile_cognito_sub", "user_profile", ["cognito_sub"], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    index_names = [idx["name"] for idx in inspector.get_indexes("user_profile")]
    if "ix_user_profile_cognito_sub" in index_names:
        op.drop_index("ix_user_profile_cognito_sub", table_name="user_profile")

    column_names = [col["name"] for col in inspector.get_columns("user_profile")]
    if "cognito_sub" in column_names:
        op.drop_column("user_profile", "cognito_sub")
