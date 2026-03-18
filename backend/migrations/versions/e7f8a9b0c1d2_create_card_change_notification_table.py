"""create card_change_notification table

Revision ID: e7f8a9b0c1d2
Revises: 1c2d3e4f5a6b
Create Date: 2026-03-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "1c2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "card_change_notification",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("card_name", sa.String(length=255), nullable=False),
        sa.Column("changed_fields", sa.JSON(), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_date", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_profile.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["card_id"], ["card_catalogue.card_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_card_change_notification_id"), "card_change_notification", ["id"], unique=False)
    op.create_index(op.f("ix_card_change_notification_user_id"), "card_change_notification", ["user_id"], unique=False)
    op.create_index(op.f("ix_card_change_notification_card_id"), "card_change_notification", ["card_id"], unique=False)
    op.create_index(op.f("ix_card_change_notification_created_date"), "card_change_notification", ["created_date"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_card_change_notification_created_date"), table_name="card_change_notification")
    op.drop_index(op.f("ix_card_change_notification_card_id"), table_name="card_change_notification")
    op.drop_index(op.f("ix_card_change_notification_user_id"), table_name="card_change_notification")
    op.drop_index(op.f("ix_card_change_notification_id"), table_name="card_change_notification")
    op.drop_table("card_change_notification")
