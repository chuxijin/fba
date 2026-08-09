"""add study user knowledge profile

Revision ID: e6f7a8b9c012
Revises: d4e5f6a7b8c9
Create Date: 2026-08-01 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = 'e6f7a8b9c012'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增知识点画像表，并把分类画像收敛为只服务能力练习来源。"""
    op.create_table(
        'study_user_knowledge_profile',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False, comment='主键 ID'),
        sa.Column('user_id', sa.BigInteger(), nullable=False, comment='用户 ID'),
        sa.Column('knowledge_point_id', sa.BigInteger(), nullable=False, comment='题库 v2 知识点 ID'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0', comment='练习次数'),
        sa.Column('total_count', sa.Integer(), nullable=False, server_default='0', comment='总题数'),
        sa.Column('correct_count', sa.Integer(), nullable=False, server_default='0', comment='正确数'),
        sa.Column('duration_seconds', sa.Integer(), nullable=False, server_default='0', comment='总耗时秒'),
        sa.Column('accuracy_rate', sa.Numeric(6, 2), nullable=False, server_default='0', comment='正确率百分比'),
        sa.Column('avg_seconds', sa.Numeric(8, 2), nullable=True, comment='平均耗时秒'),
        sa.Column('mastery_score', sa.Numeric(6, 2), nullable=False, server_default='0', comment='掌握度'),
        sa.Column('speed_score', sa.Numeric(6, 2), nullable=False, server_default='0', comment='速度分'),
        sa.Column('confidence_score', sa.Numeric(6, 2), nullable=False, server_default='0', comment='可信度'),
        sa.Column('trend_score', sa.Numeric(6, 2), nullable=False, server_default='0', comment='趋势分'),
        sa.Column('weakness_score', sa.Numeric(6, 2), nullable=False, server_default='100', comment='薄弱度'),
        sa.Column('last_attempt_at', sa.DateTime(timezone=True), nullable=True, comment='最近练习时间'),
        sa.Column(
            'algorithm_version',
            sa.String(32),
            nullable=False,
            server_default='ability_profile_v1',
            comment='算法版本',
        ),
        sa.Column('created_time', sa.DateTime(timezone=True), nullable=False, comment='创建时间'),
        sa.Column('updated_time', sa.DateTime(timezone=True), nullable=True, comment='更新时间'),
        sa.Column('deleted', sa.BigInteger(), nullable=False, server_default='0', comment='删除标记'),
        sa.Column('deleted_time', sa.DateTime(timezone=True), nullable=True, comment='删除时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'knowledge_point_id', name='uq_study_user_knowledge_profile_point'),
        sa.CheckConstraint(
            'attempt_count >= 0 AND total_count >= 0 AND correct_count >= 0',
            name='ck_study_user_knowledge_profile_counts',
        ),
        sa.CheckConstraint('duration_seconds >= 0', name='ck_study_user_knowledge_profile_duration'),
        sa.ForeignKeyConstraint(['user_id'], ['study_user_account.user_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['knowledge_point_id'], ['qbank_v2_knowledge_point.id'], ondelete='RESTRICT'),
        comment='用户知识点画像表',
    )
    op.create_index('idx_study_user_knowledge_profile_user', 'study_user_knowledge_profile', ['user_id'])
    op.create_index('idx_study_user_knowledge_profile_point', 'study_user_knowledge_profile', ['knowledge_point_id'])
    op.create_index('idx_study_user_knowledge_profile_mastery', 'study_user_knowledge_profile', ['mastery_score'])

    # 题库来源画像已迁到知识点表，分类画像只保留能力练习来源
    op.execute("DELETE FROM study_user_category_profile WHERE source_type = 'question_bank'")
    op.drop_constraint('ck_study_user_category_profile_source', 'study_user_category_profile', type_='check')
    op.create_check_constraint(
        'ck_study_user_category_profile_source',
        'study_user_category_profile',
        "source_type IN ('ability')",
    )


def downgrade() -> None:
    """回滚知识点画像表并恢复分类画像的题库来源枚举。"""
    op.drop_constraint('ck_study_user_category_profile_source', 'study_user_category_profile', type_='check')
    op.create_check_constraint(
        'ck_study_user_category_profile_source',
        'study_user_category_profile',
        "source_type IN ('ability','question_bank')",
    )

    op.drop_index('idx_study_user_knowledge_profile_mastery', table_name='study_user_knowledge_profile')
    op.drop_index('idx_study_user_knowledge_profile_point', table_name='study_user_knowledge_profile')
    op.drop_index('idx_study_user_knowledge_profile_user', table_name='study_user_knowledge_profile')
    op.drop_table('study_user_knowledge_profile')
