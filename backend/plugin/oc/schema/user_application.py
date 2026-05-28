from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class UserApplicationSchemaBase(SchemaBase):
    """用户投递记录基础模型"""

    user_id: int = Field(description='用户 ID')
    job_id: int = Field(description='岗位 ID')
    job_type: str = Field(description='岗位类型')
    application_status: str = Field(default='未投递', description='投递状态')
    applied_at: datetime | None = Field(None, description='投递时间')
    remark: str | None = Field(None, description='备注')


class CreateUserApplicationParam(UserApplicationSchemaBase):
    """创建用户投递记录参数"""


class UpdateUserApplicationParam(SchemaBase):
    """更新用户投递记录参数"""

    application_status: str = Field(description='投递状态')
    applied_at: datetime | None = Field(None, description='投递时间')
    remark: str | None = Field(None, description='备注')


class GetUserApplicationDetail(UserApplicationSchemaBase):
    """用户投递记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
