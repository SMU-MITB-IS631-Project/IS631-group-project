"""normalize card_catalogue legacy enum/data values

Revision ID: 2b7d9e1f4c3a
Revises: 1c2d3e4f5a6b
Create Date: 2026-03-11 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "2b7d9e1f4c3a"
down_revision: Union[str, None] = "1c2d3e4f5a6b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Normalize legacy enum-like text values that appear in older DB states.
    op.execute("UPDATE card_catalogue SET bank = 'CITI' WHERE bank IN ('Citi', 'citi')")
    op.execute(
        "UPDATE card_catalogue SET bank = 'Standard_Chartered' "
        "WHERE bank IN ('StandardChartered', 'standardchartered', 'standard_chartered')"
    )
    op.execute("UPDATE card_catalogue SET benefit_type = 'MILES' WHERE benefit_type IN ('Miles', 'miles')")
    op.execute("UPDATE card_catalogue SET benefit_type = 'CASHBACK' WHERE benefit_type IN ('Cashback', 'cashback')")
    op.execute("UPDATE card_catalogue SET status = 'VALID' WHERE status IN ('valid', 'Valid')")

    # Keep deterministic IDs used by frontend card mapping.
    op.execute(
        """
        UPDATE card_catalogue
        SET bank = 'Standard_Chartered',
            card_name = 'Standard Chartered Simply Cash',
            benefit_type = 'CASHBACK',
            base_benefit_rate = 0.015000,
            status = 'VALID'
        WHERE card_id = 1
        """
    )
    op.execute(
        """
        UPDATE card_catalogue
        SET bank = 'DBS',
            card_name = 'DBS Woman''s World Card',
            benefit_type = 'MILES',
            base_benefit_rate = 1.200000,
            status = 'VALID'
        WHERE card_id = 2
        """
    )
    op.execute(
        """
        UPDATE card_catalogue
        SET bank = 'UOB',
            card_name = 'UOB PRVI Miles Card',
            benefit_type = 'MILES',
            base_benefit_rate = 1.200000,
            status = 'VALID'
        WHERE card_id = 3
        """
    )

    op.execute(
        """
        INSERT INTO card_catalogue (card_id, bank, card_name, benefit_type, base_benefit_rate, status)
        SELECT 1, 'Standard_Chartered', 'Standard Chartered Simply Cash', 'CASHBACK', 0.015000, 'VALID'
        WHERE NOT EXISTS (SELECT 1 FROM card_catalogue WHERE card_id = 1)
        """
    )
    op.execute(
        """
        INSERT INTO card_catalogue (card_id, bank, card_name, benefit_type, base_benefit_rate, status)
        SELECT 2, 'DBS', 'DBS Woman''s World Card', 'MILES', 1.200000, 'VALID'
        WHERE NOT EXISTS (SELECT 1 FROM card_catalogue WHERE card_id = 2)
        """
    )
    op.execute(
        """
        INSERT INTO card_catalogue (card_id, bank, card_name, benefit_type, base_benefit_rate, status)
        SELECT 3, 'UOB', 'UOB PRVI Miles Card', 'MILES', 1.200000, 'VALID'
        WHERE NOT EXISTS (SELECT 1 FROM card_catalogue WHERE card_id = 3)
        """
    )
    op.execute(
        """
        INSERT INTO card_catalogue (card_id, bank, card_name, benefit_type, base_benefit_rate, status)
        SELECT 4, 'UOB', 'UOB One Card', 'CASHBACK', 0.003000, 'VALID'
        WHERE NOT EXISTS (SELECT 1 FROM card_catalogue WHERE card_id = 4)
        """
    )


def downgrade() -> None:
    # Best-effort rollback to previous value style where applicable.
    op.execute("UPDATE card_catalogue SET bank = 'Citi' WHERE bank = 'CITI'")
    op.execute("UPDATE card_catalogue SET bank = 'StandardChartered' WHERE bank = 'Standard_Chartered'")
    op.execute("UPDATE card_catalogue SET benefit_type = 'Miles' WHERE benefit_type = 'MILES'")
    op.execute("UPDATE card_catalogue SET benefit_type = 'Cashback' WHERE benefit_type = 'CASHBACK'")
    op.execute("UPDATE card_catalogue SET status = 'valid' WHERE status = 'VALID'")
