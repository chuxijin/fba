"""Study goals reuse dictionary entries and user preferences; no new tables.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = 'a3b4c5d6e7f8'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(JSONB(), 'postgresql')
    op.add_column('sys_dict_data', sa.Column('extra', json_type, nullable=False, server_default=sa.text("'{}'")))
    op.add_column(
        'qbank_v2_user_practice_preference',
        sa.Column('study_goal', json_type, nullable=False, server_default=sa.text("'{}'")),
    )
    # 只初始化字典类型，不臆造官方题量、地区或卷类。保留既有同编码数据。
    bind = op.get_bind()
    table = sa.table(
        'sys_dict_type', sa.column('id'), sa.column('name'), sa.column('code'),
        sa.column('remark'), sa.column('created_time'), sa.column('deleted'),
    )
    if bind.dialect.name == 'postgresql':
        bind.execute(sa.text('LOCK TABLE sys_dict_type IN SHARE ROW EXCLUSIVE MODE'))
    exists = bind.execute(
        sa.select(table.c.id).where(table.c.code == 'study_exam_target', table.c.deleted == 0)
    ).first()
    if not exists:
        # Alembic 不依赖应用进程的 Redis / 雪花节点初始化。
        next_id = bind.scalar(sa.select(sa.func.coalesce(sa.func.max(table.c.id), 0) + 1))
        bind.execute(
            table.insert().values(
                id=next_id, name='备考目标', code='study_exam_target',
                remark='考试目录与组卷模板配置，详见 study-goal 文档', created_time=sa.func.now(), deleted=0,
            )
        )
        if bind.dialect.name == 'postgresql':
            sequence = bind.scalar(sa.text("SELECT pg_get_serial_sequence('sys_dict_type', 'id')"))
            if sequence:
                bind.execute(
                    sa.text(
                        'SELECT setval(CAST(:sequence AS regclass), '
                        'GREATEST((SELECT MAX(id) FROM sys_dict_type), '
                        'pg_sequence_last_value(CAST(:sequence AS regclass))), true)'
                    ),
                    {'sequence': sequence},
                )


def downgrade() -> None:
    # 不删除可能已经被运营编辑、引用的字典数据。
    op.drop_column('qbank_v2_user_practice_preference', 'study_goal')
    op.drop_column('sys_dict_data', 'extra')
