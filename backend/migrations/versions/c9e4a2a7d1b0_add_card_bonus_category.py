"""Add card bonus category table

Revision ID: c9e4a2a7d1b0
Revises: b3ed2dc143be
Create Date: 2026-02-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e4a2a7d1b0'
down_revision: Union[str, None] = 'b3ed2dc143be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'card_bonus_category',
        sa.Column('card_bonuscat_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('bonus_category', sa.Enum('Food', 'Transport', 'Entertainment', 'Fashion', 'All', name='bonuscategory'), nullable=False),
        sa.Column('bonus_benefit_rate', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('bonus_cap_in_dollar', sa.Integer(), server_default=sa.text('99999999'), nullable=False),
        sa.Column('bonus_minimum_spend_in_dollar', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['card_catalogue.card_id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('card_bonuscat_id'),
        sa.UniqueConstraint('card_id', 'bonus_category', name='uq_card_bonus_category_per_card')
    )
    op.create_index(op.f('ix_card_bonus_category_card_bonuscat_id'), 'card_bonus_category', ['card_bonuscat_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_card_bonus_category_card_bonuscat_id'), table_name='card_bonus_category')
    op.drop_table('card_bonus_category')
