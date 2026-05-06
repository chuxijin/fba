#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.job.schema.job_application import JobApplicationSchema
from backend.common.pagination import _CustomPageParams
from backend.common.schema import SchemaBase


class CreateJobPosting(SchemaBase):
    """创建招聘信息"""

    company_name: str = Field(description="公司名称")
    company_type: str | None = Field(None, description="公司类型")
    industry: str | None = Field(None, description="所属行业")
    recruitment_type: str | None = Field(None, description="招聘类型")
    work_location: str | None = Field(None, description="工作地点")
    recruitment_object: str | None = Field(None, description="招聘对象")
    position: str = Field(description="岗位")
    delivery_start: datetime | None = Field(None, description="投递开始日期")
    delivery_end: datetime | None = Field(None, description="投递截止日期")
    delivery_link: str | None = Field(None, description="投递链接")
    recruitment_announcement: str | None = Field(None, description="招聘公告")
    referral_code: str | None = Field(None, description="内推码")
    remark: str | None = Field(None, description="备注")
    salary_range: str | None = Field(None, description="薪资范围")
    is_exempt_from_written_test: bool | None = Field(None, description="是否免笔试")
    logo_url: str | None = Field(None, description="公司Logo URL")


class UpdateJobPosting(CreateJobPosting):
    """更新招聘信息"""

    pass


class DeleteJobPostingParam(SchemaBase):
    """删除招聘信息参数"""

    pks: list[int] = Field(description="招聘信息 ID 列表")


class GetJobPostingListParams(_CustomPageParams):
    """获取招聘信息列表参数"""

    company_name: str | None = Field(None, description="公司名称")
    position: str | None = Field(None, description="岗位")
    industry: str | None = Field(None, description="所属行业")
    recruitment_type: str | None = Field(None, description="招聘类型")


class GetJobPostingDetail(SchemaBase):
    """招聘信息详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="招聘信息 ID")
    company_name: str = Field(description="公司名称")
    company_type: str | None = Field(None, description="公司类型")
    industry: str | None = Field(None, description="所属行业")
    recruitment_type: str | None = Field(None, description="招聘类型")
    work_location: str | None = Field(None, description="工作地点")
    recruitment_object: str | None = Field(None, description="招聘对象")
    position: str = Field(description="岗位")
    delivery_start: datetime | None = Field(None, description="投递开始日期")
    delivery_end: datetime | None = Field(None, description="投递截止日期")
    delivery_link: str | None = Field(None, description="投递链接")
    recruitment_announcement: str | None = Field(None, description="招聘公告")
    referral_code: str | None = Field(None, description="内推码")
    remark: str | None = Field(None, description="备注")
    salary_range: str | None = Field(None, description="薪资范围")
    is_exempt_from_written_test: bool | None = Field(None, description="是否免笔试")
    logo_url: str | None = Field(None, description="公司Logo URL")


class GetJobPostingWithApplications(GetJobPostingDetail):
    """招聘信息详情（包含投递记录）"""

    job_applications: list[JobApplicationSchema] = Field([], description="投递记录列表")


class JobPostingSchema(GetJobPostingDetail):
    """招聘信息详情"""

    pass
