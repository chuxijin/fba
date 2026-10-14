"""add openauth plugin without modifying legacy skill tables

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f7
Create Date: 2026-10-04 22:00:00
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'b7c8d9e0f1a2'
down_revision = 'a1b2c3d4e5f7'
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        'openauth_client',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.String(64), nullable=False),
        sa.Column('client_secret_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('client_type', sa.String(20), nullable=False, server_default='confidential'),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('icon', sa.String(500), nullable=True),
        sa.Column('scopes', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('redirect_uris', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('status', sa.Integer(), nullable=False, server_default='1'),
        *_base_columns(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id', name='uk_openauth_client_client_id'),
        sa.CheckConstraint('status IN (0, 1)', name='openauth_client_status_check'),
        comment='开放平台客户端注册表',
    )
    op.create_index('ix_openauth_client_id', 'openauth_client', ['id'], unique=True)
    op.create_index('ix_openauth_client_client_id', 'openauth_client', ['client_id'], unique=True)
    op.create_index('ix_openauth_client_status', 'openauth_client', ['status'])
    op.create_table(
        'openauth_user_authorization',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('client_id', sa.BigInteger(), nullable=False),
        sa.Column('grant_version', sa.String(36), nullable=False),
        sa.Column('scopes', postgresql.JSONB(), nullable=False, server_default='[]'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('authorized_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_used_time', sa.DateTime(timezone=True), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(['client_id'], ['openauth_client.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'client_id', name='uk_openauth_user_auth_user_client'),
        comment='用户与开放平台客户端的授权关系表',
    )
    op.create_index('ix_openauth_user_authorization_id', 'openauth_user_authorization', ['id'], unique=True)
    op.create_index('idx_openauth_user_auth_user', 'openauth_user_authorization', ['user_id'])
    op.create_index('idx_openauth_user_auth_client', 'openauth_user_authorization', ['client_id'])


def downgrade() -> None:
    op.drop_table('openauth_user_authorization')
    op.drop_table('openauth_client')
