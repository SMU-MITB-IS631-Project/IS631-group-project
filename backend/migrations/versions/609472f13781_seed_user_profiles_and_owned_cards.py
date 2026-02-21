"""seed user profiles and owned cards

Revision ID: 609472f13781
Revises: 9f2c1b3e4a5d
Create Date: 2026-02-21 11:26:57.648370

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '609472f13781'
down_revision: Union[str, None] = '9f2c1b3e4a5d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO user_profile (id, username, password_hash, name, email, benefits_preference, created_date)
        SELECT 1, 'user1', 'hashed_password_1', 'Alice', 'alice@example.com', 'Cashback', '2026-02-21 11:26:57.648370'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_profile WHERE id = 1 OR username = 'user1' OR email = 'alice@example.com'
        )
        """
    )
    op.execute(
        """
        INSERT INTO user_profile (id, username, password_hash, name, email, benefits_preference, created_date)
        SELECT 2, 'user2', 'hashed_password_2', 'Bob', 'bob@example.com', 'Miles', '2026-02-21 11:26:57.648370'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_profile WHERE id = 2 OR username = 'user2' OR email = 'bob@example.com'
        )
        """
    )

    op.execute(
        """
        INSERT INTO user_owned_cards (user_id, card_id, card_expiry_date, billing_cycle_refresh_date, status)
        SELECT 1, 1, '2029-02-28', '2026-02-28', 'Active'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_owned_cards WHERE user_id = 1 AND card_id = 1
        )
        """
    )
    op.execute(
        """
        INSERT INTO user_owned_cards (user_id, card_id, card_expiry_date, billing_cycle_refresh_date, status)
        SELECT 1, 2, '2029-02-28', '2026-02-28', 'Active'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_owned_cards WHERE user_id = 1 AND card_id = 2
        )
        """
    )
    op.execute(
        """
        INSERT INTO user_owned_cards (user_id, card_id, card_expiry_date, billing_cycle_refresh_date, status)
        SELECT 2, 3, '2029-02-28', '2026-02-28', 'Active'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_owned_cards WHERE user_id = 2 AND card_id = 3
        )
        """
    )
    op.execute(
        """
        INSERT INTO user_owned_cards (user_id, card_id, card_expiry_date, billing_cycle_refresh_date, status)
        SELECT 2, 4, '2029-02-28', '2026-02-28', 'Active'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_owned_cards WHERE user_id = 2 AND card_id = 4
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM user_owned_cards WHERE (user_id = 1 AND card_id IN (1, 2)) OR (user_id = 2 AND card_id IN (3, 4))")
    op.execute("DELETE FROM user_profile WHERE username IN ('user1', 'user2')")
