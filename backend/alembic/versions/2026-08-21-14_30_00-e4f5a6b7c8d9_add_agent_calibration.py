"""add agent calibration anchors and policies

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
"""

import sqlalchemy as sa

from alembic import op

revision = 'e4f5a6b7c8d9'
down_revision = 'd3e4f5a6b7c8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'agent_calibration_anchor',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('agent_key', sa.String(64), nullable=False),
        sa.Column('bank_revision_id', sa.BigInteger(), nullable=False),
        sa.Column('session_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('actual_score_percent', sa.Numeric(7, 3), nullable=False),
        sa.Column('predicted_score_percent', sa.Numeric(7, 3), nullable=False),
        sa.Column('actual_total_score', sa.Numeric(10, 3), nullable=False),
        sa.Column('predicted_total_score', sa.Numeric(10, 3), nullable=False),
        sa.Column('paper_total_score', sa.Numeric(10, 3), nullable=False),
        sa.Column('source_type', sa.String(32), nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.String(16), server_default='ready', nullable=False),
        sa.Column('exclusion_reason', sa.Text(), nullable=True),
        sa.Column('metadata_payload', sa.JSON(), nullable=False),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_key', 'session_id', name='uq_agent_calibration_anchor_session'),
        comment='Agent 整卷人工校准锚点表',
    )
    op.create_index(
        'idx_agent_calibration_anchor_ready',
        'agent_calibration_anchor',
        ['agent_key', 'status', 'bank_revision_id'],
    )
    op.create_index(
        'idx_agent_calibration_anchor_session',
        'agent_calibration_anchor',
        ['session_id', 'created_time'],
    )

    op.create_table(
        'agent_calibration_policy',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('agent_key', sa.String(64), nullable=False),
        sa.Column('policy_version', sa.String(64), nullable=False),
        sa.Column('scope_type', sa.String(24), nullable=False),
        sa.Column('scope_key', sa.String(160), nullable=False),
        sa.Column('active_key', sa.String(192), nullable=True),
        sa.Column('status', sa.String(16), server_default='draft', nullable=False),
        sa.Column('anchor_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('paper_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('source_hash', sa.String(64), nullable=False),
        sa.Column('policy_payload', sa.JSON(), nullable=False),
        sa.Column('metrics_payload', sa.JSON(), nullable=False),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_key', 'source_hash', name='uq_agent_calibration_policy_source'),
        sa.UniqueConstraint('agent_key', 'active_key', name='uq_agent_calibration_policy_active'),
        comment='Agent 校准策略版本表',
    )
    op.create_index(
        'idx_agent_calibration_policy_scope',
        'agent_calibration_policy',
        ['agent_key', 'scope_type', 'scope_key', 'status'],
    )


def downgrade() -> None:
    op.drop_index('idx_agent_calibration_policy_scope', table_name='agent_calibration_policy')
    op.drop_table('agent_calibration_policy')
    op.drop_index('idx_agent_calibration_anchor_session', table_name='agent_calibration_anchor')
    op.drop_index('idx_agent_calibration_anchor_ready', table_name='agent_calibration_anchor')
    op.drop_table('agent_calibration_anchor')
