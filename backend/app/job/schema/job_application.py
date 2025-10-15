#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import ConfigDict, Field

from backend.common.enums import ApplicationStatus
from backend.common.pagination import _CustomPageParams
from backend.common.schema import SchemaBase


class CreateJobApplication(SchemaBase):
    """创建投递记录"""

    job_posting_id: int = Field(description="招聘信息 ID")
    application_status: ApplicationStatus = Field(description="投递状态")


class UpdateJobApplication(SchemaBase):
    """更新投递记录"""

    application_status: ApplicationStatus = Field(description="投递状态")


class DeleteJobApplicationParam(SchemaBase):
    """删除投递记录参数"""

    pks: list[int] = Field(description="投递记录 ID 列表")


class GetJobApplicationListParams(_CustomPageParams):
    """获取投递记录列表参数"""

    job_posting_id: int | None = Field(None, description="招聘信息 ID")
    application_status: ApplicationStatus | None = Field(None, description="投递状态")


class GetJobApplicationDetail(SchemaBase):
    """投递记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="投递记录 ID")
    job_posting_id: int = Field(description="招聘信息 ID")
    application_status: ApplicationStatus = Field(description="投递状态")


class JobApplicationSchema(GetJobApplicationDetail):
    """投递记录详情"""

    pass
