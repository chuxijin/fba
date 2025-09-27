from __future__ import annotations

from typing import Optional
from datetime import datetime

from sqlalchemy import String, Text, Boolean, Date
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, snowflake_id_key


class JobPosting(Base, UserMixin):
    """
    招聘信息表
    """
    __tablename__ = "job_posting"

    id: Mapped[snowflake_id_key] = mapped_column(init=False)
    company_name: Mapped[str] = mapped_column(String(255), comment="公司名称")
    company_type: Mapped[Optional[str]] = mapped_column(String(255), comment="公司类型")
    industry: Mapped[Optional[str]] = mapped_column(String(255), comment="所属行业")
    recruitment_type: Mapped[Optional[str]] = mapped_column(String(255), comment="招聘类型")
    work_location: Mapped[Optional[str]] = mapped_column(String(255), comment="工作地点")
    recruitment_object: Mapped[Optional[str]] = mapped_column(String(255), comment="招聘对象")
    position: Mapped[str] = mapped_column(String(255), comment="岗位")
    delivery_start: Mapped[Optional[datetime]] = mapped_column(Date, comment="投递开始日期")
    delivery_end: Mapped[Optional[datetime]] = mapped_column(Date, comment="投递截止日期")
    delivery_link: Mapped[Optional[str]] = mapped_column(Text, comment="投递链接")
    recruitment_announcement: Mapped[Optional[str]] = mapped_column(Text, comment="招聘公告")
    referral_code: Mapped[Optional[str]] = mapped_column(String(255), comment="内推码")
    remark: Mapped[Optional[str]] = mapped_column(Text, comment="备注")
    salary_range: Mapped[Optional[str]] = mapped_column(String(255), comment="薪资范围")
    is_exempt_from_written_test: Mapped[Optional[Boolean]] = mapped_column(Boolean, comment="是否免笔试")
    logo_url: Mapped[Optional[str]] = mapped_column(Text, comment="公司Logo URL")
