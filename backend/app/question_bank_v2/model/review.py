from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key
from backend.utils.timezone import timezone

from .common import CompatibleJSONB

if TYPE_CHECKING:
    from .knowledge import QbKnowledgePoint
    from .question import QbQuestionRevision


class QbWrongQuestionState(Base, UserMixin):
    """Current wrong-book projection for one user and stable question."""

    __tablename__ = 'qbank_v2_wrong_question_state'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'question_id', 'deleted', name='uq_qbv2_wrong_user_question'),
        sa.UniqueConstraint('user_id', 'question_id', 'id', name='uq_qbv2_wrong_user_question_id'),
        sa.ForeignKeyConstraint(
            ['question_id', 'last_question_revision_id'],
            ['qbank_v2_question_revision.question_id', 'qbank_v2_question_revision.id'],
            name='fk_qbv2_wrong_last_revision',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'question_id', 'source_attempt_id'],
            [
                'qbank_v2_question_attempt.user_id',
                'qbank_v2_question_attempt.question_id',
                'qbank_v2_question_attempt.id',
            ],
            name='fk_qbv2_wrong_source_attempt',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['question_id', 'last_question_revision_id', 'source_bank_item_id'],
            ['qbank_v2_bank_item.question_id', 'qbank_v2_bank_item.question_revision_id', 'qbank_v2_bank_item.id'],
            name='fk_qbv2_wrong_bank_context',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            'source_bank_item_id IS NULL OR last_question_revision_id IS NOT NULL',
            name='ck_qbv2_wrong_bank_revision',
        ),
        sa.CheckConstraint("status IN ('active','resolved','suspended')", name='ck_qbv2_wrong_status'),
        sa.CheckConstraint('wrong_count >= 0 AND correct_streak >= 0', name='ck_qbv2_wrong_counts'),
        sa.Index('ix_qbv2_wrong_user_status', 'user_id', 'status', 'is_pinned', 'last_wrong_time'),
        sa.Index('ix_qbv2_wrong_question', 'question_id', 'status'),
        sa.Index('ix_qbv2_wrong_source_bank_item', 'source_bank_item_id'),
        {'comment': '用户错题本当前状态表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='RESTRICT'),
        comment='稳定题目 ID',
    )
    last_question_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='最近答错或复习的题目版本 ID',
    )
    source_attempt_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='最近触发错题状态的作答 ID',
    )
    source_bank_item_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='最近触发时的题库上下文',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='active/resolved/suspended')
    wrong_count: Mapped[int] = mapped_column(sa.Integer, default=1, comment='累计错误次数')
    correct_streak: Mapped[int] = mapped_column(sa.Integer, default=0, comment='错题重练连续正确次数')
    first_wrong_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='首次答错时间')
    last_wrong_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近答错时间')
    last_practice_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近重练时间')
    last_wrong_response: Mapped[Any | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='最近一次错误答案快照',
    )
    is_pinned: Mapped[bool] = mapped_column(default=False, comment='是否置顶')
    pinned_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='置顶时间')
    resolved_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='转为已解决时间')

    last_question_revision: Mapped[QbQuestionRevision | None] = relationship(
        init=False,
        foreign_keys=[question_id, last_question_revision_id],
        lazy='noload',
    )
    reviews: Mapped[list[QbQuestionReview]] = relationship(
        init=False,
        back_populates='wrong_state',
        cascade='save-update, merge',
        lazy='noload',
    )


