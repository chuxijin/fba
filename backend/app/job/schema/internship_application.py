#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import ConfigDict, Field

from backend.common.enums import ApplicationStatus
from backend.common.pagination import _CustomPageParams
from backend.common.schema import SchemaBase


class CreateInternshipApplication(SchemaBase):
    """创建实习投递记录"""
    internship_posting_id: int = Field(..., description="实习信息ID")
    application_status: ApplicationStatus = Field(..., description="投递状态")


class UpdateInternshipApplication(SchemaBase):
    """更新实习投递记录"""
    application_status: ApplicationStatus = Field(..., description="投递状态")


class DeleteInternshipApplicationParam(SchemaBase):
    """删除实习投递记录参数"""
    pks: list[int] = Field(..., description="实习投递记录ID列表")

class GetInternshipApplicationListParams(_CustomPageParams):
    """获取实习投递记录列表参数"""
    internship_posting_id: int | None = Field(None, description="实习信息ID")
    application_status: ApplicationStatus | None = Field(None, description="投递状态")

class GetInternshipApplicationDetail(SchemaBase):
    """获取实习投递记录详情"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="ID")
    internship_posting_id: int = Field(..., description="实习信息ID")
    application_status: ApplicationStatus = Field(..., description="投递状态")


class InternshipApplicationSchema(GetInternshipApplicationDetail):
    """实习投递记录详情"""
    pass

