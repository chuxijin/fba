#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, id_key
from backend.utils.timezone import timezone

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class ChallengeLevel(Base):
    """闯关关卡表"""

    __tablename__ = 'study_challenge_level'
    __table_args__ = (
        sa.UniqueConstraint('challenge_key', 'stage', 'level_no', name='uq_challenge_level_stage_no'),
        sa.UniqueConstraint('challenge_key', 'global_no', name='uq_challenge_level_global_no'),
        sa.Index('idx_challenge_level_key_status_sort', 'challenge_key', 'status', 'sort_order'),
        sa.CheckConstraint(
            "stage IN ('stage_1','stage_2','stage_3','stage_4')",
            name='ck_challenge_level_stage',
        ),
        sa.CheckConstraint("status IN ('draft','published','disabled')", name='ck_challenge_level_status'),
        sa.CheckConstraint('level_no > 0 AND global_no > 0', name='ck_challenge_level_number'),
        sa.CheckConstraint('question_count > 0', name='ck_challenge_level_question_count'),
        sa.CheckConstraint('time_limit >= 0', name='ck_challenge_level_time_limit'),
        sa.CheckConstraint(
            'pass_rate >= 0 AND pass_rate <= 100 '
            'AND star_two_rate >= pass_rate AND star_two_rate <= 100 '
            'AND star_three_rate >= star_two_rate AND star_three_rate <= 100',
            name='ck_challenge_level_rates',
        ),
        {'comment': '闯关关卡表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    challenge_key: Mapped[str] = mapped_column(sa.String(64), comment='闯关标识')
    stage: Mapped[str] = mapped_column(sa.String(16), comment='闯关阶段: stage_1/stage_2/stage_3/stage_4')
    level_no: Mapped[int] = mapped_column(sa.SmallInteger, comment='阶段内关卡号')
    global_no: Mapped[int] = mapped_column(sa.SmallInteger, comment='全局关卡序号')
    title: Mapped[str] = mapped_column(sa.String(128), comment='关卡名称')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='关卡描述')
    previous_level_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_challenge_level.id', ondelete='SET NULL'),
        default=None,
        comment='前置关卡 ID',
    )
    question_count: Mapped[int] = mapped_column(sa.SmallInteger, default=5, comment='题目数量')
    time_limit: Mapped[int] = mapped_column(sa.Integer, default=0, comment='建议用时（秒，0 不限制）')
    pass_rate: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), default=Decimal('80'), comment='通关正确率')
    star_two_rate: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2), default=Decimal('90'), comment='二星正确率'
    )
    star_three_rate: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2), default=Decimal('100'), comment='三星正确率'
    )
    required_section_pass: Mapped[bool] = mapped_column(default=False, comment='是否要求每个题目分组达标')
    display_config: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='前端展示配置')
    status: Mapped[str] = mapped_column(sa.String(16), default='draft', comment='状态: draft/published/disabled')
    config_version: Mapped[int] = mapped_column(sa.Integer, default=1, comment='配置版本')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    created_by: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='创建者 ID')
    updated_by: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='修改者 ID')

    sections: Mapped[list[ChallengeLevelSection]] = relationship(
        init=False,
        back_populates='level',
        lazy='noload',
        cascade='all, delete-orphan',
        order_by='ChallengeLevelSection.seq_no',
    )