class QbReviewTag(Base, UserMixin):
    """System or user-owned wrong-reason and solution-method tag."""

    __tablename__ = 'qbank_v2_review_tag'
    __table_args__ = (
        sa.CheckConstraint("tag_type IN ('reason','method','other')", name='ck_qbv2_review_tag_type'),
        sa.CheckConstraint('sort_order >= 0', name='ck_qbv2_review_tag_sort'),
        sa.Index(
            'uq_qbv2_review_tag_system_name',
            'name',
            unique=True,
            postgresql_where=sa.text('user_id IS NULL AND deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        sa.Index(
            'uq_qbv2_review_tag_user_name',
            'user_id',
            'name',
            unique=True,
            postgresql_where=sa.text('user_id IS NOT NULL AND deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        sa.Index('ix_qbv2_review_tag_user_type', 'user_id', 'tag_type', 'sort_order'),
        {'comment': '错题复盘标签定义表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='标签名称')
    user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        default=None,
        comment='用户自定义标签所有者；系统标签为空',
    )
    tag_type: Mapped[str] = mapped_column(sa.String(16), default='reason', comment='reason/method/other')
    color: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='展示颜色')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='展示顺序')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否可选')


class QbQuestionReview(Base, UserMixin):
    """Append-oriented wrong-question review event and learner reflection."""

    __tablename__ = 'qbank_v2_question_review'
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['question_id', 'question_revision_id'],
            ['qbank_v2_question_revision.question_id', 'qbank_v2_question_revision.id'],
            name='fk_qbv2_review_question_revision',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'question_id', 'wrong_state_id'],
            [
                'qbank_v2_wrong_question_state.user_id',
                'qbank_v2_wrong_question_state.question_id',
                'qbank_v2_wrong_question_state.id',
            ],
            name='fk_qbv2_review_wrong_state',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'question_id', 'source_attempt_id'],
            [
                'qbank_v2_question_attempt.user_id',
                'qbank_v2_question_attempt.question_id',
                'qbank_v2_question_attempt.id',
            ],
            name='fk_qbv2_review_source_attempt',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['question_id', 'question_revision_id', 'bank_item_id'],
            ['qbank_v2_bank_item.question_id', 'qbank_v2_bank_item.question_revision_id', 'qbank_v2_bank_item.id'],
            name='fk_qbv2_review_bank_context',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint('duration_ms >= 0', name='ck_qbv2_review_duration'),
        sa.CheckConstraint(
            "outcome IN ('continue','mastered','reopened')",
            name='ck_qbv2_review_outcome',
        ),
        sa.Index('ix_qbv2_review_user_time', 'user_id', 'reviewed_time'),
        sa.Index('ix_qbv2_review_question_time', 'question_id', 'reviewed_time'),
        sa.Index('ix_qbv2_review_wrong_state', 'wrong_state_id', 'reviewed_time'),
        {'comment': '用户错题复盘事件表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='稳定题目 ID')
    question_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='本次复盘看到的题目版本 ID')
    wrong_state_id: Mapped[int] = mapped_column(sa.BigInteger, comment='错题当前状态 ID')
    source_attempt_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='本次复盘关联的作答 ID',
    )
    bank_item_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='本次复盘题库上下文',
    )
    duration_ms: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='复盘用时毫秒')
    summary: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='学习者复盘总结')
    outcome: Mapped[str] = mapped_column(sa.String(16), default='continue', comment='复盘后的错题状态意图')
    review_data: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='防错策略等可扩展结构化内容',
    )
    reviewed_time: Mapped[datetime] = mapped_column(
        TimeZone,
        default_factory=timezone.now,
        comment='复盘发生时间',
    )

    wrong_state: Mapped[QbWrongQuestionState] = relationship(
        init=False,
        back_populates='reviews',
        foreign_keys=[user_id, question_id, wrong_state_id],
        lazy='noload',
    )
    question_revision: Mapped[QbQuestionRevision] = relationship(
        init=False,
        foreign_keys=[question_id, question_revision_id],
        overlaps='reviews,wrong_state',
        lazy='noload',
    )
    tags: Mapped[list[QbQuestionReviewTag]] = relationship(
        init=False,
        back_populates='review',
        cascade='all, delete-orphan',
        lazy='noload',
    )
    knowledge_points: Mapped[list[QbQuestionReviewKnowledgePoint]] = relationship(
        init=False,
        back_populates='review',
        cascade='all, delete-orphan',
        lazy='noload',
    )


class QbQuestionReviewTag(Base):
    """Normalized review-to-reason/method tag association."""

    __tablename__ = 'qbank_v2_question_review_tag'
    __table_args__ = (
        sa.UniqueConstraint('review_id', 'tag_id', 'deleted', name='uq_qbv2_review_tag_link'),
        sa.Index('ix_qbv2_review_tag_reverse', 'tag_id', 'review_id'),
        {'comment': '复盘记录与复盘标签关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    review_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_review.id', ondelete='CASCADE'),
        comment='复盘记录 ID',
    )
    tag_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_review_tag.id', ondelete='RESTRICT'),
        comment='复盘标签 ID',
    )

    review: Mapped[QbQuestionReview] = relationship(init=False, back_populates='tags', lazy='noload')
    tag: Mapped[QbReviewTag] = relationship(init=False, lazy='noload')


class QbQuestionReviewKnowledgePoint(Base):
    """Knowledge point selected by the learner during a review event."""

    __tablename__ = 'qbank_v2_question_review_knowledge_point'
    __table_args__ = (
        sa.UniqueConstraint('review_id', 'knowledge_point_id', 'deleted', name='uq_qbv2_review_kp_link'),
        sa.Index('ix_qbv2_review_kp_reverse', 'knowledge_point_id', 'review_id'),
        {'comment': '复盘记录与知识点关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    review_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question_review.id', ondelete='CASCADE'),
        comment='复盘记录 ID',
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_knowledge_point.id', ondelete='RESTRICT'),
        comment='知识点 ID',
    )

    review: Mapped[QbQuestionReview] = relationship(
        init=False,
        back_populates='knowledge_points',
        lazy='noload',
    )
    knowledge_point: Mapped[QbKnowledgePoint] = relationship(init=False, lazy='noload')
