#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from backend.app.job.model.job_posting import JobPosting


class JobApplication(Base, UserMixin):
    """投递记录表"""
    __tablename__ = "job_application"

    id: Mapped[id_key] = mapped_column(init=False)
    job_posting_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("job_posting.id"), comment="招聘信息 ID")
    application_status: Mapped[str] = mapped_column(String(50), comment="投递状态")

    job_posting: Mapped[JobPosting] = relationship(init=False, back_populates="job_applications")
