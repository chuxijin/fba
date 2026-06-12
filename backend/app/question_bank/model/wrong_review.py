#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    from .practice import WrongQuestionBook
    from .question import Question


class WrongReasonTag(Base):
    """错因标签表"""

    __tablename__ = 'study_wrong_reason_tag'
    __table_args__ = (
        sa.Index('uq_reason_tag_system_name', 'name', unique=True, postgresql_where=sa.text('user_id IS NULL AND deleted = 0')),
        sa.Index('uq_reason_tag_user_name', 'user_id', 'name', unique=True, postgresql_where=sa.text('user_id IS NOT NULL AND deleted = 0')),
        {'comment': '错因标签表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='标签名称')
    user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        default=None,
        comment='用户 ID（NULL 表示系统预设）',
    )
    color: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='标签颜色')
    is_system: Mapped[bool] = mapped_column(default=False, comment='是否系统预设')
    display_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序权重')


class WrongQuestionCustom(Base):
    """自定义导入错题表"""

    __tablename__ = 'study_wrong_question_custom'
    __table_args__ = (
        sa.Index('idx_wrong_custom_user', 'user_id', 'deleted'),
        sa.Index('idx_wrong_custom_category', 'category_id', postgresql_where=sa.text('category_id IS NOT NULL')),
        sa.Index('idx_wrong_custom_question', 'question_id', postgresql_where=sa.text('question_id IS NOT NULL')),
        {'comment': '自定义导入错题表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='SET NULL'),
        default=None,
        comment='关联题库题目',
    )
    category_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='关联题库分类（sys_category）')
    stem: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='题干文本（截图题可为空）')
    images: Mapped[list | None] = mapped_column(CompatibleJSONB, default=None, comment='截图 URL 数组')
    options: Mapped[dict | list | None] = mapped_column(CompatibleJSONB, default=None, comment='选项')
    answer: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='正确答案')
    explanation: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='解析')
    source: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='来源')
    reasons: Mapped[list | None] = mapped_column(CompatibleJSONB, default=None, comment='错因标签 ID 数组')
    summary: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='一句话复盘')
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='做题用时（秒）')

    # ============ 关系 ============
    question: Mapped[Question | None] = relationship(init=False, lazy='noload')


class WrongQuestionReview(Base):
    """错题复盘记录表"""

    __tablename__ = 'study_wrong_question_review'
    __table_args__ = (
        sa.CheckConstraint("review_type IN ('auto', 'custom')", name='ck_review_type'),
        sa.CheckConstraint(
            "(review_type = 'auto' AND wrong_book_id IS NOT NULL AND custom_question_id IS NULL) "
            "OR (review_type = 'custom' AND custom_question_id IS NOT NULL AND wrong_book_id IS NULL)",
            name='ck_review_source',
        ),
        sa.CheckConstraint('duration_seconds >= 0', name='ck_review_duration'),
        sa.Index('idx_review_user_time', 'user_id', 'reviewed_time', postgresql_where=sa.text('deleted = 0')),
        sa.Index('idx_review_wrong_book', 'wrong_book_id', postgresql_where=sa.text('wrong_book_id IS NOT NULL')),
        sa.Index('idx_review_custom', 'custom_question_id', postgresql_where=sa.text('custom_question_id IS NOT NULL')),
        {'comment': '错题复盘记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    review_type: Mapped[str] = mapped_column(sa.String(16), comment='复盘类型: auto/custom')
    wrong_book_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_wrong_question_book.id', ondelete='CASCADE'),
        default=None,
        comment='关联自动收录错题',
    )
    custom_question_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_wrong_question_custom.id', ondelete='CASCADE'),
        default=None,
        comment='关联自定义错题',
    )
    duration_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='复盘用时（秒）')
    reasons: Mapped[list | None] = mapped_column(CompatibleJSONB, default=None, comment='错因标签 ID 数组')
    summary: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='一句话复盘')
    reviewed_time: Mapped[datetime] = mapped_column(
        TimeZone, default_factory=timezone.now, comment='复盘时间',
    )

    # ============ 关系 ============
    wrong_book: Mapped[WrongQuestionBook | None] = relationship(init=False, lazy='noload')
    custom_question: Mapped[WrongQuestionCustom | None] = relationship(init=False, lazy='noload')
