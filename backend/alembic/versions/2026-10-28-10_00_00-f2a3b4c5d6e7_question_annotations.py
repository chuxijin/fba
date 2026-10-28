"""User text annotations and immutable attempt snapshots.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
"""

import sqlalchemy as sa

from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    json_type = sa.JSON().with_variant(JSONB(), 'postgresql')
    inspector = sa.inspect(op.get_bind())
    if 'annotations' not in {column['name'] for column in inspector.get_columns('qbank_v2_question_attempt')}:
        op.add_column(
            'qbank_v2_question_attempt',
            sa.Column('annotations', json_type, nullable=False, server_default=sa.text("'[]'")),
        )
    if inspector.has_table('qbank_v2_question_annotation'):
        return
    op.create_table(
        'qbank_v2_question_annotation',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.BigInteger(), sa.ForeignKey('sys_user.id', ondelete='CASCADE'), nullable=False),
        sa.Column(
            'question_id', sa.BigInteger(), sa.ForeignKey('qbank_v2_question.id', ondelete='CASCADE'), nullable=False
        ),
        sa.Column('context_key', sa.String(80), nullable=False),
        sa.Column('annotations', json_type, nullable=False, server_default=sa.text("'[]'")),
        sa.Column('save_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_time', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('deleted_time', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('user_id', 'question_id', 'context_key', name='uq_qbv2_annotation_context'),
        sa.CheckConstraint('save_version >= 1', name='ck_qbv2_annotation_version'),
        comment='用户题干与材料高亮批注',
    )


def downgrade() -> None:
    op.drop_table('qbank_v2_question_annotation')
    op.drop_column('qbank_v2_question_attempt', 'annotations')
