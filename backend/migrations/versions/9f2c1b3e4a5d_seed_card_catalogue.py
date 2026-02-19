"""Seed card catalogue and bonus categories

Revision ID: 9f2c1b3e4a5d
Revises: 7b883af92e3b
Create Date: 2026-02-15 20:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "9f2c1b3e4a5d"
down_revision: Union[str, None] = "7b883af92e3b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Deterministic seed data for shared dev DBs.
    op.execute(
        "DELETE FROM card_bonus_category WHERE card_bonuscat_id IN (301, 302)"
    )
    op.execute(
        "DELETE FROM card_catalogue WHERE card_id IN (1, 2, 3, 4)"
    )

    op.execute(
        """
        INSERT INTO card_catalogue (card_id, bank, card_name, benefit_type, base_benefit_rate, status)
        VALUES
          (1, 'StandardChartered', 'Standard Chartered Simply Cash', 'Cashback', 0.015000, 'valid'),
          (2, 'DBS', 'DBS Woman''s World Card', 'Miles', 1.200000, 'valid'),
          (3, 'UOB', 'UOB PRIMI Miles Card', 'Miles', 1.200000, 'valid'),
          (4, 'UOB', 'UOB One Card', 'Cashback', 0.003000, 'valid');
        """
    )

    op.execute(
        """
        INSERT INTO card_bonus_category
          (card_bonuscat_id, card_id, bonus_category, bonus_benefit_rate, bonus_cap_in_dollar, bonus_minimum_spend_in_dollar)
        VALUES
          (301, 4, 'Fashion', 0.057000, 50, 800),
          (302, 4, 'Transport', 0.057000, 20, 800);
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM card_bonus_category WHERE card_bonuscat_id IN (301, 302)"
    )
    op.execute(
        "DELETE FROM card_catalogue WHERE card_id IN (1, 2, 3, 4)"
    )