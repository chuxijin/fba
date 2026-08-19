#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key
from backend.utils.timezone import timezone

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class MemoryCardDeck(Base, UserMixin):
    """记忆卡组表"""

    __tablename__ = 'memory_card_deck'
    __table_args__ = (
        sa.UniqueConstraint('code', 'deleted', name='uq_memory_deck_code'),
        sa.CheckConstraint(
            "scope IN ('system','personal')",
            name='ck_memory_deck_scope',
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled','archived')",
            name='ck_memory_deck_status',
        ),
        sa.Index('ix_memory_deck_scope_status', 'scope', 'status'),
        sa.Index('ix_memory_deck_owner', 'owner_id'),
        sa.Index('ix_memory_deck_category', 'category_id'),
        {'comment': '记忆卡组表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='稳定业务编码')
    name: Mapped[str] = mapped_column(sa.String(120), comment='卡组名称')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='卡组描述')
    category_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='SET NULL'),
        default=None,
        comment='所属领域分类 ID（考公/考研等）',
    )
    scope: Mapped[str] = mapped_column(sa.String(16), default='system', comment='system 公共 / personal 私人')
    owner_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        default=None,
        comment='私人卡组所有者，公共卡组为空',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='active/disabled/archived')
    daily_new_limit: Mapped[int] = mapped_column(sa.Integer, default=20, comment='默认每日新卡上限')
    daily_review_limit: Mapped[int] = mapped_column(sa.Integer, default=200, comment='默认每日复习上限')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    settings: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, default_factory=dict, comment='卡组扩展配置')

    cards: Mapped[list['MemoryCard']] = relationship(
        init=False,
        back_populates='deck',
        cascade='save-update, merge',
        lazy='noload',
    )


class MemoryCard(Base, UserMixin):
    """记忆卡表"""

    __tablename__ = 'memory_card'
    __table_args__ = (
        sa.UniqueConstraint('code', 'deleted', name='uq_memory_card_code'),
        sa.ForeignKeyConstraint(
            ['deck_id'],
            ['memory_card_deck.id'],
            name='fk_memory_card_deck',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            "card_type IN ('cloze','correction')",
            name='ck_memory_card_type',
        ),
        sa.CheckConstraint(
            "response_mode IN ('reveal','input','choice','select_replace')",
            name='ck_memory_card_response_mode',
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled','archived')",
            name='ck_memory_card_status',
        ),
        sa.Index('ix_memory_card_deck_status', 'deck_id', 'status'),
        sa.Index('ix_memory_card_group', 'deck_id', 'group_id'),
        {'comment': '记忆卡表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    deck_id: Mapped[int] = mapped_column(sa.BigInteger, comment='卡组 ID')
    code: Mapped[str] = mapped_column(sa.String(64), comment='稳定业务编码')
    title: Mapped[str] = mapped_column(sa.String(255), comment='卡片标题')
    group_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('memory_card_group.id', ondelete='SET NULL'),
        default=None,
        comment='所属分组（章/节）ID，空为卡组根目录',
    )
    card_type: Mapped[str] = mapped_column(sa.String(16), default='cloze', comment='记忆玩法')
    response_mode: Mapped[str] = mapped_column(sa.String(16), default='input', comment='作答交互')
    current_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='当前发布版本 ID',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='active/disabled/archived')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')

    deck: Mapped[MemoryCardDeck] = relationship(init=False, back_populates='cards', lazy='noload')
    revisions: Mapped[list['MemoryCardRevision']] = relationship(
        init=False,
        back_populates='card',
        cascade='save-update, merge',
        lazy='noload',
    )


class MemoryCardGroup(Base, UserMixin):
    """记忆卡分组表（章/节等多级目录）"""

    __tablename__ = 'memory_card_group'
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['deck_id'],
            ['memory_card_deck.id'],
            name='fk_memory_group_deck',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['parent_id'],
            ['memory_card_group.id'],
            name='fk_memory_group_parent',
            ondelete='CASCADE',
        ),
        sa.CheckConstraint(
            "status IN ('active','disabled','archived')",
            name='ck_memory_group_status',
        ),
        sa.Index('ix_memory_group_deck_parent', 'deck_id', 'parent_id', 'sort_order'),
        sa.Index('ix_memory_group_parent', 'parent_id'),
        {'comment': '记忆卡分组表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    deck_id: Mapped[int] = mapped_column(sa.BigInteger, comment='卡组 ID')
    name: Mapped[str] = mapped_column(sa.String(120), comment='分组名称（章/节）')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='父分组 ID，空为卡组一级分组',
    )
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='active/disabled/archived')


