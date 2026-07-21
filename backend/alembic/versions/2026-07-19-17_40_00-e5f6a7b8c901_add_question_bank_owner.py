#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""add question bank owner

Revision ID: e5f6a7b8c901
Revises: d4a7b8c9e012
Create Date: 2026-07-19 17:40:00.000000

"""
import sqlalchemy as sa

from alembic import op

revision = 'e5f6a7b8c901'
down_revision = 'd4a7b8c9e012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """添加私人题库归属字段"""
    op.add_column(
        'study_question_bank',
        sa.Column(
            'owner_id',
            sa.BigInteger(),
            sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
            nullable=True,
            comment='所属用户 ID（NULL 表示公共题库）',
        ),
    )
    op.create_index('idx_study_question_bank_owner_category', 'study_question_bank', ['owner_id', 'cat_id'])


def downgrade() -> None:
    """删除私人题库归属字段"""
    op.drop_index('idx_study_question_bank_owner_category', table_name='study_question_bank')
    op.drop_column('study_question_bank', 'owner_id')
