"""drop preference FK constraints

Revision ID: 3cfca8c7baa5
Revises: b7c8d9e0f123
Create Date: 2026-07-30 21:14:57.614092

"""
import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = '3cfca8c7baa5'
down_revision = 'b7c8d9e0f123'
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {fk['name'] for fk in inspector.get_foreign_keys('qbank_v2_user_practice_preference')}
    for name in (
        'qbank_v2_user_practice_preference_current_category_id_fkey',
        'qbank_v2_user_practice_preferen_current_knowledge_point_id_fkey',
    ):
        if name in existing:
            op.drop_constraint(name, 'qbank_v2_user_practice_preference', type_='foreignkey')


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {fk['name'] for fk in inspector.get_foreign_keys('qbank_v2_user_practice_preference')}
    if 'qbank_v2_user_practice_preference_current_category_id_fkey' not in existing:
        op.create_foreign_key(
            'qbank_v2_user_practice_preference_current_category_id_fkey',
            'qbank_v2_user_practice_preference',
            'qbank_v2_collection',
            ['current_category_id'],
            ['id'],
            ondelete='SET NULL',
        )
    if 'qbank_v2_user_practice_preferen_current_knowledge_point_id_fkey' not in existing:
        op.create_foreign_key(
            'qbank_v2_user_practice_preferen_current_knowledge_point_id_fkey',
            'qbank_v2_user_practice_preference',
            'qbank_v2_knowledge_point',
            ['current_knowledge_point_id'],
            ['id'],
            ondelete='SET NULL',
        )
