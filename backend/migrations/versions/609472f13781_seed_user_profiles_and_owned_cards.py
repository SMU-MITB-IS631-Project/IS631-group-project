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
        VALUES
          (1, 'user1', 'hashed_password_1', 'Alice', 'alice@example.com', 'Cashback', '2026-02-21 11:26:57.648370'),
          (2, 'user2', 'hashed_password_2', 'Bob', 'bob@example.com', 'Miles', '2026-02-21 11:26:57.648370')
        """
    )

    op.execute(
        """
        INSERT INTO user_owned_cards (user_id, card_id, card_expiry_date, billing_cycle_refresh_date, status)
        VALUES
          (1, 1, '9999-01-01', '2026-02-28', 'Active'),
          (1, 2, '9999-01-01', '2026-02-28', 'Active'),
          (2, 3, '9999-01-01', '2026-02-28', 'Active'),
          (2, 4, '9999-01-01', '2026-02-28', 'Active');
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM user_owned_cards WHERE user_id IN (1, 2)")
    op.execute("DELETE FROM user_profile WHERE id IN (1, 2)")
