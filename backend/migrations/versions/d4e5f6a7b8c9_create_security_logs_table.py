"""create security_logs table

Revision ID: d4e5f6a7b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-03-04 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'security_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('event_status', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=255), nullable=True),
        sa.Column('request_id', sa.String(length=100), nullable=True),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user_profile.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_security_logs_event_type'), 'security_logs', ['event_type'], unique=False)
    op.create_index(op.f('ix_security_logs_id'), 'security_logs', ['id'], unique=False)
    op.create_index(op.f('ix_security_logs_timestamp'), 'security_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_security_logs_user_id'), 'security_logs', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_security_logs_user_id'), table_name='security_logs')
    op.drop_index(op.f('ix_security_logs_timestamp'), table_name='security_logs')
    op.drop_index(op.f('ix_security_logs_id'), table_name='security_logs')
    op.drop_index(op.f('ix_security_logs_event_type'), table_name='security_logs')
    op.drop_table('security_logs')
