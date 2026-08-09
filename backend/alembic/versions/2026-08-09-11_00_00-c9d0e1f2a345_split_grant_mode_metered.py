"""split grant mode metered and add trial policy

Revision ID: c9d0e1f2a345
Revises: b8c9d0e1f234
Create Date: 2026-08-09 11:00:00.000000

"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql

revision = 'c9d0e1f2a345'
down_revision = 'b8c9d0e1f234'
branch_labels = None
depends_on = None

#: 旧 grant_mode 取值中, 哪些是"会员周期配额"而非"未付费试看"。
#: trial 旧值身兼两职, 无法自动判别, 因此统一迁移为 metered(保守: 保留付费门槛),
#: 真正的试看规则由运营在管理端改配 trial_policy。
_LEGACY_TRIAL_TO_METERED = "UPDATE resource_rule SET grant_mode = 'metered' WHERE grant_mode = 'trial'"


def upgrade() -> None:
    """grant_mode 拆分 metered / 移除 ownership_required, 并给规则加试看策略。"""
    op.add_column(
        'resource_rule',
        sa.Column(
            'trial_policy',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment='试看策略, NULL 表示不允许试看; 形如 {"mode": "ordinal", "limit": 5}',
        ),
    )

    # PostgreSQL 无法直接删除 ENUM 取值, 需换类型
    op.execute("ALTER TYPE grant_mode RENAME TO grant_mode_old")
    op.execute("CREATE TYPE grant_mode AS ENUM ('access', 'metered', 'free_pass')")

    # 先落到文本列才能改写取值, 否则旧值不在新类型里会报错
    op.execute('ALTER TABLE resource_rule ALTER COLUMN grant_mode TYPE varchar(32) USING grant_mode::text')
    op.execute(_LEGACY_TRIAL_TO_METERED)
    # ownership_required 从未实现(评估器是空实现), 存量按需要权益处理
    op.execute("UPDATE resource_rule SET grant_mode = 'access' WHERE grant_mode = 'ownership_required'")
    op.execute(
        'ALTER TABLE resource_rule ALTER COLUMN grant_mode TYPE grant_mode USING grant_mode::grant_mode'
    )
    op.execute('DROP TYPE grant_mode_old')

    # 决策日志里的历史原因码同步改名, 保持前端筛选项一致
    op.execute("UPDATE decision_log SET reason_code = 'metered_consumed' WHERE reason_code = 'quota_trial'")


def downgrade() -> None:
    """回退 grant_mode 与试看策略。"""
    op.execute("UPDATE decision_log SET reason_code = 'quota_trial' WHERE reason_code = 'metered_consumed'")

    op.execute("ALTER TYPE grant_mode RENAME TO grant_mode_new")
    op.execute("CREATE TYPE grant_mode AS ENUM ('access', 'trial', 'free_pass', 'ownership_required')")
    op.execute('ALTER TABLE resource_rule ALTER COLUMN grant_mode TYPE varchar(32) USING grant_mode::text')
    op.execute("UPDATE resource_rule SET grant_mode = 'trial' WHERE grant_mode = 'metered'")
    op.execute(
        'ALTER TABLE resource_rule ALTER COLUMN grant_mode TYPE grant_mode USING grant_mode::grant_mode'
    )
    op.execute('DROP TYPE grant_mode_new')

    op.drop_column('resource_rule', 'trial_policy')
