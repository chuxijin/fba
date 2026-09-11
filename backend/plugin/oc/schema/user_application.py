from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase
from backend.plugin.oc.schema.recruit_announcement import GetCompanyBriefDetail


class UserApplicationSchemaBase(SchemaBase):
    """用户投递记录基础模型"""

    user_id: int = Field(description='用户 ID')
    announcement_id: int = Field(description='公告 ID')
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


class GetApplicationAnnouncementDetail(SchemaBase):
    """投递记录内嵌公告简要信息"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='公告 ID')
    title: str = Field(description='公告标题')
    recruitment_type: str = Field(description='招聘类型')
    end_time: str | None = Field(None, description='截止时间')
    location: str | None = Field(None, description='工作地点')
    company: GetCompanyBriefDetail = Field(description='公司信息')


class GetUserApplicationDetail(UserApplicationSchemaBase):
    """用户投递记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetUserApplicationWithRelationDetail(GetUserApplicationDetail):
    """用户投递记录详情（含公告与公司信息）"""

    announcement: GetApplicationAnnouncementDetail = Field(description='公告信息')
