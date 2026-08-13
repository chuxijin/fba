"""add commercial membership tier

Revision ID: f2a3b4c5d678
Revises: e1f2a3b4c567
Create Date: 2026-08-11 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'f2a3b4c5d678'
down_revision = 'e1f2a3b4c567'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增商业会员档位，并把现有模板按编码/名称回填到 FREE、VIP、SVIP。"""
    op.create_table(
        'membership_tier',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('code', sa.String(length=32), nullable=False, comment='档位编码'),
        sa.Column('name', sa.String(length=64), nullable=False, comment='档位名称'),
        sa.Column('weight', sa.Integer(), server_default='0', nullable=False, comment='展示排序权重'),
        sa.Column('is_paid', sa.Boolean(), server_default=sa.false(), nullable=False, comment='是否属于付费会员'),
        sa.Column('badge_color', sa.String(length=16), nullable=True, comment='徽章主题色'),
        sa.Column('description', sa.Text(), nullable=True, comment='描述'),
        sa.Column('display_order', sa.Integer(), server_default='0', nullable=False, comment='显示顺序'),
        sa.Column(
            'metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment='扩展展示配置',
        ),
        sa.Column(
            'status',
            postgresql.ENUM('active', 'archived', 'draft', name='common_status', create_type=False),
            server_default='active',
            nullable=False,
            comment='状态',
        ),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column(
            'deleted',
            sa.BigInteger(),
            server_default='0',
            nullable=False,
            comment='是否已删除（0：否；id：是）',
        ),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_membership_tier_code'),
        comment='商业会员档位',
    )
    op.create_index('ix_membership_tier_id', 'membership_tier', ['id'], unique=True)
    op.create_index('idx_membership_tier_status_order', 'membership_tier', ['status', 'display_order'])

    op.execute(
        sa.text("""
            INSERT INTO membership_tier (
                code, name, weight, is_paid, badge_color, description,
                display_order, metadata, status, created_time, updated_time, deleted
            ) VALUES
                (
                    'FREE', '普通用户', 0, FALSE, '#64748B', '免费用户与基础权益',
                    0, '{}'::jsonb, 'active', NOW(), NOW(), 0
                ),
                (
                    'VIP', 'VIP会员', 100, TRUE, '#2563EB', '标准付费会员',
                    100, '{}'::jsonb, 'active', NOW(), NOW(), 0
                ),
                (
                    'SVIP', 'SVIP会员', 200, TRUE, '#7C3AED', '高级付费会员',
                    200, '{}'::jsonb, 'active', NOW(), NOW(), 0
                )
        """)
    )

    op.add_column(
        'subscription_template',
        sa.Column('tier_id', sa.BigInteger(), nullable=True, comment='商业会员档位 ID'),
    )
    op.create_index('ix_subscription_template_tier_id', 'subscription_template', ['tier_id'])
    op.create_foreign_key(
        'fk_subscription_template_tier_id_membership_tier',
        'subscription_template',
        'membership_tier',
        ['tier_id'],
        ['id'],
        ondelete='RESTRICT',
    )

    op.execute(
        sa.text("""
            UPDATE subscription_template AS template
            SET tier_id = tier.id
            FROM membership_tier AS tier
            WHERE tier.code = CASE
                WHEN LOWER(template.code) LIKE '%svip%' OR LOWER(template.name) LIKE '%svip%' THEN 'SVIP'
                WHEN LOWER(template.code) LIKE '%vip%' OR LOWER(template.name) LIKE '%vip%' THEN 'VIP'
                WHEN template.code = 'template.free' THEN 'FREE'
                ELSE NULL
            END
        """)
    )


def downgrade() -> None:
    """移除商业会员档位。"""
    op.drop_constraint(
        'fk_subscription_template_tier_id_membership_tier',
        'subscription_template',
        type_='foreignkey',
    )
    op.drop_index('ix_subscription_template_tier_id', table_name='subscription_template')
    op.drop_column('subscription_template', 'tier_id')
    op.drop_index('idx_membership_tier_status_order', table_name='membership_tier')
    op.drop_index('ix_membership_tier_id', table_name='membership_tier')
    op.drop_table('membership_tier')
