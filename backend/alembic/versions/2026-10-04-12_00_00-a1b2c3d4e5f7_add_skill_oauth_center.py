"""add skill oauth center

Revision ID: a1b2c3d4e5f7
Revises: f1b2c3d4e5f6
Create Date: 2026-10-04 12:00:00.000000
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'a1b2c3d4e5f7'
down_revision = 'f1b2c3d4e5f6'
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False, comment='是否已删除'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
    ]


def upgrade() -> None:
    op.create_table(
        'skill_client',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('client_id', sa.String(64), nullable=False, comment='客户端标识（分发给 skill 包）'),
        sa.Column('client_secret_hash', sa.String(255), nullable=False, comment='客户端密钥哈希'),
        sa.Column('name', sa.String(100), nullable=False, comment='skill 显示名称（授权页展示）'),
        sa.Column('description', sa.String(500), nullable=True, comment='skill 描述（授权页展示）'),
        sa.Column('icon', sa.String(500), nullable=True, comment='skill 图标 URL（授权页展示）'),
        sa.Column('scopes', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]', comment='允许申请的权限列表'),
        sa.Column('redirect_uris', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]', comment='允许的回调地址列表'),
        sa.Column('status', sa.Integer(), nullable=False, server_default='1', comment='状态(0停用 1启用)'),
        *_base_columns(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('client_id', name='uk_skill_client_client_id'),
        comment='skill 客户端注册表',
    )
    op.create_index('ix_skill_client_id', 'skill_client', ['id'], unique=True)
    op.create_index('ix_skill_client_client_id', 'skill_client', ['client_id'], unique=True)
    op.create_index('ix_skill_client_status', 'skill_client', ['status'])

    op.create_table(
        'skill_user_authorization',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
        sa.Column('client_id', sa.BigInteger(), nullable=False, comment='skill 客户端主键 ID'),
        sa.Column('scopes', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='[]', comment='用户实际同意的权限列表'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active', comment='授权状态(active/revoked)'),
        sa.Column('authorized_time', sa.DateTime(timezone=True), nullable=True, comment='最近一次授权时间'),
        sa.Column('last_used_time', sa.DateTime(timezone=True), nullable=True, comment='最近一次使用时间'),
        *_base_columns(),
        sa.ForeignKeyConstraint(['client_id'], ['skill_client.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'client_id', name='uk_skill_user_auth_user_client'),
        comment='用户与 skill 的授权关系表',
    )
    op.create_index('ix_skill_user_authorization_id', 'skill_user_authorization', ['id'], unique=True)
    op.create_index('idx_skill_user_auth_user', 'skill_user_authorization', ['user_id'])
    op.create_index('idx_skill_user_auth_client', 'skill_user_authorization', ['client_id'])


def downgrade() -> None:
    op.drop_table('skill_user_authorization')
    op.drop_table('skill_client')
