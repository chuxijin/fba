#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, HttpUrl

from backend.common.schema import SchemaBase


class JobSearchParam(SchemaBase):
    """岗位检索参数"""

    class_: int = Field(0, alias='class', description='届别，如 26；0 表示不限')
    page: int = Field(1, description='页码')
    page_size: int = Field(20, description='每页大小')
    user_id: str | None = Field(None, description='用户 ID')

    job_title_ids: list[int] = Field(default_factory=list, description='岗位名称 ID 列表')
    address_ids: list[int] = Field(default_factory=list, description='地址 ID 列表')
    degree_ids: list[int] = Field(default_factory=list, description='学位要求 ID 列表')
    english_ids: list[int] = Field(default_factory=list, description='英语要求 ID 列表')
    industry: list[str] = Field(default_factory=list, description='行业列表')
    major_ids: list[int] = Field(default_factory=list, description='专业 ID 列表')
    org_type: list[str] = Field(default_factory=list, description='组织类型列表')
    other_ids: list[int] = Field(default_factory=list, description='其他标签 ID 列表')
    personal_ids: list[int] = Field(default_factory=list, description='个性化标签 ID 列表')
    school_ids: list[int] = Field(default_factory=list, description='学校标签 ID 列表')
    tags: list[str] = Field(default_factory=list, description='标签列表')

    publish_date_start: str = Field('', description='发布时间开始')
    publish_date_end: str = Field('', description='发布时间结束')
    expire_date_start: str = Field('', description='截止时间开始')
    expire_date_end: str = Field('', description='截止时间结束')
    cache_page: bool = Field(True, description='是否缓存分页')

    model_config = ConfigDict(populate_by_name=True)


class CreateJobPostingParam(SchemaBase):
    """创建岗位参数"""

    company_name: str | None = Field(None, description='事业群/公司名')
    main_company_name: str | None = Field(None, description='主体公司名')
    company_alias: str | None = Field(None, description='公司别名')
    company_id: str | None = Field(None, description='外部公司 ID')
    org_type: list[str] = Field(default_factory=list, description='组织类型')
    industry: list[str] = Field(default_factory=list, description='行业')
    logo: str | None = Field(None, description='公司 LOGO')

    job_title: str = Field(description='岗位标题')
    class_: int | None = Field(None, alias='class', description='届别，如 26')
    num_hire: int | None = Field(None, description='招聘人数')
    salary: str | None = Field(None, description='薪资')

    responsibility: str | None = Field(None, description='岗位职责')
    raw_position_require: str | None = Field(None, description='职位要求原文')
    position_require_parsed: bool = Field(False, description='是否已解析')
    position_require_new: dict[str, Any] | None = Field(None, description='结构化职位要求 JSON')

    job_title_id: list[int] = Field(default_factory=list, description='岗位名称 ID 列表')
    major_id: list[int] = Field(default_factory=list, description='专业 ID 列表')
    address_id: list[int] = Field(default_factory=list, description='地址 ID 列表')
    degree_str: list[str] = Field(default_factory=list, description='学位展示')
    major_str: list[str] = Field(default_factory=list, description='专业展示')
    address_str: list[str] = Field(default_factory=list, description='地址展示')
    job_title_str: list[str] = Field(default_factory=list, description='岗位展示')
    tags: list[str] = Field(default_factory=list, description='标签')

    publish_date: datetime | None = Field(None, description='发布时间')
    expire_date: datetime | None = Field(None, description='截止时间')
    spider_time: datetime | None = Field(None, description='抓取时间')
    position_web_url: HttpUrl | None = Field(None, description='岗位链接')
    page_list_config_id: str | None = Field(None, description='页面配置 ID')

    referral_code: str | None = Field(None, description='内推码')
    referral_show_index: int | None = Field(None, description='内推展示顺序')

    model_config = ConfigDict(populate_by_name=True)


