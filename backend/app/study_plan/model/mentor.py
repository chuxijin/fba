#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    pass


class StudyMentorStudent(Base):
    """导师学员关联表"""

    __tablename__ = 'study_mentor_student'
    __table_args__ = (
        sa.UniqueConstraint('mentor_id', 'student_id', name='uq_study_mentor_student_pair'),
        sa.Index('idx_study_mentor_student_student', 'student_id', 'status'),
        sa.Index('idx_study_mentor_student_mentor', 'mentor_id', 'status'),
        sa.CheckConstraint('mentor_id <> student_id', name='ck_study_mentor_student_not_self'),
        sa.CheckConstraint("status IN ('active','paused')", name='ck_study_mentor_student_status'),
        {'comment': '导师学员关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    mentor_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='导师用户 ID',
    )
    student_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='学员用户 ID',
    )
    assigned_by: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='SET NULL'),
        default=None,
        comment='分配操作人（管理员 sys_user.id；管理员注销后为 NULL）',
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        default='active',
        comment='状态: active/paused',
    )
    note: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='分配备注')
    assigned_at: Mapped[datetime] = mapped_column(
        TimeZone,
        default_factory=timezone.now,
        comment='分配时间',
    )
