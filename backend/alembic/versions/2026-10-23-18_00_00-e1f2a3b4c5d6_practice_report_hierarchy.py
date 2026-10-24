"""add imported practice reports and direct submodules

Revision ID: e1f2a3b4c5d6
Revises: d9e0f1a2b3c4
"""

import sqlalchemy as sa

from alembic import op

revision = 'e1f2a3b4c5d6'
down_revision = 'd9e0f1a2b3c4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    log_columns = {column['name'] for column in inspector.get_columns('gongkao_practice_log')}
    for column in (
        sa.Column('subject_name', sa.String(100), nullable=False, server_default='行测'),
        sa.Column('source_platform', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('source_key', sa.String(128)),
        sa.Column('source_url', sa.String(512)),
        sa.Column('source_updated_at', sa.DateTime(timezone=True)),
        sa.Column('time_source', sa.String(24), nullable=False, server_default='manual'),
        sa.Column('unanswered_count', sa.Integer()),
        sa.Column('score', sa.Numeric(10, 2)),
        sa.Column('full_score', sa.Numeric(10, 2)),
    ):
        if column.name not in log_columns:
            op.add_column('gongkao_practice_log', column)
    if 'uq_gk_practice_log_source' not in {c['name'] for c in inspector.get_unique_constraints('gongkao_practice_log')}:
        op.create_unique_constraint(
            'uq_gk_practice_log_source', 'gongkao_practice_log', ['user_id', 'source_platform', 'source_key']
        )
    module_columns = {column['name'] for column in inspector.get_columns('gongkao_practice_module')}
    if 'parent_id' not in module_columns:
        op.add_column('gongkao_practice_module', sa.Column('parent_id', sa.BigInteger()))
    if 'unanswered_count' not in module_columns:
        op.add_column('gongkao_practice_module', sa.Column('unanswered_count', sa.Integer()))
    if 'fk_gk_practice_module_parent' not in {c['name'] for c in inspector.get_foreign_keys('gongkao_practice_module')}:
        op.create_foreign_key(
            'fk_gk_practice_module_parent',
            'gongkao_practice_module',
            'gongkao_practice_module',
            ['parent_id'],
            ['id'],
            ondelete='CASCADE',
        )
    if 'idx_gk_practice_module_parent_id' not in {c['name'] for c in inspector.get_indexes('gongkao_practice_module')}:
        op.create_index('idx_gk_practice_module_parent_id', 'gongkao_practice_module', ['parent_id'])


def downgrade() -> None:
    op.drop_index('idx_gk_practice_module_parent_id', table_name='gongkao_practice_module')
    op.drop_constraint('fk_gk_practice_module_parent', 'gongkao_practice_module', type_='foreignkey')
    op.drop_column('gongkao_practice_module', 'unanswered_count')
    op.drop_column('gongkao_practice_module', 'parent_id')
    op.drop_constraint('uq_gk_practice_log_source', 'gongkao_practice_log', type_='unique')
    for name in (
        'full_score',
        'score',
        'unanswered_count',
        'time_source',
        'source_updated_at',
        'source_url',
        'source_key',
        'source_platform',
        'subject_name',
    ):
        op.drop_column('gongkao_practice_log', name)
