#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
练习刷题相关模型

包含：
- PracticeSession: 练习会话表
- PracticeRecord: 答题记录表
- WrongQuestionBook: 错题本表

设计参考：Moodle quiz_attempts + question_attempts 标准
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UserMixin, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from .question import Question
    from .user import UserAccount


class PracticeSession(Base, UserMixin):
    """
    练习会话表

    设计思路：
    - 用户每次开始练习时创建一个 Session
    - 该次练习的所有题目答题记录都关联到这个 Session
    - Session 中存储聚合统计数据，避免实时计算
    - 参考：Moodle quiz_attempts 表
    """

    __tablename__ = 'study_practice_session'
    __table_args__ = (
        sa.Index('idx_session_user_time', 'user_id', 'start_time'),
        sa.Index('idx_session_type_status', 'session_type', 'status'),
        sa.Index('idx_session_bank_chapter', 'bank_id', 'chapter_id'),
        {'comment': '练习会话表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.id', ondelete='CASCADE'),
        comment='用户 ID',
    )

    # ============ 会话信息 ============
    session_type: Mapped[str] = mapped_column(
        sa.String(32),
        comment="""练习类型：
        - chapter: 章节练习
        - bank: 题库练习
        - random: 随机练习
        - exam: 考试/试卷
        - wrong: 错题练习
        - favorite: 收藏练习
        """,
    )
    bank_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='SET NULL'),
        default=None,
        comment='题库 ID',
    )
    chapter_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_chapter.id', ondelete='SET NULL'),
        default=None,
        comment='章节 ID',
    )

    # ============ 题目信息 ============
    question_ids: Mapped[list[int] | None] = mapped_column(
        sa.JSON,
        default=None,
        comment='本次练习的题目 ID 列表 JSON: [1, 2, 3, ...]（可选字段，空间换时间）',
    )
    total_count: Mapped[int] = mapped_column(default=0, comment='题目总数')

    # ============ 完成统计（核心！避免实时计算） ============
    completed_count: Mapped[int] = mapped_column(default=0, comment='已完成数量')
    correct_count: Mapped[int] = mapped_column(default=0, comment='答对数量')
    wrong_count: Mapped[int] = mapped_column(default=0, comment='答错数量')
    accuracy_rate: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2), default=Decimal('0'), comment='正确率（百分比 0-100）'
    )

    # ============ 练习名称（冗余字段，优化查询性能） ============
    practice_name: Mapped[str | None] = mapped_column(
        sa.String(255),
        default=None,
        comment='练习名称（创建会话时从题库/章节获取，避免 JOIN 查询）',
    )

    # ============ 分数（考试模式） ============
    score: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(8, 2), default=None, comment='得分（考试模式）'
    )
    total_score: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(8, 2), default=None, comment='总分（考试模式）'
    )

    # ============ 时间统计 ============
    total_time: Mapped[int] = mapped_column(default=0, comment='总用时（秒）')
    start_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    submit_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='提交时间（None=未完成）')

    # ============ 状态 ============
    status: Mapped[str] = mapped_column(
        sa.String(32),
        default='in_progress',
        comment='状态：in_progress=进行中, completed=已完成, abandoned=已放弃',
    )

    # ============ 考试配置（可选） ============
    exam_config: Mapped[dict | None] = mapped_column(
        sa.JSON,
        default=None,
        comment="""考试配置 JSON:
        {
            "time_limit": 3600,      # 时间限制（秒）
            "show_answer": false,    # 是否显示答案
            "allow_review": true     # 是否允许回顾
        }
        """,
    )

    # ============ 关系 ============
    user: Mapped['UserAccount'] = relationship(init=False, back_populates='practice_sessions', lazy='noload')
    records: Mapped[list['PracticeRecord']] = relationship(
        init=False,
        back_populates='session',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class PracticeRecord(Base, UserMixin):
    """
    答题记录表

    设计思路：
    - 每答一题创建一条记录
    - 关联到 PracticeSession，方便批量查询
    - 冗余 bank_id、chapter_id，提高查询性能
    - 参考：Moodle question_attempts 表
    """

    __tablename__ = 'study_practice_record'
    __table_args__ = (
        sa.Index('idx_record_user_time', 'user_id', 'created_time'),
        sa.Index('idx_record_session', 'session_id'),
        sa.Index('idx_record_question_correct', 'question_id', 'is_correct'),
        sa.UniqueConstraint('session_id', 'question_id', name='uq_session_question'),
        {'comment': '答题记录表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    session_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_practice_session.id', ondelete='CASCADE'),
        comment='练习会话 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )

    # ============ 答题内容 ============
    user_answer: Mapped[str | list[str]] = mapped_column(
        sa.JSON,
        comment="""用户答案 JSON:
        - 单选/判断: "A"
        - 多选: ["A", "C"]
        - 填空: ["答案1", "答案2"]
        - 简答: "文本答案"
        """,
    )

    # ============ 冗余字段（提高查询性能） ============
    bank_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题库 ID（冗余）')

    # ============ 判题结果和用时（有默认值，必须在无默认值字段后面） ============
    is_correct: Mapped[bool | None] = mapped_column(default=None, comment='是否正确（答题时为空，提交时由后端统一判题）')
    answer_time: Mapped[int] = mapped_column(default=0, comment='本题用时（秒）')
    chapter_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='章节 ID（冗余）')

    # ============ 时间 ============
    created_time: Mapped[datetime] = mapped_column(
        TimeZone,
        init=False,
        default_factory=timezone.now,
        comment='答题时间',
    )

    # ============ 关系 ============
    user: Mapped['UserAccount'] = relationship(init=False, back_populates='practice_records', lazy='noload')
    session: Mapped['PracticeSession'] = relationship(init=False, back_populates='records', lazy='noload')
    question: Mapped['Question'] = relationship(init=False, lazy='noload')


class WrongQuestionBook(Base, UserMixin):
    """
    错题本表

    设计思路：
    - 答错自动加入，答对 3 次自动标记为已掌握
    - 支持置顶功能
    - 已掌握的题目不再显示在错题本列表
    """

    __tablename__ = 'study_wrong_question_book'
    __table_args__ = (
        sa.Index('idx_wrong_user_mastered', 'user_id', 'is_mastered', 'is_pinned'),
        sa.Index('idx_wrong_question', 'question_id'),
        sa.UniqueConstraint('user_id', 'question_id', name='uq_user_question'),
        {'comment': '错题本表'},
    )

    # ============ 基础字段 ============
    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )

    # ============ 错题统计 ============
    wrong_count: Mapped[int] = mapped_column(default=1, comment='错误次数')
    correct_count: Mapped[int] = mapped_column(default=0, comment='连续做对次数（连续 3 次移除）')

    # ============ 时间记录 ============
    first_wrong_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='首次错误时间')
    last_wrong_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最后一次错误时间')
    last_practice_time: Mapped[datetime | None] = mapped_column(
        TimeZone, default=None, comment='最后一次练习时间'
    )

    # ============ 状态 ============
    is_mastered: Mapped[bool] = mapped_column(default=False, comment='是否已掌握（连续答对 3 次）')
    mastered_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='掌握时间')

    # ============ 置顶功能 ============
    is_pinned: Mapped[bool] = mapped_column(default=False, comment='是否置顶')
    pinned_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='置顶时间')

    # ============ 关系 ============
    user: Mapped['UserAccount'] = relationship(init=False, back_populates='wrong_questions', lazy='noload')
    question: Mapped['Question'] = relationship(init=False, lazy='joined')
