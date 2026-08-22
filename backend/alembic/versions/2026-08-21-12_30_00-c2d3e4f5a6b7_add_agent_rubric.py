"""add agent rubric cache

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
"""

import sqlalchemy as sa

from alembic import op

revision = 'c2d3e4f5a6b7'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_rubric',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('agent_key', sa.String(64), nullable=False),
        sa.Column('question_id', sa.BigInteger(), nullable=False),
        sa.Column('reference_set_hash', sa.String(64), nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('rubric_version', sa.String(64), nullable=False),
        sa.Column('status', sa.String(24), server_default='ready', nullable=False),
        sa.Column('provider', sa.String(128), nullable=True),
        sa.Column('model_name', sa.String(128), nullable=True),
        sa.Column('rubric_payload', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'agent_key',
            'question_id',
            'reference_set_hash',
            'source_hash',
            'rubric_version',
            name='uq_agent_rubric_source',
        ),
        comment='Agent 可复用评分基准表',
    )
    op.create_index('idx_agent_rubric_question', 'agent_rubric', ['agent_key', 'question_id', 'status'])


def downgrade() -> None:
    op.drop_index('idx_agent_rubric_question', table_name='agent_rubric')
    op.drop_table('agent_rubric')
