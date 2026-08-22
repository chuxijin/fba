"""add agent run audit tables

Revision ID: b1c2d3e4f5a6
Revises: a2b3c4d5e6f7
Create Date: 2026-08-21 10:00:00.000000
"""

import sqlalchemy as sa

from alembic import op

revision = 'b1c2d3e4f5a6'
down_revision = 'a2b3c4d5e6f7'
branch_labels = None
depends_on = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), server_default='0', nullable=False, comment='是否已删除'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
    ]


def upgrade() -> None:
    op.create_table(
        'agent_run',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('agent_key', sa.String(64), nullable=False),
        sa.Column('agent_version', sa.String(32), nullable=False),
        sa.Column('workflow_key', sa.String(64), nullable=False),
        sa.Column('workflow_version', sa.String(32), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('subject_type', sa.String(64), nullable=False),
        sa.Column('subject_id', sa.BigInteger(), nullable=False),
        sa.Column('idempotency_key', sa.String(160), nullable=False),
        sa.Column('status', sa.String(24), server_default='queued', nullable=False),
        sa.Column('stage', sa.String(64), nullable=True),
        sa.Column('progress', sa.Float(), server_default='0', nullable=False),
        sa.Column('input_snapshot', sa.JSON(), nullable=False),
        sa.Column('result_summary', sa.Text(), nullable=True),
        sa.Column('result_payload', sa.JSON(), nullable=True),
        sa.Column('config_snapshot', sa.JSON(), nullable=False),
        sa.Column('error_code', sa.String(64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_time', sa.DateTime(timezone=True), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE', name='fk_agent_run_user'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('idempotency_key', name='uq_agent_run_idempotency_key'),
        comment='Agent 运行任务表',
    )
    op.create_index('idx_agent_run_user_status', 'agent_run', ['user_id', 'status', 'created_time'])
    op.create_index('idx_agent_run_subject', 'agent_run', ['subject_type', 'subject_id', 'created_time'])
    op.create_index('idx_agent_run_agent_key', 'agent_run', ['agent_key', 'workflow_key', 'created_time'])

    op.create_table(
        'agent_run_step',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.BigInteger(), nullable=False),
        sa.Column('step_no', sa.Integer(), nullable=False),
        sa.Column('node_key', sa.String(64), nullable=False),
        sa.Column('status', sa.String(24), server_default='running', nullable=False),
        sa.Column('input_snapshot', sa.JSON(), nullable=False),
        sa.Column('output_snapshot', sa.JSON(), nullable=True),
        sa.Column('model_name', sa.String(128), nullable=True),
        sa.Column('tokens_in', sa.Integer(), server_default='0', nullable=False),
        sa.Column('tokens_out', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duration_ms', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_time', sa.DateTime(timezone=True), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(['run_id'], ['agent_run.id'], ondelete='CASCADE', name='fk_agent_run_step_run'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('run_id', 'step_no', name='uq_agent_run_step_no'),
        comment='Agent 节点执行轨迹表',
    )
    op.create_index('idx_agent_run_step_run', 'agent_run_step', ['run_id', 'step_no'])


def downgrade() -> None:
    op.drop_index('idx_agent_run_step_run', table_name='agent_run_step')
    op.drop_table('agent_run_step')
    op.drop_index('idx_agent_run_agent_key', table_name='agent_run')
    op.drop_index('idx_agent_run_subject', table_name='agent_run')
    op.drop_index('idx_agent_run_user_status', table_name='agent_run')
    op.drop_table('agent_run')
