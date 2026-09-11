from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class OCRecruitAnnouncementSchemaBase(SchemaBase):
    """招聘公告基础模型"""

    company_id: int = Field(description='公司 ID')
    title: str = Field(description='公告标题')
    recruitment_type: str = Field(description='招聘类型（校招/实习/社招）')
    recruit_target: str | None = Field(None, description='招聘对象')
    positions: str | None = Field(None, description='岗位名称')
    start_time: str | None = Field(None, description='开始时间')
    end_time: str | None = Field(None, description='截止时间')
    location: str | None = Field(None, description='工作地点')
    exam_info: str | None = Field(None, description='笔试情况')
    referral_code: str | None = Field(None, description='内推码')
    apply_url: str | None = Field(None, description='投递链接（本帖）')
    notice_url: str | None = Field(None, description='公告链接（本帖）')
    source_update_date: str | None = Field(None, description='源站更新日期（YYYY-MM-DD）')
    remark: str | None = Field(None, description='备注')


class CreateRecruitAnnouncementParam(OCRecruitAnnouncementSchemaBase):
    """创建招聘公告参数"""


class UpdateRecruitAnnouncementParam(SchemaBase):
    """更新招聘公告参数"""

    company_id: int | None = Field(None, description='公司 ID')
    title: str | None = Field(None, description='公告标题')
    recruitment_type: str | None = Field(None, description='招聘类型（校招/实习/社招）')
    recruit_target: str | None = Field(None, description='招聘对象')
    positions: str | None = Field(None, description='岗位名称')
    start_time: str | None = Field(None, description='开始时间')
    end_time: str | None = Field(None, description='截止时间')
    location: str | None = Field(None, description='工作地点')
    exam_info: str | None = Field(None, description='笔试情况')
    referral_code: str | None = Field(None, description='内推码')
    apply_url: str | None = Field(None, description='投递链接（本帖）')
    notice_url: str | None = Field(None, description='公告链接（本帖）')
    source_update_date: str | None = Field(None, description='源站更新日期（YYYY-MM-DD）')
    remark: str | None = Field(None, description='备注')


class GetCompanyBriefDetail(SchemaBase):
    """公司简要信息（公告内嵌）"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='公司 ID')
    name: str = Field(description='公司名称')
    short_name: str | None = Field(None, description='公司简称')
    company_type: str | None = Field(None, description='公司类型')
    industry: str | None = Field(None, description='所属行业')
    company_size: str | None = Field(None, description='公司规模')


class GetRecruitAnnouncementDetail(OCRecruitAnnouncementSchemaBase):
    """招聘公告详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='公告 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetRecruitAnnouncementWithCompanyDetail(GetRecruitAnnouncementDetail):
    """招聘公告详情（含公司信息）"""

    company: GetCompanyBriefDetail = Field(description='公司信息')
