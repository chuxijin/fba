#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import DataClassBase, DateTimeMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class OCCompany(DataClassBase, DateTimeMixin):
    """公司信息表"""

    __tablename__ = 'oc_company'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True, comment='公司名称')
    short_name: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='公司简称')
    company_type: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='公司类型')
    industry: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='所属行业')
    company_size: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='公司规模')
    location: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='地点')
    extra_info: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, default_factory=dict, comment='公司其他信息')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')

    websites: Mapped[list['OCCompanyWebsite']] = relationship(
        init=False,
        back_populates='company',
        cascade='save-update, merge',
        lazy='noload',
    )
    announcements: Mapped[list['OCRecruitAnnouncement']] = relationship(
        init=False,
        back_populates='company',
        cascade='save-update, merge',
        lazy='noload',
    )


class OCCompanyWebsite(DataClassBase, DateTimeMixin):
    """公司网站表"""

    __tablename__ = 'oc_company_website'
    __table_args__ = (
        sa.UniqueConstraint('company_id', 'url', name='uq_oc_company_website'),
        {'comment': '公司网站表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    company_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('oc_company.id', ondelete='CASCADE'),
        index=True,
        comment='公司ID',
    )
    url: Mapped[str] = mapped_column(sa.Text, comment='网站链接')
    name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='网站名称（官网/投递入口等）')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')

    company: Mapped[OCCompany] = relationship(init=False, back_populates='websites', lazy='noload')


class OCRecruitAnnouncement(DataClassBase, DateTimeMixin):
    """招聘公告表"""

    __tablename__ = 'oc_recruit_announcement'
    __table_args__ = (
        sa.Index('ix_oc_announcement_company_type', 'company_id', 'recruitment_type'),
        {'comment': '招聘公告表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    company_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('oc_company.id', ondelete='CASCADE'),
        index=True,
        comment='公司ID',
    )
    title: Mapped[str] = mapped_column(sa.String(256), comment='公告标题')
    recruitment_type: Mapped[str] = mapped_column(sa.String(32), comment='招聘类型（校招/实习/社招）')
    recruit_target: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='招聘对象')
    positions: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='岗位名称')
    start_time: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='开始时间')
    end_time: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='截止时间')
    location: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='工作地点')
    exam_info: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='笔试情况')
    referral_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='内推码')
    apply_url: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='投递链接（本帖）')
    notice_url: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='公告链接（本帖）')
    source_update_date: Mapped[str | None] = mapped_column(
        sa.String(32), default=None, comment='源站更新日期（YYYY-MM-DD）'
    )
    source_key: Mapped[str | None] = mapped_column(
        sa.String(64), unique=True, index=True, default=None, comment='来源幂等键（如 campus:25567）'
    )
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')

    company: Mapped[OCCompany] = relationship(init=False, back_populates='announcements', lazy='noload')