class ChallengeLevelSection(Base):
    """闯关关卡题目分组表"""

    __tablename__ = 'study_challenge_level_section'
    __table_args__ = (
        sa.UniqueConstraint('level_id', 'seq_no', name='uq_challenge_level_section_seq'),
        sa.Index('idx_challenge_level_section_level_enabled', 'level_id', 'enabled'),
        sa.CheckConstraint("source_type IN ('fixed','pool','manual','generator')", name='ck_challenge_section_source'),
        sa.CheckConstraint('seq_no > 0 AND question_count > 0', name='ck_challenge_section_number'),
        sa.CheckConstraint(
            'required_correct_count IS NULL '
            'OR (required_correct_count >= 0 AND required_correct_count <= question_count)',
            name='ck_challenge_section_required_correct',
        ),
        {'comment': '闯关关卡题目分组表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    level_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_challenge_level.id', ondelete='CASCADE'),
        comment='关卡 ID',
    )
    seq_no: Mapped[int] = mapped_column(sa.SmallInteger, comment='分组顺序')
    source_type: Mapped[str] = mapped_column(sa.String(16), comment='题目来源')
    question_count: Mapped[int] = mapped_column(sa.SmallInteger, comment='抽题数量')
    name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='分组名称')
    source_config: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='题源配置')
    required_correct_count: Mapped[int | None] = mapped_column(
        sa.SmallInteger, default=None, comment='分组最低答对数量'
    )
    enabled: Mapped[bool] = mapped_column(default=True, comment='是否启用')

    level: Mapped[ChallengeLevel] = relationship(init=False, back_populates='sections', lazy='noload')


class ChallengeAttempt(Base):
    """闯关挑战记录表"""

    __tablename__ = 'study_challenge_attempt'
    __table_args__ = (
        sa.Index('idx_challenge_attempt_user_level_status', 'user_id', 'level_id', 'status'),
        sa.Index('idx_challenge_attempt_user_started', 'user_id', 'started_at'),
        sa.CheckConstraint("status IN ('in_progress','completed','abandoned')", name='ck_challenge_attempt_status'),
        sa.CheckConstraint(
            'question_count >= 0 AND completed_count >= 0 AND correct_count >= 0 AND wrong_count >= 0',
            name='ck_challenge_attempt_counts',
        ),
        sa.CheckConstraint('accuracy_rate >= 0 AND accuracy_rate <= 100', name='ck_challenge_attempt_accuracy'),
        sa.CheckConstraint('stars >= 0 AND stars <= 3', name='ck_challenge_attempt_stars'),
        {'comment': '闯关挑战记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    attempt_key: Mapped[str] = mapped_column(sa.String(32), unique=True, comment='挑战唯一标识')
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    level_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_challenge_level.id', ondelete='RESTRICT'),
        comment='关卡 ID',
    )
    level_version: Mapped[int] = mapped_column(sa.Integer, comment='关卡配置版本')
    question_count: Mapped[int] = mapped_column(sa.SmallInteger, comment='题目数量')
    status: Mapped[str] = mapped_column(sa.String(16), default='in_progress', comment='挑战状态')
    completed_count: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='已作答数量')
    correct_count: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='答对数量')
    wrong_count: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='答错数量')
    accuracy_rate: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), default=Decimal('0'), comment='正确率')
    stars: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='星级')
    passed: Mapped[bool] = mapped_column(default=False, comment='本次是否达标')
    total_time: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总用时（秒）')
    rule_snapshot: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='通关规则快照')
    started_at: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='开始时间')
    completed_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')


class UserChallengeProgress(Base):
    """用户闯关进度表"""

    __tablename__ = 'study_user_challenge_progress'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'level_id', name='uq_user_challenge_progress_level'),
        sa.Index('idx_user_challenge_progress_user_passed', 'user_id', 'passed'),
        sa.CheckConstraint('best_stars >= 0 AND best_stars <= 3', name='ck_user_challenge_progress_stars'),
        sa.CheckConstraint('best_accuracy >= 0 AND best_accuracy <= 100', name='ck_user_challenge_progress_accuracy'),
        sa.CheckConstraint('attempt_count >= 0', name='ck_user_challenge_progress_attempts'),
        {'comment': '用户闯关进度表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    level_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_challenge_level.id', ondelete='CASCADE'),
        comment='关卡 ID',
    )
    passed: Mapped[bool] = mapped_column(default=False, comment='是否通过')
    best_stars: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='最佳星级')
    best_accuracy: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2), default=Decimal('0'), comment='最佳正确率'
    )
    best_time: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='最短通关用时（秒）')
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='挑战次数')
    last_attempt_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_challenge_attempt.id', ondelete='SET NULL'),
        default=None,
        comment='最近挑战 ID',
    )
    passed_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='首次通过时间')
