from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key

from .common import CompatibleJSONB

if TYPE_CHECKING:
    from .question import QbQuestionRevision


class QbFavoriteFolder(Base, UserMixin):
    """User-owned folder for durable favorite organization."""

    __tablename__ = 'qbank_v2_favorite_folder'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'name', 'deleted', name='uq_qbv2_fav_folder_name'),
        sa.UniqueConstraint('user_id', 'id', name='uq_qbv2_fav_folder_user_id'),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_fav_folder_sort'),
        sa.CheckConstraint("status IN ('active','archived')", name='ck_qbv2_fav_folder_status'),
        sa.Index('ix_qbv2_fav_folder_user_order', 'user_id', 'status', 'sort_order'),
        {'comment': '用户题目收藏夹表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    name: Mapped[str] = mapped_column(sa.String(100), comment='收藏夹名称')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='收藏夹说明')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='用户内排序')
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='active/archived')

    favorites: Mapped[list[QbQuestionFavorite]] = relationship(
        init=False,
        back_populates='folder',
        cascade='save-update, merge',
        lazy='noload',
    )


class QbQuestionFavorite(Base, UserMixin):
    """Favorite follows a stable question while retaining save-time provenance."""

    __tablename__ = 'qbank_v2_question_favorite'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'question_id', 'deleted', name='uq_qbv2_favorite_user_question'),
        sa.ForeignKeyConstraint(
            ['question_id', 'source_revision_id'],
            ['qbank_v2_question_revision.question_id', 'qbank_v2_question_revision.id'],
            name='fk_qbv2_favorite_source_revision',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'folder_id'],
            ['qbank_v2_favorite_folder.user_id', 'qbank_v2_favorite_folder.id'],
            name='fk_qbv2_favorite_user_folder',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['question_id', 'source_revision_id', 'bank_item_id'],
            ['qbank_v2_bank_item.question_id', 'qbank_v2_bank_item.question_revision_id', 'qbank_v2_bank_item.id'],
            name='fk_qbv2_favorite_bank_context',
            ondelete='RESTRICT',
        ),
        sa.Index('ix_qbv2_favorite_user_folder', 'user_id', 'folder_id', 'is_pinned', 'created_time'),
        sa.Index('ix_qbv2_favorite_question', 'question_id'),
        sa.Index('ix_qbv2_favorite_bank_item', 'bank_item_id'),
        {'comment': '用户题目收藏表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='稳定题目 ID')
    source_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='收藏时看到的题目版本 ID')
    folder_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='收藏夹 ID')
    bank_item_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='收藏时的题库编排上下文',
    )
    tags: Mapped[list[str]] = mapped_column(CompatibleJSONB, default_factory=list, comment='轻量用户标签')
    remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='收藏备注')
    is_pinned: Mapped[bool] = mapped_column(default=False, comment='是否置顶')
    pinned_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='置顶时间')

    folder: Mapped[QbFavoriteFolder | None] = relationship(
        init=False,
        back_populates='favorites',
        foreign_keys=[user_id, folder_id],
        lazy='noload',
    )
    source_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        foreign_keys=[question_id, source_revision_id],
        lazy='noload',
    )


