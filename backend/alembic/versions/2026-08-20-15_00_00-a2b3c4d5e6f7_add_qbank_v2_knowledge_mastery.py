"""add question bank v2 knowledge mastery projections

Revision ID: a2b3c4d5e6f7
Revises: f1b2c3d4e5f6
Create Date: 2026-08-20 15:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = 'a2b3c4d5e6f7'
down_revision = 'f1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create immutable attempt mapping snapshots and user mastery projections."""
    op.create_table(
        'qbank_v2_question_attempt_knowledge_point',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('attempt_id', sa.BigInteger(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('question_id', sa.BigInteger(), nullable=False),
        sa.Column('system_id', sa.BigInteger(), nullable=False),
        sa.Column('knowledge_point_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False, server_default='primary'),
        sa.Column('weight', sa.Numeric(precision=7, scale=6), nullable=False),
        sa.Column('source', sa.String(length=16), nullable=False, server_default='manual'),
        sa.Column('correctness', sa.Numeric(precision=7, scale=6), nullable=True),
        sa.Column('evidence_applied', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('graded_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ['attempt_id'],
            ['qbank_v2_question_attempt.id'],
            ondelete='CASCADE',
            name='fk_qbv2_attempt_kp_snapshot_attempt',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['sys_user.id'], ondelete='CASCADE', name='fk_qbv2_attempt_kp_snapshot_user'
        ),
        sa.ForeignKeyConstraint(
            ['question_id'], ['qbank_v2_question.id'], ondelete='RESTRICT', name='fk_qbv2_attempt_kp_snapshot_question'
        ),
        sa.ForeignKeyConstraint(
            ['system_id'],
            ['qbank_v2_knowledge_system.id'],
            ondelete='RESTRICT',
            name='fk_qbv2_attempt_kp_snapshot_system',
        ),
        sa.ForeignKeyConstraint(
            ['knowledge_point_id'],
            ['qbank_v2_knowledge_point.id'],
            ondelete='RESTRICT',
            name='fk_qbv2_attempt_kp_snapshot_point',
        ),
        sa.CheckConstraint("role IN ('primary','secondary','prerequisite')", name='ck_qbv2_attempt_kp_role'),
        sa.CheckConstraint('weight > 0 AND weight <= 1', name='ck_qbv2_attempt_kp_weight'),
        sa.CheckConstraint('correctness IS NULL OR correctness BETWEEN 0 AND 1', name='ck_qbv2_attempt_kp_correctness'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'attempt_id', 'system_id', 'knowledge_point_id', 'deleted', name='uq_qbv2_attempt_kp_snapshot'
        ),
        comment='作答发生时的题目知识点关联快照',
    )
    op.create_index(
        'ix_qbv2_attempt_kp_user_system_point',
        'qbank_v2_question_attempt_knowledge_point',
        ['user_id', 'system_id', 'knowledge_point_id'],
    )
    op.create_index(
        'ix_qbv2_attempt_kp_attempt',
        'qbank_v2_question_attempt_knowledge_point',
        ['attempt_id', 'system_id'],
    )

    op.create_table(
        'qbank_v2_user_knowledge_mastery',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('system_id', sa.BigInteger(), nullable=False),
        sa.Column('knowledge_point_id', sa.BigInteger(), nullable=False),
        sa.Column('mastery_score', sa.Numeric(precision=7, scale=6), nullable=False, server_default='0.500000'),
        sa.Column('confidence_score', sa.Numeric(precision=7, scale=6), nullable=False, server_default='0.000000'),
        sa.Column(
            'effective_sample_size', sa.Numeric(precision=14, scale=6), nullable=False, server_default='0.000000'
        ),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('weighted_correct', sa.Numeric(precision=14, scale=6), nullable=False, server_default='0.000000'),
        sa.Column('weighted_wrong', sa.Numeric(precision=14, scale=6), nullable=False, server_default='0.000000'),
        sa.Column(
            'lifetime_correct_weight', sa.Numeric(precision=14, scale=6), nullable=False, server_default='0.000000'
        ),
        sa.Column(
            'lifetime_wrong_weight', sa.Numeric(precision=14, scale=6), nullable=False, server_default='0.000000'
        ),
        sa.Column('last_attempt_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('state', sa.String(length=16), nullable=False, server_default='unknown'),
        sa.Column('model_version', sa.String(length=32), nullable=False, server_default='beta_decay_v1'),
        sa.Column('calculated_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['sys_user.id'], ondelete='CASCADE', name='fk_qbv2_user_kmastery_user'),
        sa.ForeignKeyConstraint(
            ['system_id'], ['qbank_v2_knowledge_system.id'], ondelete='RESTRICT', name='fk_qbv2_user_kmastery_system'
        ),
        sa.ForeignKeyConstraint(
            ['knowledge_point_id'],
            ['qbank_v2_knowledge_point.id'],
            ondelete='RESTRICT',
            name='fk_qbv2_user_kmastery_point',
        ),
        sa.CheckConstraint("state IN ('unknown','learning','stable','mastered')", name='ck_qbv2_user_kmastery_state'),
        sa.CheckConstraint('mastery_score BETWEEN 0 AND 1', name='ck_qbv2_user_kmastery_score'),
        sa.CheckConstraint('confidence_score BETWEEN 0 AND 1', name='ck_qbv2_user_kmastery_confidence'),
        sa.CheckConstraint('effective_sample_size >= 0', name='ck_qbv2_user_kmastery_effective_sample'),
        sa.CheckConstraint('attempt_count >= 0 AND correct_count >= 0', name='ck_qbv2_user_kmastery_count'),
        sa.CheckConstraint('correct_count <= attempt_count', name='ck_qbv2_user_kmastery_correct'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'user_id', 'system_id', 'knowledge_point_id', 'deleted', name='uq_qbv2_user_system_knowledge_mastery'
        ),
        comment='用户知识点掌握度投影',
    )
    op.create_index(
        'ix_qbv2_user_kmastery_scope',
        'qbank_v2_user_knowledge_mastery',
        ['user_id', 'system_id', 'state', 'knowledge_point_id'],
    )
    op.create_index(
        'ix_qbv2_user_kmastery_point',
        'qbank_v2_user_knowledge_mastery',
        ['knowledge_point_id', 'system_id', 'state'],
    )


def downgrade() -> None:
    """Drop knowledge mastery projections."""
    op.drop_index('ix_qbv2_user_kmastery_point', table_name='qbank_v2_user_knowledge_mastery')
    op.drop_index('ix_qbv2_user_kmastery_scope', table_name='qbank_v2_user_knowledge_mastery')
    op.drop_table('qbank_v2_user_knowledge_mastery')
    op.drop_index('ix_qbv2_attempt_kp_attempt', table_name='qbank_v2_question_attempt_knowledge_point')
    op.drop_index('ix_qbv2_attempt_kp_user_system_point', table_name='qbank_v2_question_attempt_knowledge_point')
    op.drop_table('qbank_v2_question_attempt_knowledge_point')