class MemoryCardRevision(Base, UserMixin):
    """记忆卡不可变内容版本表"""

    __tablename__ = 'memory_card_revision'
    __table_args__ = (
        sa.UniqueConstraint('card_id', 'revision_no', name='uq_memory_revision_no'),
        sa.ForeignKeyConstraint(
            ['card_id'],
            ['memory_card.id'],
            name='fk_memory_revision_card',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint('revision_no > 0', name='ck_memory_revision_no'),
        sa.CheckConstraint(
            "status IN ('draft','published','retired')",
            name='ck_memory_revision_status',
        ),
        sa.Index('ix_memory_revision_card_status', 'card_id', 'status', 'revision_no'),
        sa.Index('ix_memory_revision_hash', 'content_hash'),
        {'comment': '记忆卡不可变内容版本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    card_id: Mapped[int] = mapped_column(sa.BigInteger, comment='卡片 ID')
    revision_no: Mapped[int] = mapped_column(sa.Integer, comment='版本号，从 1 递增')
    content: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, comment='结构化卡片内容')
    content_hash: Mapped[str] = mapped_column(sa.String(64), comment='规范化内容 SHA-256')
    status: Mapped[str] = mapped_column(sa.String(16), default='published', comment='draft/published/retired')
    published_by: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='发布人 ID',
    )
    published_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发布时间')

    card: Mapped[MemoryCard] = relationship(init=False, back_populates='revisions', lazy='noload')


class MemoryCardSubscription(Base):
    """用户卡组订阅表"""

    __tablename__ = 'memory_card_subscription'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'deck_id', 'deleted', name='uq_memory_subscription'),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['sys_user.id'],
            name='fk_memory_subscription_user',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['deck_id'],
            ['memory_card_deck.id'],
            name='fk_memory_subscription_deck',
            ondelete='CASCADE',
        ),
        sa.CheckConstraint(
            "status IN ('active','paused')",
            name='ck_memory_subscription_status',
        ),
        sa.Index('ix_memory_subscription_user', 'user_id', 'status'),
        {'comment': '用户卡组订阅表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    deck_id: Mapped[int] = mapped_column(sa.BigInteger, comment='卡组 ID')
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='active/paused')
    daily_new_limit: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='自定义每日新卡上限')
    daily_review_limit: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='自定义每日复习上限')


class MemoryCardUserState(Base):
    """用户卡片 FSRS 记忆状态表"""

    __tablename__ = 'memory_card_user_state'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'card_id', 'deleted', name='uq_memory_user_card'),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['sys_user.id'],
            name='fk_memory_state_user',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['card_id'],
            ['memory_card.id'],
            name='fk_memory_state_card',
            ondelete='CASCADE',
        ),
        sa.CheckConstraint(
            "status IN ('active','suspended')",
            name='ck_memory_state_status',
        ),
        sa.CheckConstraint('state BETWEEN 0 AND 3', name='ck_memory_state_fsrs'),
        sa.CheckConstraint('review_count >= 0 AND lapse_count >= 0', name='ck_memory_state_counts'),
        sa.CheckConstraint('last_rating IS NULL OR last_rating BETWEEN 1 AND 4', name='ck_memory_state_rating'),
        sa.Index('ix_memory_state_user_due', 'user_id', 'status', 'due'),
        {'comment': '用户卡片 FSRS 记忆状态表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    card_id: Mapped[int] = mapped_column(sa.BigInteger, comment='卡片 ID')
    due: Mapped[datetime] = mapped_column(TimeZone, comment='下次到期时间')
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='active/suspended')
    # FSRS v6 核心字段
    state: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=0,
        comment='FSRS 状态(0 new 1 learning 2 review 3 relearning)',
    )
    step: Mapped[int | None] = mapped_column(sa.SmallInteger, default=0, comment='FSRS 学习步骤')
    stability: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='FSRS 稳定性(天)')
    difficulty: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='FSRS 难度')
    last_review: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='上次复习时间')
    # 业务字段
    learned_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='记忆状态基于的卡片版本 ID',
    )
    review_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计复习次数')
    lapse_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计遗忘次数')
    last_rating: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='最近评分 1-4')


class MemoryCardReviewLog(Base):
    """记忆卡复习日志表"""

    __tablename__ = 'memory_card_review_log'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'idempotency_key', 'deleted', name='uq_memory_review_idempotency'),
        sa.ForeignKeyConstraint(
            ['user_id'],
            ['sys_user.id'],
            name='fk_memory_review_user',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['card_id'],
            ['memory_card.id'],
            name='fk_memory_review_card',
            ondelete='CASCADE',
        ),
        sa.CheckConstraint(
            "check_result IN ('correct','wrong','undetermined')",
            name='ck_memory_review_check_result',
        ),
        sa.CheckConstraint('rating BETWEEN 1 AND 4', name='ck_memory_review_rating'),
        sa.CheckConstraint('duration_ms >= 0', name='ck_memory_review_duration'),
        sa.Index('ix_memory_review_user_time', 'user_id', 'reviewed_at'),
        sa.Index('ix_memory_review_user_card', 'user_id', 'card_id'),
        {'comment': '记忆卡复习日志表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    card_id: Mapped[int] = mapped_column(sa.BigInteger, comment='卡片 ID')
    idempotency_key: Mapped[str] = mapped_column(sa.String(128), comment='客户端幂等键')
    rating: Mapped[int] = mapped_column(sa.SmallInteger, comment='评分(1 Again 2 Hard 3 Good 4 Easy)')
    revision_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='复习时的卡片版本 ID')
    session_key: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='学习会话标识')
    check_result: Mapped[str] = mapped_column(
        sa.String(16),
        default='undetermined',
        comment='客观判定 correct/wrong/undetermined',
    )
    response_data: Mapped[Any | None] = mapped_column(CompatibleJSONB, default=None, comment='作答数据快照')
    revealed: Mapped[bool] = mapped_column(default=False, comment='是否先揭晓答案再评分')
    duration_ms: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='作答用时毫秒')
    prev_state: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='调度前 FSRS 状态')
    next_state: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='调度后 FSRS 状态')
    prev_due: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='调度前到期时间')
    next_due: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='调度后到期时间')
    prev_stability: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='调度前稳定性')
    next_stability: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='调度后稳定性')
    prev_difficulty: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='调度前难度')
    next_difficulty: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='调度后难度')
    reviewed_at: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='复习时间')
