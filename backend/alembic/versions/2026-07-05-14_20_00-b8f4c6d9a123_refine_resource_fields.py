#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""refine resource fields

Revision ID: b8f4c6d9a123
Revises: a27b51fe019b
Create Date: 2026-07-05 14:20:00.000000

"""
import sqlalchemy as sa

from alembic import op


revision = 'b8f4c6d9a123'
down_revision = 'a27b51fe019b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('yp_resource', sa.Column('org_name', sa.String(length=100), nullable=True, comment='机构或老师名称'))
    op.add_column('yp_resource', sa.Column('storage_key', sa.String(length=500), nullable=True, comment='存储对象 Key'))

    op.execute(
        """
        UPDATE yp_resource
        SET remark = COALESCE(NULLIF(BTRIM(remark), ''), NULLIF(BTRIM(main_name), ''))
        WHERE main_name IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE yp_resource
        SET resource_intro = COALESCE(NULLIF(BTRIM(resource_intro), ''), NULLIF(BTRIM(description), ''))
        WHERE description IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE yp_resource
        SET storage_key = local_file_path
        WHERE local_file_path IS NOT NULL
        """
    )

    op.drop_column('yp_resource', 'main_name')
    op.drop_column('yp_resource', 'description')
    op.drop_column('yp_resource', 'local_file_path')


def downgrade() -> None:
    op.add_column('yp_resource', sa.Column('main_name', sa.String(length=200), nullable=True, comment='主要名字'))
    op.add_column('yp_resource', sa.Column('description', sa.Text(), nullable=True, comment='描述'))
    op.add_column('yp_resource', sa.Column('local_file_path', sa.String(length=500), nullable=True, comment='本地文件路径'))

    op.execute(
        """
        UPDATE yp_resource
        SET main_name = COALESCE(NULLIF(BTRIM(remark), ''), NULLIF(BTRIM(title), ''), '未命名资源')
        """
    )
    op.execute(
        """
        UPDATE yp_resource
        SET description = resource_intro
        WHERE resource_intro IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE yp_resource
        SET local_file_path = storage_key
        WHERE storage_key IS NOT NULL
        """
    )
    op.alter_column('yp_resource', 'main_name', existing_type=sa.String(length=200), nullable=False)

    op.drop_column('yp_resource', 'storage_key')
    op.drop_column('yp_resource', 'org_name')
