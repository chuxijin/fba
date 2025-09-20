#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class JobPosting(Base):
    """岗位表"""

    __tablename__ = 'job_posting'

    id: Mapped[id_key] = mapped_column(init=False)

    # 岗位基本信息（必填字段需在默认值字段前声明）
    job_title: Mapped[str] = mapped_column(String(200), index=True, comment='岗位标题')

    # 公司与展示信息（冗余字段，便于直接返回）
    company_name: Mapped[str | None] = mapped_column(String(200), default=None, comment='事业群/公司名')
    main_company_name: Mapped[str | None] = mapped_column(String(200), default=None, comment='主体公司名')
    company_alias: Mapped[str | None] = mapped_column(String(200), default=None, comment='公司别名')
    company_id: Mapped[str | None] = mapped_column(String(64), default=None, comment='外部公司 ID')
    org_type: Mapped[list[str] | None] = mapped_column(JSON, default=None, comment='组织类型数组')
    industry: Mapped[list[str] | None] = mapped_column(JSON, default=None, comment='行业数组')
    logo: Mapped[str | None] = mapped_column(String(500), default=None, comment='公司 LOGO URL')

    class_: Mapped[int | None] = mapped_column('class', default=None, index=True, comment='届别，如 26')
    num_hire: Mapped[int | None] = mapped_column(default=None, comment='招聘人数')
    salary: Mapped[str | None] = mapped_column(String(100), default=None, comment='薪资')

    # 文本/内容
    responsibility: Mapped[str | None] = mapped_column(Text, default=None)
    raw_position_require: Mapped[str | None] = mapped_column(Text, default=None)
    position_require_parsed: Mapped[bool] = mapped_column(default=False, comment='职位要求是否已解析')

    # 结构化职位要求（直接 JSON 内嵌）
    position_require_new: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, default=None, comment='结构化职位要求 JSON'
    )

    # 关联 ID/名称类（直接 JSON 内嵌）
    job_title_id: Mapped[list[int] | None] = mapped_column(JSON, default=None, comment='岗位名称 ID 列表')
    major_id: Mapped[list[int] | None] = mapped_column(JSON, default=None, comment='专业 ID 列表')
    address_id: Mapped[list[int] | None] = mapped_column(JSON, default=None, comment='地址 ID 列表')
    degree_str: Mapped[list[str] | None] = mapped_column(JSON, default=None, comment='学位展示标签')
    major_str: Mapped[list[str] | None] = mapped_column(JSON, default=None, comment='专业展示标签')
    address_str: Mapped[list[str] | None] = mapped_column(JSON, default=None, comment='地址展示标签')
    job_title_str: Mapped[list[str] | None] = mapped_column(JSON, default=None, comment='岗位展示标签')
    tags: Mapped[list[str] | None] = mapped_column(JSON, default=None, comment='自定义标签')

    # 时间与链接
    publish_date: Mapped[datetime | None] = mapped_column(TimeZone, default=None, index=True, comment='发布时间')
    expire_date: Mapped[datetime | None] = mapped_column(TimeZone, default=None, index=True, comment='截止时间')
    spider_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, index=True, comment='抓取时间')
    position_web_url: Mapped[str | None] = mapped_column(String(500), default=None, comment='职位链接 URL')
    page_list_config_id: Mapped[str | None] = mapped_column(String(64), default=None, comment='页面配置 ID')

    # 内推
    referral_code: Mapped[str | None] = mapped_column(String(50), default=None, comment='内推码')
    referral_show_index: Mapped[int | None] = mapped_column(default=None, comment='内推展示顺序')


