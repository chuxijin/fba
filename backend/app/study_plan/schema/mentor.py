#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

MentorStatus = Literal['active', 'paused']


class AssignMentorStudentParam(SchemaBase):
    """分配导师学员参数"""

    mentor_id: int = Field(description='导师用户 ID')
    student_id: int = Field(description='学员用户 ID')
    note: str | None = Field(default=None, max_length=255, description='分配备注')


class UpdateMentorStudentStatusParam(SchemaBase):
    """更新导师学员关系状态参数"""

    status: MentorStatus = Field(description='状态')


class GetMentorStudentDetail(SchemaBase):
    """导师学员关系详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='关系 ID')
    mentor_id: int = Field(description='导师用户 ID')
    student_id: int = Field(description='学员用户 ID')
    assigned_by: int | None = Field(default=None, description='分配操作人')
    status: MentorStatus = Field(description='状态')
    note: str | None = Field(default=None, description='分配备注')
    assigned_at: datetime = Field(description='分配时间')