class UpdateJobPostingParam(SchemaBase):
    """更新岗位参数"""

    company_name: str | None = Field(None, description='事业群/公司名')
    main_company_name: str | None = Field(None, description='主体公司名')
    company_alias: str | None = Field(None, description='公司别名')
    company_id: str | None = Field(None, description='外部公司 ID')
    org_type: list[str] | None = Field(None, description='组织类型')
    industry: list[str] | None = Field(None, description='行业')
    logo: str | None = Field(None, description='公司 LOGO')

    job_title: str | None = Field(None, description='岗位标题')
    class_: int | None = Field(None, alias='class', description='届别，如 26')
    num_hire: int | None = Field(None, description='招聘人数')
    salary: str | None = Field(None, description='薪资')

    responsibility: str | None = Field(None, description='岗位职责')
    raw_position_require: str | None = Field(None, description='职位要求原文')
    position_require_parsed: bool | None = Field(None, description='是否已解析')
    position_require_new: dict[str, Any] | None = Field(None, description='结构化职位要求 JSON')

    job_title_id: list[int] | None = Field(None, description='岗位名称 ID 列表')
    major_id: list[int] | None = Field(None, description='专业 ID 列表')
    address_id: list[int] | None = Field(None, description='地址 ID 列表')
    degree_str: list[str] | None = Field(None, description='学位展示')
    major_str: list[str] | None = Field(None, description='专业展示')
    address_str: list[str] | None = Field(None, description='地址展示')
    job_title_str: list[str] | None = Field(None, description='岗位展示')
    tags: list[str] | None = Field(None, description='标签')

    publish_date: datetime | None = Field(None, description='发布时间')
    expire_date: datetime | None = Field(None, description='截止时间')
    spider_time: datetime | None = Field(None, description='抓取时间')
    position_web_url: HttpUrl | None = Field(None, description='岗位链接')
    page_list_config_id: str | None = Field(None, description='页面配置 ID')

    referral_code: str | None = Field(None, description='内推码')
    referral_show_index: int | None = Field(None, description='内推展示顺序')

    model_config = ConfigDict(populate_by_name=True)


class DeleteJobPostingParam(SchemaBase):
    """批量删除岗位参数"""

    ids: list[int] = Field(description='岗位 ID 列表')


class PositionRequireNewOut(SchemaBase):
    """结构化职位要求"""

    degree_associate: int = Field(description='专科')
    degree_bachelor: int = Field(description='本科')
    degree_master: int = Field(description='硕士')
    degree_doctor: int = Field(description='博士')
    degree_unlimited: int = Field(description='不限')

    e_4: int = Field(description='英语四级')
    e_6: int = Field(description='英语六级')
    e_fluent: int = Field(description='英语流利')
    e_IELTS: int = Field(description='雅思')
    e_TOEFL: int = Field(description='托福')
    e_GRE: int = Field(description='GRE')

    s_211: int = Field(description='211 院校')
    s_double_first_class: int = Field(description='双一流')

    party_number: int = Field(description='党员')
    oversea: int = Field(description='海外经历')
    student_leader: int = Field(description='学生干部')

    business_trip: int = Field(description='出差')
    overtime: int = Field(description='加班')

    address: list[str] = Field(default_factory=list, description='工作城市（名称）')
    major: list[str] = Field(default_factory=list, description='专业（名称）')
    class_: list[int] = Field(alias='class', default_factory=list, description='届别列表')
    major_id: list[int] = Field(default_factory=list, description='专业 ID 列表')
    address_id: list[int] = Field(default_factory=list, description='地址 ID 列表')

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class JobPostingDetail(SchemaBase):
    """岗位详情"""

    model_config = ConfigDict(from_attributes=True)

    company_name: str | None = Field(None, description='事业群/公司名')
    position_require: dict[str, Any] | None = Field(None, description='原始职位要求')
    expire_date: datetime | None = Field(None, description='截止时间')
    job_title: str = Field(description='岗位标题')
    publish_date: datetime | None = Field(None, description='发布时间')
    num_hire: int | None = Field(None, description='招聘人数')
    class_: int | None = Field(None, alias='class', description='届别')
    salary: str | None = Field(None, description='薪资')
    raw_position_require: str | None = Field(None, description='职位要求原文')
    responsibility: str | None = Field(None, description='岗位职责')
    address: list[str] = Field(default_factory=list, description='工作城市名称列表')
    spider_time: datetime | None = Field(None, description='抓取时间')
    position_web_url: HttpUrl | None = Field(None, description='岗位链接')
    page_list_config_id: str | None = Field(None, description='页面配置 ID')
    position_require_parsed: bool = Field(description='是否已解析')
    job_title_id: list[int] = Field(default_factory=list, description='岗位名称 ID 列表')
    position_require_new: PositionRequireNewOut | None = Field(None, description='结构化职位要求')

    referral_code: str | None = Field(None, description='内推码')
    referral_show_index: int | None = Field(None, description='内推展示顺序')

    main_company_name: str | None = Field(None, description='主体公司名称')
    company_alias: str | None = Field(None, description='公司别名')
    org_type: list[str] = Field(default_factory=list, description='组织类型')
    industry: list[str] = Field(default_factory=list, description='行业')
    tags: list[str] = Field(default_factory=list, description='标签')
    company_id: str | None = Field(None, description='外部公司 ID')
    logo: str | None = Field(None, description='公司 LOGO')

    degree_str: list[str] = Field(default_factory=list, description='学位展示')
    major_str: list[str] = Field(default_factory=list, description='专业展示')
    address_str: list[str] = Field(default_factory=list, description='地址展示')
    job_title_str: list[str] = Field(default_factory=list, description='岗位展示')


