#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, model_validator
from typing_extensions import Self

from backend.app.job.schema.internship_application import InternshipApplicationSchema
from backend.common.pagination import _CustomPageParams
from backend.common.schema import SchemaBase


class CreateInternshipPosting(SchemaBase):
    """实习信息基础"""
    company_name: str = Field(..., description="公司名称")
    company_type: str | None = Field(None, description="公司类型")
    industry: str | None = Field(None, description="所属行业")
    recruitment_type: str | None = Field(None, description="招聘类型")
    work_location: str | None = Field(None, description="工作地点")
    recruitment_object: str | None = Field(None, description="招聘对象")
    position: str = Field(..., description="岗位")
    delivery_start: datetime | None = Field(None, description="投递开始日期")
    delivery_end: datetime | None = Field(None, description="投递截止日期")
    delivery_link: str | None = Field(None, description="投递链接")
    recruitment_announcement: str | None = Field(None, description="招聘公告")
    referral_code: str | None = Field(None, description="内推码")
    remark: str | None = Field(None, description="备注")
    salary_range: str | None = Field(None, description="薪资范围")
    is_exempt_from_written_test: bool = Field(False, description="是否免笔试")
    logo_url: str | None = Field(None, description="公司Logo URL")


class UpdateInternshipPosting(CreateInternshipPosting):
    """更新实习信息"""

    pass


class DeleteInternshipPostingParam(SchemaBase):
    """删除实习信息参数"""

    pks: list[int] = Field(description="实习信息 ID 列表")


class GetInternshipPostingListParams(_CustomPageParams):
    """获取实习信息列表参数"""

    company_name: str | None = Field(None, description="公司名称")
    position: str | None = Field(None, description="岗位")
    industry: str | None = Field(None, description="所属行业")
    recruitment_type: str | None = Field(None, description="招聘类型")


class GetInternshipPostingDetail(SchemaBase):
    """获取实习信息详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="实习信息 ID")
    company_name: str = Field(..., description="公司名称")
    company_type: str | None = Field(None, description="公司类型")
    industry: str | None = Field(None, description="所属行业")
    recruitment_type: str | None = Field(None, description="招聘类型")
    work_location: str | None = Field(None, description="工作地点")
    recruitment_object: str | None = Field(None, description="招聘对象")
    position: str = Field(..., description="岗位")
    delivery_start: datetime | None = Field(None, description="投递开始日期")
    delivery_end: datetime | None = Field(None, description="投递截止日期")
    delivery_link: str | None = Field(None, description="投递链接")
    recruitment_announcement: str | None = Field(None, description="招聘公告")
    referral_code: str | None = Field(None, description="内推码")
    remark: str | None = Field(None, description="备注")
    salary_range: str | None = Field(None, description="薪资范围")
    is_exempt_from_written_test: bool = Field(False, description="是否免笔试")
    logo_url: str | None = Field(None, description="公司Logo URL")


class GetInternshipPostingWithApplications(GetInternshipPostingDetail):
    """获取带投递记录的实习信息"""
    internship_applications: list[InternshipApplicationSchema] = Field([], description="投递记录列表")


class InternshipPostingSchema(GetInternshipPostingDetail):
    """实习信息详情"""
    pass
