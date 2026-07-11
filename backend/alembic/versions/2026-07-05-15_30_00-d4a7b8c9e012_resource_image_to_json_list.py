#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""resource image to json

Revision ID: d4a7b8c9e012
Revises: c3e2d4f6a789
Create Date: 2026-07-05 15:30:00.000000

"""
import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision = 'd4a7b8c9e012'
down_revision = 'c3e2d4f6a789'
branch_labels = None
depends_on = None

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


def upgrade() -> None:
    """将资源图片迁移为 JSONB"""
    op.alter_column(
        'yp_resource',
        'resource_image',
        existing_type=sa.String(length=500),
        type_=CompatibleJSONB,
        existing_nullable=True,
        comment='资源图片 JSON',
        existing_comment='资源图片',
        postgresql_using=(
            "CASE "
            "WHEN resource_image IS NULL OR NULLIF(BTRIM(resource_image), '') IS NULL THEN NULL "
            "WHEN LEFT(BTRIM(resource_image), 1) IN ('[', '{') THEN resource_image::jsonb "
            "ELSE jsonb_build_array(resource_image) "
            "END"
        ),
    )


def downgrade() -> None:
    """将资源图片 JSON 回退为单图片链接"""
    op.alter_column(
        'yp_resource',
        'resource_image',
        existing_type=CompatibleJSONB,
        type_=sa.String(length=500),
        existing_nullable=True,
        comment='资源图片',
        existing_comment='资源图片 JSON',
        postgresql_using=(
            "CASE "
            "WHEN resource_image IS NULL THEN NULL "
            "WHEN jsonb_typeof(resource_image) = 'array' THEN resource_image ->> 0 "
            "WHEN jsonb_typeof(resource_image) = 'string' THEN resource_image #>> '{}' "
            "ELSE resource_image::text "
            "END"
        ),
    )
