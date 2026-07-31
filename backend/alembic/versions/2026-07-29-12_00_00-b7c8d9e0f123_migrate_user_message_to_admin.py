"""migrate user message to admin

Revision ID: b7c8d9e0f123
Revises: a1b2c3d4e5f6
Create Date: 2026-07-29 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

revision = 'b7c8d9e0f123'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def _compatible_json() -> sa.JSON:
    """返回与模型一致的 PostgreSQL/MySQL 兼容 JSON 类型"""
    return sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')


def _base_columns() -> tuple[sa.Column, ...]:
    """返回 Base 模型的公共字段"""
    return (
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
    )


def _has_table(bind: Connection, table_name: str) -> bool:
    """判断当前 schema 是否存在指定表"""
    return sa.inspect(bind).has_table(table_name)


def _reflect_table(bind: Connection, table_name: str) -> sa.Table:
    """反射迁移中需要搬运数据的表"""
    return sa.Table(table_name, sa.MetaData(), autoload_with=bind)


def _reset_postgresql_sequence(bind: Connection, table_name: str) -> None:
    """显式写入历史主键后，将 PostgreSQL 自增序列推进到最大主键"""
    if bind.dialect.name != 'postgresql':
        return

    sequence_name = bind.execute(
        sa.text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
        {'table_name': table_name},
    ).scalar_one_or_none()
    if sequence_name is None:
        return

    table = _reflect_table(bind, table_name)
    max_id = bind.execute(sa.select(sa.func.max(table.c.id))).scalar_one_or_none()
    if max_id is not None:
        bind.execute(
            sa.text('SELECT setval(to_regclass(:sequence_name), :max_id, true)'),
            {'sequence_name': sequence_name, 'max_id': max_id},
        )


def _create_sys_message_tables(bind: Connection) -> None:
    """创建 admin 消息中心表；兼容已由 create_all 提前建表的开发环境"""
    if not _has_table(bind, 'sys_message'):
        op.create_table(
            'sys_message',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
            sa.Column('title', sa.String(length=128), nullable=False, comment='标题'),
            sa.Column('content', sa.Text(), nullable=False, comment='内容'),
            sa.Column('target_type', sa.String(length=20), nullable=False, comment='目标类型: all/user/role'),
            sa.Column('user_id', sa.BigInteger(), nullable=True, comment='目标用户 ID（target_type=user 时）'),
            sa.Column('role_id', sa.BigInteger(), nullable=True, comment='目标角色 ID（target_type=role 时）'),
            sa.Column(
                'message_type',
                sa.String(length=32),
                nullable=False,
                comment='消息类型: system/update/maintenance/personal',
            ),
            sa.Column('biz_source', sa.String(length=32), nullable=True, comment='来源模块，如 question_bank_v2'),
            sa.Column('biz_id', sa.String(length=64), nullable=True, comment='来源业务对象 ID，前端可点回原处'),
            sa.Column('sender_id', sa.BigInteger(), nullable=True, comment='发送人 ID（系统自动发送为空）'),
            sa.Column('link_url', sa.String(length=500), nullable=True, comment='跳转链接'),
            sa.Column('payload', _compatible_json(), nullable=True, comment='扩展数据'),
            sa.Column('status', sa.SmallInteger(), nullable=False, comment='状态: 0=禁用, 1=启用'),
            sa.Column('publish_time', sa.DateTime(timezone=True), nullable=True, comment='发布时间'),
            sa.Column('expire_time', sa.DateTime(timezone=True), nullable=True, comment='过期时间'),
            *_base_columns(),
            sa.PrimaryKeyConstraint('id'),
            comment='系统消息表',
        )
        op.create_index('ix_sys_message_id', 'sys_message', ['id'], unique=True)
        op.create_index('ix_sys_message_user_id', 'sys_message', ['user_id'], unique=False)
        op.create_index('ix_sys_message_status', 'sys_message', ['status'], unique=False)
        op.create_index(
            'idx_message_target_status_time',
            'sys_message',
            ['target_type', 'user_id', 'status', 'publish_time'],
            unique=False,
        )
        op.create_index('idx_message_type_time', 'sys_message', ['message_type', 'publish_time'], unique=False)
        op.create_index('idx_message_biz', 'sys_message', ['biz_source', 'biz_id'], unique=False)

    if not _has_table(bind, 'sys_message_read'):
        op.create_table(
            'sys_message_read',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
            sa.Column('message_id', sa.BigInteger(), nullable=False, comment='消息 ID'),
            sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
            sa.Column('read_time', sa.DateTime(timezone=True), nullable=False, comment='读取时间'),
            *_base_columns(),
            sa.ForeignKeyConstraint(['message_id'], ['sys_message.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('message_id', 'user_id', name='uq_message_read_message_user'),
            comment='系统消息已读表',
        )
        op.create_index('ix_sys_message_read_id', 'sys_message_read', ['id'], unique=True)
        op.create_index('ix_sys_message_read_user_id', 'sys_message_read', ['user_id'], unique=False)
        op.create_index(
            'idx_message_read_user_time',
            'sys_message_read',
            ['user_id', 'read_time'],
            unique=False,
        )


def _create_study_message_tables(bind: Connection) -> None:
    """重建 question_bank 旧消息表，供 downgrade 回迁数据"""
    if not _has_table(bind, 'study_user_message'):
        op.create_table(
            'study_user_message',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
            sa.Column('title', sa.String(length=128), nullable=False, comment='标题'),
            sa.Column('content', sa.Text(), nullable=False, comment='内容'),
            sa.Column('target_type', sa.String(length=20), nullable=False, comment='目标类型: all/user'),
            sa.Column('user_id', sa.BigInteger(), nullable=True, comment='用户 ID'),
            sa.Column(
                'message_type',
                sa.String(length=32),
                nullable=False,
                comment='消息类型: system/update/maintenance/personal',
            ),
            sa.Column('link_url', sa.String(length=500), nullable=True, comment='跳转链接'),
            sa.Column('payload', _compatible_json(), nullable=True, comment='扩展数据'),
            sa.Column('status', sa.SmallInteger(), nullable=False, comment='状态: 0=禁用, 1=启用'),
            sa.Column('publish_time', sa.DateTime(timezone=True), nullable=True, comment='发布时间'),
            sa.Column('expire_time', sa.DateTime(timezone=True), nullable=True, comment='过期时间'),
            sa.Column('read_time', sa.DateTime(timezone=True), nullable=True, comment='个人消息读取时间'),
            *_base_columns(),
            sa.PrimaryKeyConstraint('id'),
            comment='用户消息表',
        )
        op.create_index('ix_study_user_message_id', 'study_user_message', ['id'], unique=True)
        op.create_index('ix_study_user_message_user_id', 'study_user_message', ['user_id'], unique=False)
        op.create_index('ix_study_user_message_status', 'study_user_message', ['status'], unique=False)
        op.create_index(
            'idx_user_message_target_status_time',
            'study_user_message',
            ['target_type', 'user_id', 'status', 'publish_time'],
            unique=False,
        )
        op.create_index(
            'idx_user_message_type_time',
            'study_user_message',
            ['message_type', 'publish_time'],
            unique=False,
        )

    if not _has_table(bind, 'study_user_message_read'):
        op.create_table(
            'study_user_message_read',
            sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
            sa.Column('message_id', sa.BigInteger(), nullable=False, comment='消息 ID'),
            sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
            sa.Column('read_time', sa.DateTime(timezone=True), nullable=False, comment='读取时间'),
            *_base_columns(),
            sa.ForeignKeyConstraint(['message_id'], ['study_user_message.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('message_id', 'user_id', name='uq_user_message_read_message_user'),
            comment='用户消息已读表',
        )
        op.create_index('ix_study_user_message_read_id', 'study_user_message_read', ['id'], unique=True)
        op.create_index('ix_study_user_message_read_user_id', 'study_user_message_read', ['user_id'], unique=False)
        op.create_index(
            'idx_user_message_read_user_time',
            'study_user_message_read',
            ['user_id', 'read_time'],
            unique=False,
        )


def _migrate_to_sys(bind: Connection) -> None:
    """将 question_bank 消息和已读状态搬入 admin 消息中心"""
    if not _has_table(bind, 'study_user_message'):
        return

    source = _reflect_table(bind, 'study_user_message')
    target = _reflect_table(bind, 'sys_message')
    target_columns = [
        'id',
        'title',
        'content',
        'target_type',
        'user_id',
        'role_id',
        'message_type',
        'biz_source',
        'biz_id',
        'sender_id',
        'link_url',
        'payload',
        'status',
        'publish_time',
        'expire_time',
        'created_time',
        'updated_time',
        'deleted',
        'deleted_time',
    ]
    source_values = [
        source.c.id,
        source.c.title,
        source.c.content,
        source.c.target_type,
        source.c.user_id,
        sa.null(),
        source.c.message_type,
        sa.null(),
        sa.null(),
        sa.null(),
        source.c.link_url,
        source.c.payload,
        source.c.status,
        source.c.publish_time,
        source.c.expire_time,
        source.c.created_time,
        source.c.updated_time,
        source.c.deleted,
        source.c.deleted_time,
    ]
    missing_message = ~sa.exists(sa.select(1).select_from(target).where(target.c.id == source.c.id))
    bind.execute(target.insert().from_select(target_columns, sa.select(*source_values).where(missing_message)))
    _reset_postgresql_sequence(bind, 'sys_message')

    target_read = _reflect_table(bind, 'sys_message_read')
    read_columns = [
        'message_id',
        'user_id',
        'read_time',
        'created_time',
        'updated_time',
        'deleted',
        'deleted_time',
    ]
    if _has_table(bind, 'study_user_message_read'):
        source_read = _reflect_table(bind, 'study_user_message_read')
        missing_read = ~sa.exists(
            sa.select(1)
            .select_from(target_read)
            .where(
                target_read.c.message_id == source_read.c.message_id,
                target_read.c.user_id == source_read.c.user_id,
            )
        )
        bind.execute(
            target_read.insert().from_select(
                read_columns,
                sa.select(
                    source_read.c.message_id,
                    source_read.c.user_id,
                    source_read.c.read_time,
                    source_read.c.created_time,
                    source_read.c.updated_time,
                    source_read.c.deleted,
                    source_read.c.deleted_time,
                ).where(missing_read),
            )
        )

    missing_inline_read = ~sa.exists(
        sa.select(1)
        .select_from(target_read)
        .where(
            target_read.c.message_id == source.c.id,
            target_read.c.user_id == source.c.user_id,
        )
    )
    bind.execute(
        target_read.insert().from_select(
            read_columns,
            sa.select(
                source.c.id,
                source.c.user_id,
                source.c.read_time,
                source.c.read_time,
                source.c.updated_time,
                sa.literal(0, type_=sa.BigInteger()),
                sa.null(),
            ).where(
                source.c.target_type == 'user',
                source.c.user_id.is_not(None),
                source.c.read_time.is_not(None),
                missing_inline_read,
            ),
        )
    )


def _migrate_to_study(bind: Connection) -> None:
    """将 admin 消息中心数据回迁到 question_bank 旧表"""
    if not _has_table(bind, 'sys_message'):
        return

    source = _reflect_table(bind, 'sys_message')
    source_read = _reflect_table(bind, 'sys_message_read')
    target = _reflect_table(bind, 'study_user_message')
    read_time = (
        sa.select(sa.func.max(source_read.c.read_time))
        .where(
            source_read.c.message_id == source.c.id,
            source_read.c.user_id == source.c.user_id,
        )
        .correlate(source)
        .scalar_subquery()
    )
    target_columns = [
        'id',
        'title',
        'content',
        'target_type',
        'user_id',
        'message_type',
        'link_url',
        'payload',
        'status',
        'publish_time',
        'expire_time',
        'read_time',
        'created_time',
        'updated_time',
        'deleted',
        'deleted_time',
    ]
    missing_message = ~sa.exists(sa.select(1).select_from(target).where(target.c.id == source.c.id))
    bind.execute(
        target.insert().from_select(
            target_columns,
            sa.select(
                source.c.id,
                source.c.title,
                source.c.content,
                source.c.target_type,
                source.c.user_id,
                source.c.message_type,
                source.c.link_url,
                source.c.payload,
                source.c.status,
                source.c.publish_time,
                source.c.expire_time,
                read_time,
                source.c.created_time,
                source.c.updated_time,
                source.c.deleted,
                source.c.deleted_time,
            ).where(missing_message),
        )
    )
    _reset_postgresql_sequence(bind, 'study_user_message')

    target_read = _reflect_table(bind, 'study_user_message_read')
    missing_read = ~sa.exists(
        sa.select(1)
        .select_from(target_read)
        .where(
            target_read.c.message_id == source_read.c.message_id,
            target_read.c.user_id == source_read.c.user_id,
        )
    )
    bind.execute(
        target_read.insert().from_select(
            [
                'message_id',
                'user_id',
                'read_time',
                'created_time',
                'updated_time',
                'deleted',
                'deleted_time',
            ],
            sa.select(
                source_read.c.message_id,
                source_read.c.user_id,
                source_read.c.read_time,
                source_read.c.created_time,
                source_read.c.updated_time,
                source_read.c.deleted,
                source_read.c.deleted_time,
            ).where(missing_read),
        )
    )


def upgrade() -> None:
    """创建 admin 消息中心空表；不迁移旧消息、不删除 question_bank 旧表（v1 前端仍在使用）"""
    bind = op.get_bind()
    _create_sys_message_tables(bind)


def downgrade() -> None:
    """重建 question_bank 旧表并回迁数据；admin 新增的业务归属字段无法保留"""
    bind = op.get_bind()
    _create_study_message_tables(bind)
    _migrate_to_study(bind)

    if _has_table(bind, 'sys_message_read'):
        op.drop_table('sys_message_read')
    if _has_table(bind, 'sys_message'):
        op.drop_table('sys_message')
