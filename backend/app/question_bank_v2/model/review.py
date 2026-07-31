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


class QbWrongQuestionState(Base, UserMixin):
    """Current wrong-book projection for one user and stable question."""

    __tablename__ = 'qbank_v2_wrong_question_state'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'question_id', 'deleted', name='uq_qbv2_wrong_user_question'),
        sa.UniqueConstraint('user_id', 'question_id', 'id', name='uq_qbv2_wrong_user_question_id'),
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
            ['question_id', 'source_bank_item_id'],
            ['qbank_v2_bank_item.question_id', 'qbank_v2_bank_item.id'],
            name='fk_qbv2_wrong_bank_context',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            "entry_source IN ('attempt','manual','ocr','import')",
            name='ck_qbv2_wrong_entry_source',
        ),
        sa.CheckConstraint("status IN ('active','resolved','suspended')", name='ck_qbv2_wrong_status'),
        sa.CheckConstraint('wrong_count >= 0 AND correct_streak >= 0', name='ck_qbv2_wrong_counts'),
        sa.CheckConstraint('review_count >= 0 AND practice_level >= 0', name='ck_qbv2_wrong_review_counts'),
        sa.CheckConstraint('last_rating IS NULL OR last_rating BETWEEN 1 AND 4', name='ck_qbv2_wrong_rating'),
        sa.Index('ix_qbv2_wrong_user_status', 'user_id', 'status', 'is_pinned', 'last_wrong_time', 'id'),
        sa.Index('ix_qbv2_wrong_question', 'question_id', 'status'),
        sa.Index('ix_qbv2_wrong_source_bank_item', 'source_bank_item_id'),
        # 推送扫描：单表 partial index，只覆盖仍在错题本且已排期的行
        sa.Index(
            'ix_qbv2_wrong_push_due',
            'next_practice_time',
            'user_id',
            'id',
            postgresql_where=sa.text("deleted = 0 AND status = 'active' AND next_practice_time IS NOT NULL"),
        ).ddl_if(dialect='postgresql'),
        # 用户到期列表：按用户定位后扫描到期时间，避免扫描全站到期数据。
        sa.Index(
            'ix_qbv2_wrong_user_due',
            'user_id',
            'next_practice_time',
            'id',
            postgresql_where=sa.text("deleted = 0 AND status = 'active' AND next_practice_time IS NOT NULL"),
        ).ddl_if(dialect='postgresql'),
        # 复盘档案：只索引复盘过的行，考前回顾不受错题本状态影响
        sa.Index(
            'ix_qbv2_wrong_reviewed',
            'user_id',
            'last_reviewed_time',
            'id',
            postgresql_where=sa.text('deleted = 0 AND review_count > 0'),
        ).ddl_if(dialect='postgresql'),
        # 待复盘队列
        sa.Index(
            'ix_qbv2_wrong_unreviewed',
            'user_id',
            'last_wrong_time',
            'id',
            postgresql_where=sa.text("deleted = 0 AND review_count = 0 AND status = 'active'"),
        ).ddl_if(dialect='postgresql'),
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
    entry_source: Mapped[str] = mapped_column(
        sa.String(16),
        default='attempt',
        comment='首次进入错题本的来源: attempt/manual/ocr/import',
    )
    entry_metadata: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='外部来源、OCR 置信度和采集上下文',
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

    # 复盘线：用户主动填写，不参与自动调度
    review_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='真正复盘次数，不含录入事件')
    last_reviewed_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近复盘时间')

    # 重练线：由客观作答自动推进，next_practice_time 是推送的唯一真相源
    practice_level: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='重练阶梯等级')
    last_rating: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='最近派生等级 1-4')
    last_duration_ms: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='最近一次作答用时，下次派生等级的对比基线',
    )
    next_practice_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='下次重练时间')

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
            ['question_id', 'bank_item_id'],
            ['qbank_v2_bank_item.question_id', 'qbank_v2_bank_item.id'],
            name='fk_qbv2_review_bank_context',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint('duration_ms >= 0', name='ck_qbv2_review_duration'),
        sa.CheckConstraint(
            "event_type IN ('capture','review')",
            name='ck_qbv2_review_event_type',
        ),
        sa.UniqueConstraint('user_id', 'idempotency_key', 'deleted', name='uq_qbv2_review_idempotency'),
        sa.Index('ix_qbv2_review_user_time', 'user_id', 'reviewed_time'),
        sa.Index(
            'ix_qbv2_review_user_review_time',
            'user_id',
            'reviewed_time',
            'id',
            postgresql_where=sa.text("deleted = 0 AND event_type = 'review'"),
        ).ddl_if(dialect='postgresql'),
        sa.Index('ix_qbv2_review_question_time', 'question_id', 'reviewed_time'),
        sa.Index('ix_qbv2_review_wrong_state', 'wrong_state_id', 'reviewed_time'),
        sa.Index(
            'ix_qbv2_review_wrong_state_page',
            'wrong_state_id',
            sa.desc('reviewed_time'),
            sa.desc('id'),
            postgresql_where=sa.text('deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        {'comment': '用户错题复盘事件表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='稳定题目 ID')
    wrong_state_id: Mapped[int] = mapped_column(sa.BigInteger, comment='错题当前状态 ID')
    idempotency_key: Mapped[str] = mapped_column(sa.String(128), comment='客户端复盘提交幂等键')
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
    event_type: Mapped[str] = mapped_column(sa.String(16), default='review', comment='capture/review')
    duration_ms: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='复盘用时毫秒')
    summary: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='学习者复盘总结')
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
