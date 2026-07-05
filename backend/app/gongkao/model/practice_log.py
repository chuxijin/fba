#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class GongkaoPracticeLog(Base):
    """公考练习记录表"""

    __tablename__ = 'gongkao_practice_log'
    __table_args__ = (
        sa.Index('idx_gk_practice_log_user_date', 'user_id', 'practiced_at'),
        sa.Index('idx_gk_practice_log_created_by', 'created_by'),
        {'comment': '公考练习记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    material_title: Mapped[str] = mapped_column(sa.String(200), comment='练习材料标题')
    total_questions: Mapped[int] = mapped_column(comment='总题数')
    correct_count: Mapped[int] = mapped_column(comment='正确数')
    practiced_at: Mapped[date] = mapped_column(sa.Date, comment='练习日期')
    created_by: Mapped[int] = mapped_column(sa.BigInteger, comment='创建者')
    material_type: Mapped[str] = mapped_column(sa.String(20), default='exam', comment='材料类型（exam 模考, practice 练习, special 专项）')
    accuracy_rate: Mapped[float | None] = mapped_column(sa.Numeric(5, 2), default=None, comment='正确率（%）')
    duration_seconds: Mapped[int | None] = mapped_column(default=None, comment='练习用时（秒）')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')


class GongkaoPracticeModule(Base):
    """公考练习模块表"""

    __tablename__ = 'gongkao_practice_module'
    __table_args__ = (
        sa.Index('idx_gk_practice_module_log_id', 'log_id'),
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
