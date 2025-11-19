#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BiliDuplicateCheckSchemaBase(SchemaBase):
    """B 站用户操作记录基础模型"""

    mid: str = Field(description='被操作的 B 站用户 MID')
    operation_type: str = Field(description='操作类型(at/comment/message)')
    is_active: bool = Field(False, description='是否主动操作(0 被动 1 主动)')
    send_content: str | None = Field(None, description='发送内容')
    send_result: str | None = Field(None, description='发送结果(JSON 格式)')
    work_id: int | None = Field(None, description='作品关联 ID')
    execution_log_id: int | None = Field(None, description='任务执行记录 ID')


class CreateBiliDuplicateCheckParam(BiliDuplicateCheckSchemaBase):
    """创建 B 站用户操作记录参数"""


class UpdateBiliDuplicateCheckParam(SchemaBase):
    """更新 B 站用户操作记录参数"""

    mid: str | None = Field(None, description='被操作的 B 站用户 MID')
    operation_type: str | None = Field(None, description='操作类型')
    is_active: bool | None = Field(None, description='是否主动操作')
    send_content: str | None = Field(None, description='发送内容')
    send_result: str | None = Field(None, description='发送结果')
    work_id: int | None = Field(None, description='作品关联 ID')
    execution_log_id: int | None = Field(None, description='任务执行记录 ID')


class GetBiliDuplicateCheckDetail(BiliDuplicateCheckSchemaBase):
    """B 站用户操作记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
