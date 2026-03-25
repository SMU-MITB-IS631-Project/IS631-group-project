"""update security logs

Revision ID: 141c4a372c2e
Revises: 3a9f2b1c4d6e
Create Date: 2026-03-25 09:26:56.548163

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '141c4a372c2e'
down_revision: Union[str, None] = '3a9f2b1c4d6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    table_names = set(inspector.get_table_names())

    if 'card_change_notification' not in table_names:
        op.create_table('card_change_notification',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('card_id', sa.Integer(), nullable=False),
        sa.Column('card_name', sa.String(length=255), nullable=False),
        sa.Column('changed_fields', sa.JSON(), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False),
        sa.Column('created_date', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['card_id'], ['card_catalogue.card_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user_profile.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
        )
        op.create_index(op.f('ix_card_change_notification_card_id'), 'card_change_notification', ['card_id'], unique=False)
        op.create_index(op.f('ix_card_change_notification_created_date'), 'card_change_notification', ['created_date'], unique=False)
        op.create_index(op.f('ix_card_change_notification_id'), 'card_change_notification', ['id'], unique=False)
        op.create_index(op.f('ix_card_change_notification_user_id'), 'card_change_notification', ['user_id'], unique=False)

    if dialect != 'sqlite':
        op.alter_column('card_bonus_category', 'bonus_cap_in_dollar',
                   existing_type=sa.INTEGER(),
                   server_default=None,
                   existing_nullable=False)
        op.alter_column('card_bonus_category', 'bonus_minimum_spend_in_dollar',
                   existing_type=sa.INTEGER(),
                   server_default=None,
                   existing_nullable=False)
        op.alter_column('card_catalogue', 'bank',
                   existing_type=sa.VARCHAR(length=17),
                   type_=sa.Enum('DBS', 'CITI', 'Standard_Chartered', 'UOB', 'Citi', 'StandardChartered', 'dbs', 'citi', 'standard_chartered', name='bankenum'),
                   existing_nullable=False)
        op.alter_column('transactions', 'status',
                   existing_type=sa.VARCHAR(length=15),
                   server_default=None,
                   type_=sa.Enum('active', 'deleted_with_card', 'Active', 'DeletedWithCard', name='transactionstatus'),
                   existing_nullable=False)

    user_owned_cards_cols = {col['name'] for col in inspector.get_columns('user_owned_cards')}
    if 'billing_cycle_refresh_day_of_mth' not in user_owned_cards_cols:
        op.add_column('user_owned_cards', sa.Column('billing_cycle_refresh_day_of_mth', sa.Integer(), server_default='1', nullable=False))
    if 'billing_cycle_refresh_day_of_month' in user_owned_cards_cols:
        op.drop_column('user_owned_cards', 'billing_cycle_refresh_day_of_month')

    user_profile_cols = {col['name'] for col in inspector.get_columns('user_profile')}
    if 'password_hash' not in user_profile_cols:
        op.add_column('user_profile', sa.Column('password_hash', sa.String(), server_default='', nullable=False))

    user_profile_indexes = {idx['name'] for idx in inspector.get_indexes('user_profile')}
    if 'ix_user_profile_cognito_sub_unique' in user_profile_indexes:
        op.drop_index('ix_user_profile_cognito_sub_unique', table_name='user_profile')

    if dialect == 'sqlite':
        if 'uq_user_profile_cognito_sub' not in user_profile_indexes:
            op.create_index('uq_user_profile_cognito_sub', 'user_profile', ['cognito_sub'], unique=True)
    else:
        op.create_unique_constraint('uq_user_profile_cognito_sub', 'user_profile', ['cognito_sub'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    dialect = bind.dialect.name

    user_profile_indexes = {idx['name'] for idx in inspector.get_indexes('user_profile')}
    if dialect == 'sqlite':
        if 'uq_user_profile_cognito_sub' in user_profile_indexes:
            op.drop_index('uq_user_profile_cognito_sub', table_name='user_profile')
    else:
        op.drop_constraint('uq_user_profile_cognito_sub', 'user_profile', type_='unique')

    if 'ix_user_profile_cognito_sub_unique' not in user_profile_indexes:
        op.create_index('ix_user_profile_cognito_sub_unique', 'user_profile', ['cognito_sub'], unique=1)

    user_profile_cols = {col['name'] for col in inspector.get_columns('user_profile')}
    if 'password_hash' in user_profile_cols:
        op.drop_column('user_profile', 'password_hash')

    user_owned_cards_cols = {col['name'] for col in inspector.get_columns('user_owned_cards')}
    if 'billing_cycle_refresh_day_of_month' not in user_owned_cards_cols:
        op.add_column('user_owned_cards', sa.Column('billing_cycle_refresh_day_of_month', sa.INTEGER(), server_default=sa.text("'1'"), nullable=False))
    if 'billing_cycle_refresh_day_of_mth' in user_owned_cards_cols:
        op.drop_column('user_owned_cards', 'billing_cycle_refresh_day_of_mth')

    if dialect != 'sqlite':
        op.alter_column('transactions', 'status',
                   existing_type=sa.Enum('active', 'deleted_with_card', 'Active', 'DeletedWithCard', name='transactionstatus'),
                   server_default=sa.text("'Active'"),
                   type_=sa.VARCHAR(length=15),
                   existing_nullable=False)
        op.alter_column('card_catalogue', 'bank',
                   existing_type=sa.Enum('DBS', 'CITI', 'Standard_Chartered', 'UOB', 'Citi', 'StandardChartered', 'dbs', 'citi', 'standard_chartered', name='bankenum'),
                   type_=sa.VARCHAR(length=17),
                   existing_nullable=False)
        op.alter_column('card_bonus_category', 'bonus_minimum_spend_in_dollar',
                   existing_type=sa.INTEGER(),
                   server_default=sa.text('0'),
                   existing_nullable=False)
        op.alter_column('card_bonus_category', 'bonus_cap_in_dollar',
                   existing_type=sa.INTEGER(),
                   server_default=sa.text('(99999999)'),
                   existing_nullable=False)

    table_names = set(inspector.get_table_names())
    if 'card_change_notification' in table_names:
        index_names = {idx['name'] for idx in inspector.get_indexes('card_change_notification')}
        if op.f('ix_card_change_notification_user_id') in index_names:
            op.drop_index(op.f('ix_card_change_notification_user_id'), table_name='card_change_notification')
        if op.f('ix_card_change_notification_id') in index_names:
            op.drop_index(op.f('ix_card_change_notification_id'), table_name='card_change_notification')
        if op.f('ix_card_change_notification_created_date') in index_names:
            op.drop_index(op.f('ix_card_change_notification_created_date'), table_name='card_change_notification')
        if op.f('ix_card_change_notification_card_id') in index_names:
            op.drop_index(op.f('ix_card_change_notification_card_id'), table_name='card_change_notification')
        op.drop_table('card_change_notification')
