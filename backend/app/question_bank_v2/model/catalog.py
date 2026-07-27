from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UniversalText, UserMixin, id_key

if TYPE_CHECKING:
    from backend.app.admin.model.category import Category

    from .bank import QbBank, QbBankRevision


class QbCollection(Base, UserMixin):
    """Navigation collection; it groups banks but never owns their content."""

    __tablename__ = 'qbank_v2_collection'
    __table_args__ = (
        sa.UniqueConstraint('code', 'deleted', name='uq_qbv2_collection_code_deleted'),
        sa.CheckConstraint(
            "visibility IN ('private','internal','public')",
            name='ck_qbv2_collection_visibility',
        ),
        sa.CheckConstraint(
            "status IN ('draft','active','archived')",
            name='ck_qbv2_collection_status',
        ),
        sa.CheckConstraint('parent_id IS NULL OR parent_id <> id', name='ck_qbv2_collection_not_self'),
        sa.Index('ix_qbv2_collection_parent_sort', 'parent_id', 'status', 'sort_order'),
        sa.Index('ix_qbv2_collection_owner_status', 'owner_id', 'status'),
        {'comment': '题库导航合集表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='合集业务编码')
    name: Mapped[str] = mapped_column(sa.String(128), comment='合集名称')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_collection.id', ondelete='SET NULL'),
        default=None,
        comment='父合集 ID；仅用于导航树',
    )
    owner_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='私有合集所有者；公共合集为空',
    )
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='合集描述')
    visibility: Mapped[str] = mapped_column(sa.String(16), default='public', comment='可见范围')
    status: Mapped[str] = mapped_column(sa.String(16), default='draft', comment='draft/active/archived')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='同层排序')

    parent: Mapped[QbCollection | None] = relationship(
        init=False,
        remote_side=lambda: [QbCollection.id],
        back_populates='children',
        lazy='noload',
    )
    children: Mapped[list[QbCollection]] = relationship(
        init=False,
        back_populates='parent',
        cascade='save-update, merge',
        lazy='noload',
    )
    bank_memberships: Mapped[list[QbCollectionBank]] = relationship(
        init=False,
        back_populates='collection',
        cascade='all, delete-orphan',
        lazy='noload',
    )


class QbCollectionBank(Base, UserMixin):
    """Many-to-many mount from collections to reusable question banks."""

    __tablename__ = 'qbank_v2_collection_bank'
    __table_args__ = (
        sa.UniqueConstraint('collection_id', 'bank_id', 'deleted', name='uq_qbv2_collection_bank'),
        sa.ForeignKeyConstraint(
            ['bank_id', 'bank_revision_id'],
            ['qbank_v2_bank_revision.bank_id', 'qbank_v2_bank_revision.id'],
            name='fk_qbv2_collection_bank_pinned_revision',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            '(follow_latest AND bank_revision_id IS NULL) OR (NOT follow_latest AND bank_revision_id IS NOT NULL)',
            name='ck_qbv2_collection_bank_pin_mode',
        ),
        sa.Index('ix_qbv2_collection_bank_order', 'collection_id', 'is_active', 'sort_order'),
        sa.Index('ix_qbv2_collection_bank_reverse', 'bank_id', 'is_active'),
        {'comment': '合集与题库多对多挂载表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    collection_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_collection.id', ondelete='CASCADE'),
        comment='合集 ID',
    )
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_bank.id', ondelete='CASCADE'),
        comment='题库稳定身份 ID',
    )
    bank_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='固定展示的题库版本；跟随最新版时为空',
    )
    follow_latest: Mapped[bool] = mapped_column(default=True, comment='是否跟随题库当前发布版本')
    display_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='合集内展示别名')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='合集内排序')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用此挂载')

    collection: Mapped[QbCollection] = relationship(
        init=False,
        back_populates='bank_memberships',
        lazy='noload',
    )
    bank: Mapped[QbBank] = relationship(
        init=False,
        foreign_keys=[bank_id],
        back_populates='collection_memberships',
        overlaps='pinned_revision',
        lazy='noload',
    )
    pinned_revision: Mapped[QbBankRevision | None] = relationship(
        init=False,
        foreign_keys=[bank_id, bank_revision_id],
        viewonly=True,
        overlaps='bank,collection_memberships',
        lazy='noload',
    )


class QbBankCategory(Base, UserMixin):
    """Business taxonomy membership from a stable bank to ``sys_category``."""

    __tablename__ = 'qbank_v2_bank_category'
    __table_args__ = (
        sa.UniqueConstraint('bank_id', 'category_id', 'deleted', name='uq_qbv2_bank_category'),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_bank_category_sort'),
        sa.Index('ix_qbv2_bank_category_bank', 'bank_id', 'is_primary', 'sort_order'),
        sa.Index(
            'ix_qbv2_bank_category_reverse',
            'category_id',
            'deleted',
            'is_primary',
            'sort_order',
            'bank_id',
        ),
        sa.Index(
            'uq_qbv2_bank_category_primary',
            'bank_id',
            unique=True,
            postgresql_where=sa.text('is_primary AND deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        {'comment': '题库与系统业务分类关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_bank.id', ondelete='CASCADE'),
        comment='题库稳定身份 ID',
    )
    category_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='RESTRICT'),
        comment='系统业务分类 ID',
    )
    is_primary: Mapped[bool] = mapped_column(default=False, comment='是否题库主分类')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='分类内题库排序')

    bank: Mapped[QbBank] = relationship(
        init=False,
        back_populates='category_memberships',
        lazy='noload',
    )
    category: Mapped[Category] = relationship(init=False, lazy='noload')
