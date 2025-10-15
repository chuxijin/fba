#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from backend.app.job.model.internship_application import InternshipApplication


class InternshipPosting(Base, UserMixin):
    """实习信息表"""
    __tablename__ = "internship_posting"

    id: Mapped[id_key] = mapped_column(init=False)
    company_name: Mapped[str] = mapped_column(String(500), comment="公司名称")
    position: Mapped[str] = mapped_column(Text, comment="岗位")
    company_type: Mapped[str | None] = mapped_column(String(500), comment="公司类型")
    industry: Mapped[str | None] = mapped_column(String(500), comment="所属行业")
    recruitment_type: Mapped[str | None] = mapped_column(String(500), comment="招聘类型")
    work_location: Mapped[str | None] = mapped_column(String(1000), comment="工作地点")
    recruitment_object: Mapped[str | None] = mapped_column(String(500), comment="招聘对象")
    delivery_start: Mapped[datetime | None] = mapped_column(Date, comment="投递开始日期")
    delivery_end: Mapped[datetime | None] = mapped_column(Date, comment="投递截止日期")
    delivery_link: Mapped[str | None] = mapped_column(Text, comment="投递链接")
    recruitment_announcement: Mapped[str | None] = mapped_column(Text, comment="招聘公告")
    referral_code: Mapped[str | None] = mapped_column(String(255), comment="内推码")
    remark: Mapped[str | None] = mapped_column(Text, comment="备注")
    salary_range: Mapped[str | None] = mapped_column(String(255), comment="薪资范围")
    logo_url: Mapped[str | None] = mapped_column(String(500), comment="公司Logo URL")
    is_exempt_from_written_test: Mapped[bool] = mapped_column(default=False, comment="是否免笔试")

    internship_applications: Mapped[list[InternshipApplication]] = relationship(
        init=False, back_populates="internship_posting"
    )

