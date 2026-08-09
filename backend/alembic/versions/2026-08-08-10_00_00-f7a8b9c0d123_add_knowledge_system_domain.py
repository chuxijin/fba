"""add knowledge system domain

Revision ID: f7a8b9c0d123
Revises: e6f7a8b9c012
Create Date: 2026-08-08 10:00:00.000000

"""

import sqlalchemy as sa

from alembic import op

from backend.app.question_bank_v2.model.common import CompatibleJSONB

revision = 'f7a8b9c0d123'
down_revision = 'e6f7a8b9c012'
branch_labels = None
depends_on = None

#: 存量知识体系统一归属公考领域（sys_category product_catalog 根）
LEGACY_GONGKAO_CATEGORY_ID = 1400


def upgrade() -> None:
    """知识体系加领域归属，并给用户偏好加按体系编码分桶的版本选择。"""
    op.add_column(
        'qbank_v2_knowledge_system',
        sa.Column(
            'domain_category_id',
            sa.BigInteger(),
            nullable=True,
            comment='所属领域分类 ID；指向 product_catalog 根分类',
        ),
    )

    # 存量体系全部是行测（公考），回填后再收紧为 NOT NULL
    op.execute(
        f'UPDATE qbank_v2_knowledge_system SET domain_category_id = {LEGACY_GONGKAO_CATEGORY_ID} '
        'WHERE domain_category_id IS NULL'
    )
    op.alter_column('qbank_v2_knowledge_system', 'domain_category_id', nullable=False)

    op.create_foreign_key(
        'fk_qbv2_ksystem_domain_category',
        'qbank_v2_knowledge_system',
        'sys_category',
        ['domain_category_id'],
        ['id'],
        ondelete='RESTRICT',
    )
    op.drop_constraint('uq_qbv2_ksystem_code_version', 'qbank_v2_knowledge_system', type_='unique')
    op.create_unique_constraint(
        'uq_qbv2_ksystem_domain_code_version',
        'qbank_v2_knowledge_system',
        ['domain_category_id', 'code', 'version', 'deleted'],
    )
    op.create_index(
        'ix_qbv2_ksystem_domain_version',
        'qbank_v2_knowledge_system',
        ['domain_category_id', 'code', 'version', 'status'],
    )

    op.add_column(
        'qbank_v2_user_practice_preference',
        sa.Column(
            'knowledge_system_choice',
            CompatibleJSONB,
            nullable=False,
            server_default='{}',
            comment='按知识体系编码隔离的选定版本；key 为 system code，value 为 system ID',
        ),
    )


def downgrade() -> None:
    """回滚领域归属与版本选择字段。"""
    op.drop_column('qbank_v2_user_practice_preference', 'knowledge_system_choice')

    op.drop_index('ix_qbv2_ksystem_domain_version', table_name='qbank_v2_knowledge_system')
    op.drop_constraint('uq_qbv2_ksystem_domain_code_version', 'qbank_v2_knowledge_system', type_='unique')
    op.create_unique_constraint(
        'uq_qbv2_ksystem_code_version',
        'qbank_v2_knowledge_system',
        ['code', 'version', 'deleted'],
    )
    op.drop_constraint('fk_qbv2_ksystem_domain_category', 'qbank_v2_knowledge_system', type_='foreignkey')
    op.drop_column('qbank_v2_knowledge_system', 'domain_category_id')
