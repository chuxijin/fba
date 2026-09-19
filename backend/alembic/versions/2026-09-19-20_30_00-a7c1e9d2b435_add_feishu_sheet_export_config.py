"""add feishu sheet export config

Revision ID: a7c1e9d2b435
Revises: f1b2c3d4e5f6
Create Date: 2026-09-19 20:30:00.000000

把原先散落在 backend/plugin/feishu/plugin.toml 里的「公考资源同步到飞书」配置，
落成 feishu_sheet_config 表里的一条记录，为后续可配置化 / 多表（如考研）打底。

本迁移只建表 + 搬运配置，不改变任何运行时行为：
导出服务仍在读取 settings.GONGKAO_FEISHU_*，切换发生在其后的改造步骤。
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection

revision = 'a7c1e9d2b435'
down_revision = 'f1b2c3d4e5f6'
branch_labels = None
depends_on = None


# 公考配置的原始值，与 plugin.toml 保持逐字一致
GONGKAO_NAME = '公考'
GONGKAO_APP_CODE = 'youanshang'
GONGKAO_CATEGORY_TYPE = 'knowledge_point'
GONGKAO_SHEET_URL = 'https://my.feishu.cn/sheets/DOEXsIyBUh6ZhDtgb4mcj0KNnZe'
GONGKAO_SHEET_MAP = {
    '笔记': '笔记专栏',
    '真题': '真题获取',
    '电子书': '干货汇总',
    '软件': '干货汇总',
    '其他': '干货汇总',
    '干货': '干货汇总',
}
GONGKAO_CATEGORY_OPTIONS = [
    '政治理论',
    '常识判断',
    '言语理解与表达',
    '数量关系',
    '判断推理',
    '资料分析',
    '申论',
    '面试',
]
GONGKAO_SOURCE_WEIGHTS = {'用户推荐': 4, '网络获取': 5, '店铺购买': 1}
GONGKAO_PAID_SHEETS = ['真题获取', '干货汇总']
GONGKAO_CRON = '0 3 * * *'


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


def _create_config_table() -> None:
    op.create_table(
        'feishu_sheet_config',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('name', sa.String(length=128), nullable=False, comment='配置名称，如「公考」'),
        sa.Column('app_code', sa.String(length=64), nullable=False, comment='分类来源：sys_category.app_code'),
        sa.Column('sheet_url', sa.String(length=512), nullable=False, comment='飞书表格地址'),
        sa.Column(
            'category_type',
            sa.String(length=64),
            server_default='knowledge_point',
            nullable=False,
            comment='分类来源：sys_category.type',
        ),
        sa.Column('description', sa.String(length=500), server_default='', nullable=False, comment='备注说明'),
        sa.Column('sheet_map', _compatible_json(), nullable=True, comment='资源类型 -> 子表名称'),
        sa.Column('category_options', _compatible_json(), nullable=True, comment='分类列下拉选项'),
        sa.Column('source_weights', _compatible_json(), nullable=True, comment='来源 -> 随机权重'),
        sa.Column('paid_sheets', _compatible_json(), nullable=True, comment='允许出现「店铺购买」来源的子表'),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False, comment='是否启用'),
        sa.Column('cron', sa.String(length=128), nullable=True, comment='定时表达式'),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=True, comment='配置结束时间'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True, comment='最近同步时间'),
        *_base_columns(),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_feishu_sheet_config_name'),
        comment='飞书表格导出配置表',
    )
    op.create_index('ix_feishu_sheet_config_id', 'feishu_sheet_config', ['id'], unique=True)
    op.create_index('idx_feishu_sheet_config_enabled', 'feishu_sheet_config', ['is_enabled'], unique=False)


def _create_task_table() -> None:
    op.create_table(
        'feishu_sheet_task',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('config_id', sa.BigInteger(), nullable=False, comment='导出配置 ID'),
        sa.Column('status', sa.String(length=16), server_default='pending', nullable=False, comment='任务状态'),
        sa.Column('statistics', _compatible_json(), nullable=True, comment='任务统计信息'),
        sa.Column('error_message', sa.Text(), nullable=True, comment='错误信息'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True, comment='开始时间'),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True, comment='完成时间'),
        *_base_columns(),
        sa.ForeignKeyConstraint(['config_id'], ['feishu_sheet_config.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed','cancelled')",
            name='ck_feishu_sheet_task_status',
        ),
        comment='飞书表格导出任务表',
    )
    op.create_index('ix_feishu_sheet_task_id', 'feishu_sheet_task', ['id'], unique=True)
    op.create_index(
        'idx_feishu_sheet_task_config_status', 'feishu_sheet_task', ['config_id', 'status'], unique=False
    )


def _seed_gongkao_config(bind: Connection) -> None:
    """写入「公考」配置（已存在则跳过，可重复执行）"""
    table = sa.Table(
        'feishu_sheet_config',
        sa.MetaData(),
        sa.Column('id', sa.BigInteger()),
        sa.Column('name', sa.String(length=128)),
        sa.Column('description', sa.String(length=500)),
        sa.Column('app_code', sa.String(length=64)),
        sa.Column('category_type', sa.String(length=64)),
        sa.Column('sheet_url', sa.String(length=512)),
        sa.Column('sheet_map', _compatible_json()),
        sa.Column('category_options', _compatible_json()),
        sa.Column('source_weights', _compatible_json()),
        sa.Column('paid_sheets', _compatible_json()),
        sa.Column('is_enabled', sa.Boolean()),
        sa.Column('cron', sa.String(length=128)),
        sa.Column('created_time', sa.DateTime(timezone=True)),
        sa.Column('updated_time', sa.DateTime(timezone=True)),
    )
    exists = bind.execute(sa.select(table.c.id).where(table.c.name == GONGKAO_NAME)).scalar_one_or_none()
    if exists is not None:
        return

    bind.execute(
        table.insert().values(
            name=GONGKAO_NAME,
            description='公考资源同步到飞书表格（自 plugin.toml 迁移）',
            app_code=GONGKAO_APP_CODE,
            category_type=GONGKAO_CATEGORY_TYPE,
            sheet_url=GONGKAO_SHEET_URL,
            sheet_map=GONGKAO_SHEET_MAP,
            category_options=GONGKAO_CATEGORY_OPTIONS,
            source_weights=GONGKAO_SOURCE_WEIGHTS,
            paid_sheets=GONGKAO_PAID_SHEETS,
            is_enabled=True,
            cron=GONGKAO_CRON,
            created_time=sa.func.now(),
            updated_time=sa.func.now(),
        )
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, 'feishu_sheet_config'):
        _create_config_table()
    if not _has_table(bind, 'feishu_sheet_task'):
        _create_task_table()
    _seed_gongkao_config(bind)


def downgrade() -> None:
    bind = op.get_bind()
    if _has_table(bind, 'feishu_sheet_task'):
        op.drop_table('feishu_sheet_task')
    if _has_table(bind, 'feishu_sheet_config'):
        op.drop_table('feishu_sheet_config')
