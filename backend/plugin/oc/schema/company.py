from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CompanyWebsiteParam(SchemaBase):
    """公司网站创建/更新参数"""

    url: str = Field(description='网站链接')
    name: str | None = Field(None, description='网站名称（官网/投递入口等）')
    remark: str | None = Field(None, description='备注')


class OCCompanySchemaBase(SchemaBase):
    """公司基础模型"""

    name: str = Field(description='公司名称')
    short_name: str | None = Field(None, description='公司简称')
    company_type: str | None = Field(None, description='公司类型')
    industry: str | None = Field(None, description='所属行业')
    company_size: str | None = Field(None, description='公司规模')
    location: str | None = Field(None, description='地点')
    extra_info: dict[str, Any] = Field(default_factory=dict, description='公司其他信息')
    remark: str | None = Field(None, description='备注')


class CreateCompanyParam(OCCompanySchemaBase):
    """创建公司参数"""

    websites: list[CompanyWebsiteParam] = Field(default_factory=list, description='网站列表')


class UpdateCompanyParam(SchemaBase):
    """更新公司参数"""

    name: str | None = Field(None, description='公司名称')
    short_name: str | None = Field(None, description='公司简称')
    company_type: str | None = Field(None, description='公司类型')
    industry: str | None = Field(None, description='所属行业')
    company_size: str | None = Field(None, description='公司规模')
    location: str | None = Field(None, description='地点')
    extra_info: dict[str, Any] | None = Field(None, description='公司其他信息')
    remark: str | None = Field(None, description='备注')
    websites: list[CompanyWebsiteParam] | None = Field(None, description='网站列表（传入时全量替换）')


class GetCompanyWebsiteDetail(SchemaBase):
    """公司网站详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='网站 ID')
    url: str = Field(description='网站链接')
    name: str | None = Field(None, description='网站名称')
    remark: str | None = Field(None, description='备注')
    created_time: datetime = Field(description='创建时间')


class GetCompanyDetail(OCCompanySchemaBase):
    """公司详情（含网站列表）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='公司 ID')
    websites: list[GetCompanyWebsiteDetail] = Field(default_factory=list, description='网站列表')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