class QbQuestionNote(Base, UserMixin):
    """One canonical private or public note per user and stable question."""

    __tablename__ = 'qbank_v2_question_note'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'question_id', 'deleted', name='uq_qbv2_note_user_question'),
        sa.ForeignKeyConstraint(
            ['question_id', 'source_revision_id'],
            ['qbank_v2_question_revision.question_id', 'qbank_v2_question_revision.id'],
            name='fk_qbv2_note_source_revision',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['question_id', 'source_revision_id', 'bank_item_id'],
            ['qbank_v2_bank_item.question_id', 'qbank_v2_bank_item.question_revision_id', 'qbank_v2_bank_item.id'],
            name='fk_qbv2_note_bank_context',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint("content_format IN ('markdown','html','plain')", name='ck_qbv2_note_format'),
        sa.CheckConstraint("visibility IN ('private','public')", name='ck_qbv2_note_visibility'),
        sa.CheckConstraint(
            "status IN ('draft','published','hidden','rejected')",
            name='ck_qbv2_note_status',
        ),
        sa.CheckConstraint(
            'like_count >= 0 AND dislike_count >= 0 AND view_count >= 0',
            name='ck_qbv2_note_counts',
        ),
        sa.Index('ix_qbv2_note_user_updated', 'user_id', 'updated_time'),
        sa.Index('ix_qbv2_note_public_rank', 'question_id', 'visibility', 'status', 'like_count'),
        sa.Index('ix_qbv2_note_featured', 'is_featured', 'featured_time'),
        {'comment': '用户题目笔记表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='作者用户 ID',
    )
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='稳定题目 ID')
    source_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='笔记针对的题目版本 ID')
    content: Mapped[str] = mapped_column(UniversalText, comment='笔记正文')
    bank_item_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='创建笔记时的题库上下文',
    )
    content_format: Mapped[str] = mapped_column(sa.String(16), default='markdown', comment='正文格式')
    visibility: Mapped[str] = mapped_column(sa.String(16), default='private', comment='private/public')
    status: Mapped[str] = mapped_column(sa.String(16), default='draft', comment='发布与审核状态')
    like_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='点赞缓存')
    dislike_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='点踩缓存')
    view_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='浏览缓存')
    is_featured: Mapped[bool] = mapped_column(default=False, comment='是否精选')
    featured_by: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='精选操作人 ID',
    )
    featured_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='精选时间')
    moderation_note: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='审核备注')

    source_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        foreign_keys=[question_id, source_revision_id],
        lazy='noload',
    )
    votes: Mapped[list[QbQuestionNoteVote]] = relationship(
        init=False,
        back_populates='note',
        cascade='all, delete-orphan',
        lazy='noload',
    )


class QbQuestionNoteVote(Base):
    """Switchable up/down vote on a public question note."""

    __tablename__ = 'qbank_v2_question_note_vote'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'note_id', 'deleted', name='uq_qbv2_note_vote_user'),
        sa.CheckConstraint('vote_value IN (-1, 1)', name='ck_qbv2_note_vote_value'),
        sa.Index('ix_qbv2_note_vote_note', 'note_id', 'vote_value'),
        sa.Index('ix_qbv2_note_vote_user_time', 'user_id', 'created_time'),
        {'comment': '公开题目笔记投票表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='投票用户 ID',
    )
    note_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_note.id', ondelete='CASCADE'),
        comment='笔记 ID',
    )
    vote_value: Mapped[int] = mapped_column(sa.SmallInteger, comment='1 点赞，-1 点踩')

    note: Mapped[QbQuestionNote] = relationship(init=False, back_populates='votes', lazy='noload')


class QbQuestionFeedback(Base, UserMixin):
    """Moderated issue report pinned to the exact question revision seen."""

    __tablename__ = 'qbank_v2_question_feedback'
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['question_id', 'question_revision_id'],
            ['qbank_v2_question_revision.question_id', 'qbank_v2_question_revision.id'],
            name='fk_qbv2_feedback_question_revision',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['question_id', 'question_revision_id', 'bank_item_id'],
            ['qbank_v2_bank_item.question_id', 'qbank_v2_bank_item.question_revision_id', 'qbank_v2_bank_item.id'],
            name='fk_qbv2_feedback_bank_context',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            "category IN ('content','answer','explanation','format','duplicate','copyright','other')",
            name='ck_qbv2_feedback_category',
        ),
        sa.CheckConstraint(
            "status IN ('open','triaged','resolved','rejected')",
            name='ck_qbv2_feedback_status',
        ),
        sa.Index('ix_qbv2_feedback_status_created', 'status', 'category', 'created_time'),
        sa.Index('ix_qbv2_feedback_question', 'question_id', 'question_revision_id', 'status'),
        sa.Index('ix_qbv2_feedback_user_created', 'user_id', 'created_time'),
        {'comment': '题目问题反馈与处理表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='RESTRICT'),
        comment='反馈用户 ID',
    )
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='稳定题目 ID')
    question_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户看到的题目版本 ID')
    category: Mapped[str] = mapped_column(sa.String(24), comment='反馈分类')
    description: Mapped[str] = mapped_column(UniversalText, comment='反馈说明')
    bank_item_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='反馈发生的题库上下文',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='open', comment='处理状态')
    assignee_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='处理人 ID',
    )
    resolution: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='处理结论')
    resolved_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='处理完成时间')

    question_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        foreign_keys=[question_id, question_revision_id],
        lazy='noload',
    )
