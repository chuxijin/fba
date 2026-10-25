#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class GongkaoPracticeLog(Base):
    """公考练习记录表"""

    __tablename__ = 'gongkao_practice_log'
    __table_args__ = (
        sa.Index('idx_gk_practice_log_user_date', 'user_id', 'practiced_at'),
        sa.Index('idx_gk_practice_log_created_by', 'created_by'),
        sa.UniqueConstraint('user_id', 'source_platform', 'source_key', name='uq_gk_practice_log_source'),
        {'comment': '公考练习记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    material_title: Mapped[str] = mapped_column(sa.String(200), comment='练习材料标题')
    total_questions: Mapped[int] = mapped_column(comment='总题数')
    correct_count: Mapped[int] = mapped_column(comment='正确数')
    practiced_at: Mapped[date] = mapped_column(sa.Date, comment='练习日期')
    created_by: Mapped[int] = mapped_column(sa.BigInteger, comment='创建者')
    material_type: Mapped[str] = mapped_column(
        sa.String(20), default='exam', comment='材料类型（exam 模考, practice 练习, special 专项）'
    )
    accuracy_rate: Mapped[float | None] = mapped_column(sa.Numeric(5, 2), default=None, comment='正确率（%）')
    duration_seconds: Mapped[int | None] = mapped_column(default=None, comment='练习用时（秒）')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')
    subject_name: Mapped[str] = mapped_column(sa.String(100), default='行测', comment='科目名称')
    source_platform: Mapped[str] = mapped_column(sa.String(20), default='manual', comment='记录来源')
    source_key: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='平台报告唯一编号')
    source_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='原报告页面')
    source_updated_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='平台报告更新时间')
    time_source: Mapped[str] = mapped_column(sa.String(24), default='manual', comment='日期来源')
    unanswered_count: Mapped[int | None] = mapped_column(default=None, comment='未答题数，未知时为空')
    score: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='得分，与正确率独立')
    full_score: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='满分')


class GongkaoPracticeModule(Base):
    """公考练习模块表"""

    __tablename__ = 'gongkao_practice_module'
    __table_args__ = (
        sa.Index('idx_gk_practice_module_log_id', 'log_id'),
        sa.Index('idx_gk_practice_module_parent_id', 'parent_id'),
        sa.UniqueConstraint('log_id', 'seq_no', name='uq_gk_practice_module_log_seq'),
        {'comment': '公考练习模块表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    log_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('gongkao_practice_log.id', ondelete='CASCADE'),
        comment='练习记录 ID',
    )
    module_name: Mapped[str] = mapped_column(sa.String(100), comment='模块名称')
    total_questions: Mapped[int] = mapped_column(comment='该模块题数')
    correct_count: Mapped[int] = mapped_column(comment='该模块正确数')
    accuracy_rate: Mapped[float | None] = mapped_column(sa.Numeric(5, 2), default=None, comment='该模块正确率（%）')
    duration_seconds: Mapped[int | None] = mapped_column(default=None, comment='该模块用时（秒）')
    seq_no: Mapped[int] = mapped_column(default=0, comment='排序序号')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('gongkao_practice_module.id', ondelete='CASCADE'),
        default=None,
        comment='所属模块或子模块，可关联细分题型',
    )
    unanswered_count: Mapped[int | None] = mapped_column(default=None, comment='未答题数，未知时为空')
