from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key

from .common import BankKind, CompatibleJSONB, ContentStatus

if TYPE_CHECKING:
    from .catalog import QbBankCategory, QbCollectionBank
    from .question import QbQuestion


class QbBank(Base, UserMixin):
    """Stable bank identity independent from collections and editions."""

    __tablename__ = 'qbank_v2_bank'
    __table_args__ = (
        sa.UniqueConstraint('code', 'deleted', name='uq_qbv2_bank_code_deleted'),
        sa.ForeignKeyConstraint(
            ['id', 'current_revision_id'],
            ['qbank_v2_bank_revision.bank_id', 'qbank_v2_bank_revision.id'],
            name='fk_qbv2_bank_current_revision',
            ondelete='RESTRICT',
            use_alter=True,
        ),
        sa.CheckConstraint(
            "visibility IN ('private','internal','public')",
            name='ck_qbv2_bank_visibility',
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled','archived')",
            name='ck_qbv2_bank_status',
        ),
        sa.Index('ix_qbv2_bank_owner_status', 'owner_id', 'status'),
        sa.Index('ix_qbv2_bank_visibility_status', 'visibility', 'status'),
        {'comment': '题库稳定身份表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='稳定业务编码')
    owner_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='私有题库所有者；公共题库为空',
    )
    current_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='当前发布版本 ID',
    )
    visibility: Mapped[str] = mapped_column(sa.String(16), default='public', comment='可见范围')
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='身份状态')

    current_revision: Mapped[QbBankRevision | None] = relationship(
        init=False,
        foreign_keys=lambda: [QbBank.id, QbBank.current_revision_id],
        post_update=True,
        lazy='noload',
    )
    revisions: Mapped[list[QbBankRevision]] = relationship(
        init=False,
        back_populates='bank',
        foreign_keys=lambda: [QbBankRevision.bank_id],
        cascade='save-update, merge',
        lazy='noload',
    )
    collection_memberships: Mapped[list[QbCollectionBank]] = relationship(
        init=False,
        back_populates='bank',
        foreign_keys='QbCollectionBank.bank_id',
        cascade='save-update, merge',
        overlaps='pinned_revision',
        lazy='noload',
    )
    category_memberships: Mapped[list[QbBankCategory]] = relationship(
        init=False,
        back_populates='bank',
        cascade='all, delete-orphan',
        lazy='noload',
    )


class QbBankRevision(Base, UserMixin):
    """Immutable composition edition once published."""

    __tablename__ = 'qbank_v2_bank_revision'
    __table_args__ = (
        sa.UniqueConstraint('bank_id', 'revision_no', name='uq_qbv2_brev_bank_no'),
        sa.UniqueConstraint('bank_id', 'id', name='uq_qbv2_brev_bank_id'),
        sa.CheckConstraint('revision_no > 0', name='ck_qbv2_brev_revision_no'),
        sa.CheckConstraint("bank_kind IN ('practice','paper','mock')", name='ck_qbv2_brev_kind'),
        sa.CheckConstraint(
            "status IN ('draft','published','retired')",
            name='ck_qbv2_brev_status',
        ),
        sa.CheckConstraint('duration_minutes IS NULL OR duration_minutes > 0', name='ck_qbv2_brev_duration'),
        sa.CheckConstraint('pass_score IS NULL OR pass_score >= 0', name='ck_qbv2_brev_pass_score'),
        sa.CheckConstraint('question_count >= 0', name='ck_qbv2_brev_question_count'),
        sa.CheckConstraint('total_score >= 0', name='ck_qbv2_brev_total_score'),
        sa.Index('ix_qbv2_brev_bank_status', 'bank_id', 'status', 'revision_no'),
        sa.Index('ix_qbv2_brev_kind_status', 'bank_kind', 'status'),
        {'comment': '题库不可变版本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_bank.id', ondelete='RESTRICT'),
        comment='题库身份 ID',
    )
    revision_no: Mapped[int] = mapped_column(sa.Integer, comment='版本号，从 1 递增')
    name: Mapped[str] = mapped_column(sa.String(160), comment='此版本题库名称')
    bank_kind: Mapped[str] = mapped_column(
        sa.String(16),
        default=BankKind.practice.value,
        comment='practice/paper/mock',
    )
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='题库描述')
    cover_asset_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_asset.id', ondelete='SET NULL'),
        default=None,
        comment='托管封面资产 ID',
    )
    cover_url: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='封面地址')
    duration_minutes: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='限时分钟数')
    pass_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='及格分')
    settings: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='抽题、展示、交卷等版本级策略',
    )
    question_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='发布时计算的题量快照')
    total_score: Mapped[Decimal] = mapped_column(
        sa.Numeric(10, 2),
        default=Decimal('0.00'),
        comment='发布时计算的总分快照',
    )
    content_hash: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='编排内容 SHA-256')
    status: Mapped[str] = mapped_column(
        sa.String(16),
        default=ContentStatus.draft.value,
        comment='draft/published/retired',
    )
    published_by: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='发布人 ID',
    )
    published_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发布时间')

    bank: Mapped[QbBank] = relationship(
        init=False,
        back_populates='revisions',
        foreign_keys=[bank_id],
        lazy='noload',
    )
    sections: Mapped[list[QbBankSection]] = relationship(
        init=False,
        back_populates='bank_revision',
        cascade='save-update, merge',
        overlaps='children,parent',
        lazy='noload',
    )
    items: Mapped[list[QbBankItem]] = relationship(
        init=False,
        back_populates='bank_revision',
        cascade='save-update, merge',
        overlaps='section',
        lazy='noload',
    )


