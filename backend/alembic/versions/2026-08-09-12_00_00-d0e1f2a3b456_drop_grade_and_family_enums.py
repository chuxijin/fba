"""drop hardcoded grade and family enums

Revision ID: d0e1f2a3b456
Revises: c9d0e1f2a345
Create Date: 2026-08-09 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = 'd0e1f2a3b456'
down_revision = 'c9d0e1f2a345'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """移除与"权益自由组合"冲突的硬编码档位枚举。

    档位(VIP / SVIP / 畅学卡…)由售卖模板名称承载, 权益内容完全由运营勾选,
    因此权益包不再有 grade, 经验规则也不再按 FREE/VIP/SVIP 族群匹配,
    改为按"是否持有某个权益编码"判定。
    """
    # 权益包档次
    op.drop_column('entitlement_pack', 'grade')
    op.execute('DROP TYPE IF EXISTS grade_level')

    # 权益的度量与动作: 引擎从不读取, 纯装饰字段
    op.drop_column('entitlement', 'metric')
    op.drop_column('entitlement', 'verb')
    op.execute('DROP TYPE IF EXISTS entitlement_metric')
    op.execute('DROP TYPE IF EXISTS entitlement_verb')

    # 经验规则: family_code(FREE/VIP/SVIP) → required_entitlement_code
    op.drop_index('idx_exp_rule_match', table_name='experience_rule')
    op.alter_column(
        'experience_rule',
        'family_code',
        new_column_name='required_entitlement_code',
        type_=sa.String(length=64),
        existing_type=sa.String(length=16),
        existing_nullable=True,
        comment='生效所需权益编码, 空表示对所有用户生效',
    )
    # 旧的族群值不是权益编码, 直接置空表示"对所有用户生效", 由运营重新配置
    op.execute("UPDATE experience_rule SET required_entitlement_code = NULL")
    op.create_index(
        'idx_exp_rule_match',
        'experience_rule',
        ['event_code', 'required_entitlement_code', 'cycle_day', 'status'],
    )

    # 成长流水的族群列: init=False 且恒为 'FREE', 是死列
    op.drop_column('growth_event', 'family_code')


def downgrade() -> None:
    """回退档位枚举(数据无法还原, 仅恢复结构)。"""
    op.add_column(
        'growth_event',
        sa.Column('family_code', sa.String(length=16), nullable=False, server_default='FREE', comment='等级族群'),
    )

    op.drop_index('idx_exp_rule_match', table_name='experience_rule')
    op.alter_column(
        'experience_rule',
        'required_entitlement_code',
        new_column_name='family_code',
        type_=sa.String(length=16),
        existing_type=sa.String(length=64),
        existing_nullable=True,
        comment='等级族群',
    )
    op.create_index(
        'idx_exp_rule_match',
        'experience_rule',
        ['event_code', 'family_code', 'cycle_day', 'status'],
    )

    op.execute("CREATE TYPE entitlement_verb AS ENUM ('access', 'view', 'export', 'download', 'share', 'comment')")
    op.execute("CREATE TYPE entitlement_metric AS ENUM ('boolean', 'count', 'level')")
    op.add_column(
        'entitlement',
        sa.Column('verb', sa.Enum(name='entitlement_verb'), nullable=False, server_default='access', comment='权益动作'),
    )
    op.add_column(
        'entitlement',
        sa.Column(
            'metric',
            sa.Enum(name='entitlement_metric'),
            nullable=False,
            server_default='boolean',
            comment='权益度量',
        ),
    )

    op.execute("CREATE TYPE grade_level AS ENUM ('basic', 'standard', 'premium', 'elite')")
    op.add_column(
        'entitlement_pack',
        sa.Column('grade', sa.Enum(name='grade_level'), nullable=False, server_default='standard', comment='档次'),
    )
