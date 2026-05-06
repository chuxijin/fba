#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from backend.app.job.model.internship_posting import InternshipPosting


class InternshipApplication(Base, UserMixin):
    """实习投递记录表"""
    __tablename__ = "internship_application"

    id: Mapped[id_key] = mapped_column(init=False)
    internship_posting_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("internship_posting.id"), comment="实习信息 ID"
    )
    application_status: Mapped[str] = mapped_column(String(50), comment="投递状态")

    internship_posting: Mapped[InternshipPosting] = relationship(init=False, back_populates="internship_applications")
