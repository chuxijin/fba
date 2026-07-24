#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add spatial cube patterns

Revision ID: f6a7b8c9d012
Revises: e5f6a7b8c901
Create Date: 2026-07-22 17:00:00.000000

"""
import sqlalchemy as sa

from alembic import op

revision = 'f6a7b8c9d012'
down_revision = 'e5f6a7b8c901'
branch_labels = None
depends_on = None

PATTERNS = [
    ('corner', '直角线', 360),
    ('slash', '斜线', 180),
    ('parallel', '平行线', 180),
    ('circle', '圆圈', 90),
    ('cross', '十字', 90),
    ('triangle', '三角', 360),
    ('square', '方块', 90),
    ('dot', '圆点', 90),
    ('diamond', '菱形', 90),
    ('arrow', '箭头', 360),
    ('bar', '横条', 180),
    ('chevron', 'V 形', 360),
    ('plus-tilt', '斜十字', 90),
    ('crescent', '月牙', 360),
]


def upgrade() -> None:
    """新增六面体面素材表并初始化内置素材"""
    table = op.create_table(
        'study_spatial_cube_pattern',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('code', sa.String(length=64), nullable=False, comment='素材编码'),
        sa.Column('name', sa.String(length=64), nullable=False, comment='素材名称'),
        sa.Column('render_type', sa.String(length=16), nullable=False, server_default='builtin', comment='渲染类型'),
        sa.Column('asset_url', sa.String(length=1024), nullable=True, comment='远程素材 URL'),
        sa.Column(
            'asset_version',
            sa.String(length=64),
            nullable=False,
            server_default='1',
            comment='素材版本',
        ),
        sa.Column('rotation_period', sa.SmallInteger(), nullable=False, server_default='360', comment='旋转等价周期'),
        sa.Column('sort', sa.Integer(), nullable=False, server_default='0', comment='排序'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true(), comment='是否启用'),
        sa.Column('created_by', sa.BigInteger(), nullable=False, server_default='0', comment='创建者'),
        sa.Column('updated_by', sa.BigInteger(), nullable=True, comment='修改者'),
        sa.Column(
            'created_time',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment='创建时间',
        ),
        sa.Column(
            'updated_time',
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.func.now(),
            comment='更新时间',
        ),
        sa.Column(
            'deleted',
            sa.BigInteger(),
            nullable=False,
            server_default='0',
            comment='是否已删除（0：否；id：是）',
        ),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.CheckConstraint("render_type IN ('builtin','image')", name='ck_study_spatial_cube_pattern_render_type'),
        sa.CheckConstraint('rotation_period IN (90, 180, 360)', name='ck_study_spatial_cube_pattern_rotation_period'),
        sa.PrimaryKeyConstraint('id'),
        comment='六面体面素材表',
    )
    op.create_index('ix_study_spatial_cube_pattern_code', 'study_spatial_cube_pattern', ['code'], unique=True)
    op.create_index('ix_study_spatial_cube_pattern_id', 'study_spatial_cube_pattern', ['id'], unique=True)
    op.create_index(
        'idx_study_spatial_cube_pattern_active_sort',
        'study_spatial_cube_pattern',
        ['is_active', 'sort'],
    )
    op.bulk_insert(
        table,
        [
            {
                'code': code,
                'name': name,
                'render_type': 'builtin',
                'asset_url': None,
                'asset_version': 'builtin-v1',
                'rotation_period': rotation_period,
                'sort': index,
                'is_active': True,
                'created_by': 0,
                'deleted': 0,
            }
            for index, (code, name, rotation_period) in enumerate(PATTERNS)
        ],
    )


def downgrade() -> None:
    """删除六面体面素材表"""
    op.drop_index('idx_study_spatial_cube_pattern_active_sort', table_name='study_spatial_cube_pattern')
    op.drop_index('ix_study_spatial_cube_pattern_id', table_name='study_spatial_cube_pattern')
    op.drop_index('ix_study_spatial_cube_pattern_code', table_name='study_spatial_cube_pattern')
    op.drop_table('study_spatial_cube_pattern')