class QbBankSection(Base, UserMixin):
    """Section tree scoped to exactly one bank revision."""

    __tablename__ = 'qbank_v2_bank_section'
    __table_args__ = (
        sa.UniqueConstraint('bank_revision_id', 'id', name='uq_qbv2_section_revision_id'),
        sa.UniqueConstraint('bank_revision_id', 'code', 'deleted', name='uq_qbv2_section_code'),
        sa.ForeignKeyConstraint(
            ['bank_revision_id', 'parent_id'],
            ['qbank_v2_bank_section.bank_revision_id', 'qbank_v2_bank_section.id'],
            name='fk_qbv2_section_parent_same_revision',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint('parent_id IS NULL OR parent_id <> id', name='ck_qbv2_section_not_self'),
        sa.CheckConstraint('depth >= 0', name='ck_qbv2_section_depth'),
        sa.Index('ix_qbv2_section_parent_order', 'bank_revision_id', 'parent_id', 'sort_order'),
        {'comment': '题库版本章节表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    bank_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_bank_revision.id', ondelete='RESTRICT'),
        comment='题库版本 ID',
    )
    code: Mapped[str] = mapped_column(sa.String(64), comment='版本内章节编码')
    name: Mapped[str] = mapped_column(sa.String(160), comment='章节名称')
    parent_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='同题库版本内父章节 ID')
    depth: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='树深度')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='同层排序')

    bank_revision: Mapped[QbBankRevision] = relationship(
        init=False,
        back_populates='sections',
        foreign_keys=[bank_revision_id],
        overlaps='children,parent',
        lazy='noload',
    )
    parent: Mapped[QbBankSection | None] = relationship(
        init=False,
        remote_side=lambda: [QbBankSection.bank_revision_id, QbBankSection.id],
        foreign_keys=lambda: [QbBankSection.bank_revision_id, QbBankSection.parent_id],
        back_populates='children',
        overlaps='bank_revision,sections',
        lazy='noload',
    )
    children: Mapped[list[QbBankSection]] = relationship(
        init=False,
        foreign_keys=lambda: [QbBankSection.bank_revision_id, QbBankSection.parent_id],
        back_populates='parent',
        cascade='save-update, merge',
        overlaps='bank_revision,sections',
        lazy='noload',
    )
    items: Mapped[list[QbBankItem]] = relationship(
        init=False,
        back_populates='section',
        cascade='save-update, merge',
        overlaps='bank_revision,items',
        lazy='noload',
    )


class QbBankItem(Base, UserMixin):
    """Association object that pins a question revision in a bank edition."""

    __tablename__ = 'qbank_v2_bank_item'
    __table_args__ = (
        sa.UniqueConstraint('bank_revision_id', 'item_key', 'deleted', name='uq_qbv2_bitem_key'),
        sa.UniqueConstraint('bank_revision_id', 'question_id', 'deleted', name='uq_qbv2_bitem_question'),
        sa.UniqueConstraint('question_id', 'id', name='uq_qbv2_bitem_question_id'),
        sa.UniqueConstraint('bank_revision_id', 'question_id', 'id', name='uq_qbv2_bitem_revision_question_id'),
        sa.ForeignKeyConstraint(
            ['question_id'],
            ['qbank_v2_question.id'],
            name='fk_qbv2_bitem_question',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['bank_revision_id', 'section_id'],
            ['qbank_v2_bank_section.bank_revision_id', 'qbank_v2_bank_section.id'],
            name='fk_qbv2_bitem_section_same_revision',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint('score >= 0', name='ck_qbv2_bitem_score'),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_bitem_sort'),
        sa.Index('ix_qbv2_bitem_order', 'bank_revision_id', 'section_id', 'is_active', 'sort_order'),
        sa.Index('ix_qbv2_bitem_delivery', 'bank_revision_id', 'is_active', 'id'),
        sa.Index('ix_qbv2_bitem_year_delivery', 'bank_revision_id', 'exam_year', 'is_active', 'id'),
        sa.Index('ix_qbv2_bitem_question', 'question_id'),
        {'comment': '题库版本题目编排表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    bank_revision_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_bank_revision.id', ondelete='RESTRICT'),
        comment='题库版本 ID',
    )
    item_key: Mapped[str] = mapped_column(sa.String(64), comment='版本内稳定题号或业务键')
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题目身份 ID')
    section_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='同题库版本内章节 ID')
    exam_year: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='试题年份；非真题可为空')
    score: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), default=Decimal('1.00'), comment='本题分值')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='题目顺序')
    is_required: Mapped[bool] = mapped_column(default=True, comment='是否必答')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    settings: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='题目在此题库中的随机化、展示等上下文设置',
    )

    bank_revision: Mapped[QbBankRevision] = relationship(
        init=False,
        back_populates='items',
        foreign_keys=[bank_revision_id],
        overlaps='section,items',
        lazy='noload',
    )
    section: Mapped[QbBankSection | None] = relationship(
        init=False,
        foreign_keys=[bank_revision_id, section_id],
        back_populates='items',
        overlaps='bank_revision,items',
        lazy='noload',
    )
    question: Mapped[QbQuestion] = relationship(
        init=False,
        foreign_keys=[question_id],
        lazy='noload',
    )
