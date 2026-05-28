"""内推码 Schema"""

from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ReferralCodeSchemaBase(SchemaBase):
    """内推码基础模型"""

    company_name: str = Field(description='企业名称')
    referral_code: str = Field(description='内推码')
    remark: str | None = Field(None, description='备注')


class CreateReferralCodeParam(ReferralCodeSchemaBase):
    """创建内推码参数"""

    pass


class UpdateReferralCodeParam(SchemaBase):
    """更新内推码参数"""

    company_name: str | None = Field(None, description='企业名称')
    referral_code: str | None = Field(None, description='内推码')
    remark: str | None = Field(None, description='备注')


class GetReferralCodeDetail(ReferralCodeSchemaBase):
    """获取内推码详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    created_by: int = Field(description='创建者ID')
    updated_by: int | None = Field(None, description='更新者ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
