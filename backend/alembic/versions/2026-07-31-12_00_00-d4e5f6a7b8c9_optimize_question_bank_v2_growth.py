"""optimize question bank v2 growth

Revision ID: d4e5f6a7b8c9
Revises: 3cfca8c7baa5
Create Date: 2026-07-31 12:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

revision = 'd4e5f6a7b8c9'
down_revision = '3cfca8c7baa5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add indexes for user-scoped growing timelines."""
    if op.get_bind().dialect.name != 'postgresql':
        return

    with op.get_context().autocommit_block():
        op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
        op.create_index(
            'ix_qbv2_brev_name_trgm',
            'qbank_v2_bank_revision',
            ['name'],
            if_not_exists=True,
            postgresql_using='gin',
            postgresql_ops={'name': 'gin_trgm_ops'},
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_mrev_title_trgm',
            'qbank_v2_material_revision',
            ['title'],
            if_not_exists=True,
            postgresql_using='gin',
            postgresql_ops={'title': 'gin_trgm_ops'},
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_question_stem_trgm',
            'qbank_v2_question',
            ['stem'],
            if_not_exists=True,
            postgresql_using='gin',
            postgresql_ops={'stem': 'gin_trgm_ops'},
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_session_user_created',
            'qbank_v2_practice_session',
            ['user_id', sa.text('created_time DESC'), sa.text('id DESC')],
            if_not_exists=True,
            postgresql_where=sa.text('deleted = 0'),
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_wrong_user_due',
            'qbank_v2_wrong_question_state',
            ['user_id', 'next_practice_time', 'id'],
            if_not_exists=True,
            postgresql_where=sa.text("deleted = 0 AND status = 'active' AND next_practice_time IS NOT NULL"),
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_review_user_review_time',
            'qbank_v2_question_review',
            ['user_id', 'reviewed_time', 'id'],
            if_not_exists=True,
            postgresql_where=sa.text("deleted = 0 AND event_type = 'review'"),
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_review_wrong_state_page',
            'qbank_v2_question_review',
            ['wrong_state_id', sa.text('reviewed_time DESC'), sa.text('id DESC')],
            if_not_exists=True,
            postgresql_where=sa.text('deleted = 0'),
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_favorite_user_page',
            'qbank_v2_question_favorite',
            [
                'user_id',
                sa.text('is_pinned DESC'),
                sa.text('pinned_time DESC'),
                sa.text('created_time DESC'),
                sa.text('id DESC'),
            ],
            if_not_exists=True,
            postgresql_where=sa.text('deleted = 0'),
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_note_user_page',
            'qbank_v2_question_note',
            ['user_id', sa.text('updated_time DESC'), sa.text('id DESC')],
            if_not_exists=True,
            postgresql_where=sa.text('deleted = 0'),
            postgresql_concurrently=True,
        )
        op.create_index(
            'ix_qbv2_note_public_page',
            'qbank_v2_question_note',
            [
                'question_id',
                sa.text('is_featured DESC'),
                sa.text('like_count DESC'),
                sa.text('id DESC'),
            ],
            if_not_exists=True,
            postgresql_where=sa.text("deleted = 0 AND visibility = 'public' AND status = 'published'"),
            postgresql_concurrently=True,
        )


def downgrade() -> None:
    """Drop user-scoped growth indexes."""
    if op.get_bind().dialect.name != 'postgresql':
        return

    with op.get_context().autocommit_block():
        for index_name, table_name in (
            ('ix_qbv2_question_stem_trgm', 'qbank_v2_question'),
            ('ix_qbv2_mrev_title_trgm', 'qbank_v2_material_revision'),
            ('ix_qbv2_brev_name_trgm', 'qbank_v2_bank_revision'),
            ('ix_qbv2_note_public_page', 'qbank_v2_question_note'),
            ('ix_qbv2_note_user_page', 'qbank_v2_question_note'),
            ('ix_qbv2_favorite_user_page', 'qbank_v2_question_favorite'),
            ('ix_qbv2_review_wrong_state_page', 'qbank_v2_question_review'),
            ('ix_qbv2_review_user_review_time', 'qbank_v2_question_review'),
            ('ix_qbv2_wrong_user_due', 'qbank_v2_wrong_question_state'),
            ('ix_qbv2_session_user_created', 'qbank_v2_practice_session'),
        ):
            op.drop_index(
                index_name,
                table_name=table_name,
                if_exists=True,
                postgresql_concurrently=True,
            )
