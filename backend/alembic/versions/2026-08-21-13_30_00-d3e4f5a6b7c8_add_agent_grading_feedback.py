"""add agent grading feedback

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
"""

import sqlalchemy as sa

from alembic import op

revision = 'd3e4f5a6b7c8'
down_revision = 'c2d3e4f5a6b7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_grading_feedback',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('question_id', sa.BigInteger(), nullable=False),
        sa.Column('point_key', sa.String(80), nullable=False),
        sa.Column('scope', sa.String(16), server_default='report', nullable=False),
        sa.Column('corrected_status', sa.String(16), nullable=False),
        sa.Column('corrected_quote', sa.Text(), server_default='', nullable=False),
        sa.Column('note', sa.Text(), server_default='', nullable=False),
        sa.Column('before_snapshot', sa.JSON(), nullable=False),
        sa.Column('after_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['agent_run.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', 'point_key', 'scope', name='uq_agent_grading_feedback_point'),
        comment='申论批改人工纠正表',
    )
    op.create_index(
        'idx_agent_grading_feedback_question',
        'agent_grading_feedback',
        ['question_id', 'scope', 'created_time'],
    )


def downgrade() -> None:
    op.drop_index('idx_agent_grading_feedback_question', table_name='agent_grading_feedback')
    op.drop_table('agent_grading_feedback')
