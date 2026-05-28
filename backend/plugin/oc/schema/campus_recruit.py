from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CampusRecruitSchemaBase(SchemaBase):
    """校招岗位基础模型"""

    company_name: str = Field(description='公司名称')
    company_type: str = Field(description='公司类型')
    industry: str = Field(description='所属行业')
    recruitment_type: str = Field(description='招聘类型')
    recruit_target: str = Field(description='招聘对象')
    location: str = Field(description='工作地点')
    positions: str = Field(description='岗位名称')
    application_status: str = Field(default='未投递', description='投递进度')
    update_time: date = Field(description='更新时间')
    company_size: str | None = Field(None, description='公司规模')
    deadline: str | None = Field(None, description='截止时间')
    apply_link: str | None = Field(None, description='投递链接')
    notice_link: str | None = Field(None, description='招聘公告链接')
    referral_code: str | None = Field(None, description='内推码')
    exam_info: str | None = Field(None, description='笔试信息')
    remark: str | None = Field(None, description='备注')


class CreateCampusRecruitParam(CampusRecruitSchemaBase):
    """创建校招岗位参数"""

    id: int = Field(description='岗位ID（使用源网站ID）')


class UpdateCampusRecruitParam(SchemaBase):
    """更新校招岗位参数"""

    company_name: str | None = Field(None, description='公司名称')
    company_type: str | None = Field(None, description='公司类型')
    company_size: str | None = Field(None, description='公司规模')
    industry: str | None = Field(None, description='所属行业')
    recruitment_type: str | None = Field(None, description='招聘类型')
    recruit_target: str | None = Field(None, description='招聘对象')
    location: str | None = Field(None, description='工作地点')
    positions: str | None = Field(None, description='岗位名称')
    application_status: str | None = Field(None, description='投递进度')
    update_time: date | None = Field(None, description='更新时间')
    deadline: str | None = Field(None, description='截止时间')
    apply_link: str | None = Field(None, description='投递链接')
    notice_link: str | None = Field(None, description='招聘公告链接')
    referral_code: str | None = Field(None, description='内推码')
    exam_info: str | None = Field(None, description='笔试信息')
    remark: str | None = Field(None, description='备注')


class GetCampusRecruitDetail(CampusRecruitSchemaBase):
    """校招岗位详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='岗位 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
