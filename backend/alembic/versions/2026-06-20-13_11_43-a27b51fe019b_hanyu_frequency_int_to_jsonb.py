"""hanyu frequency int to jsonb

Revision ID: a27b51fe019b
Revises: 4f099e3f59fa
Create Date: 2026-06-20 13:11:43.483287

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a27b51fe019b'
down_revision = '4f099e3f59fa'
branch_labels = None
depends_on = None


def upgrade():
    # gk_hanyu.frequency: int → jsonb (数组存题目 ID)
    op.drop_index('ix_gk_hanyu_frequency', table_name='gk_hanyu')
    op.execute("ALTER TABLE gk_hanyu ALTER COLUMN frequency DROP NOT NULL")
    op.execute("ALTER TABLE gk_hanyu ALTER COLUMN frequency TYPE JSONB USING CASE WHEN frequency > 0 THEN '[]'::jsonb ELSE NULL END")
    op.execute("COMMENT ON COLUMN gk_hanyu.frequency IS '相关题目ID列表'")


def downgrade():
    op.alter_column(
        'gk_hanyu', 'frequency',
        existing_type=postgresql.JSONB(),
        type_=sa.INTEGER(),
        nullable=False,
        comment='使用频次',
        existing_comment='相关题目ID列表',
    )
    op.create_index('ix_gk_hanyu_frequency', 'gk_hanyu', ['frequency'], unique=False)
