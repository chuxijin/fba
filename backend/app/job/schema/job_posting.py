from datetime import datetime
from typing import Optional, Any

from pydantic import Field

from backend.common.pagination import PageData, _CustomPageParams
from backend.common.schema import SchemaBase


class CreateJobPosting(SchemaBase):
    """创建招聘信息入参"""

    company_name: str = Field(..., description="公司名称")
    company_type: Optional[str] = Field(None, description="公司类型")
    industry: Optional[str] = Field(None, description="所属行业")
    recruitment_type: Optional[str] = Field(None, description="招聘类型")
    work_location: Optional[str] = Field(None, description="工作地点")
    recruitment_object: Optional[str] = Field(None, description="招聘对象")
    position: str = Field(..., description="岗位")
    delivery_start: Optional[datetime] = Field(None, description="投递开始日期")
    delivery_end: Optional[datetime] = Field(None, description="投递截止日期")
    delivery_link: Optional[str] = Field(None, description="投递链接")
    recruitment_announcement: Optional[str] = Field(None, description="招聘公告")
    referral_code: Optional[str] = Field(None, description="内推码")
    remark: Optional[str] = Field(None, description="备注")
    salary_range: Optional[str] = Field(None, description="薪资范围")
    is_exempt_from_written_test: Optional[bool] = Field(None, description="是否免笔试")
    logo_url: Optional[str] = Field(None, description="公司Logo URL")


class UpdateJobPosting(CreateJobPosting):
    """更新招聘信息入参"""

    pass


class GetJobPostingListParams(_CustomPageParams):
    """获取招聘信息列表参数"""

    company_name: Optional[str] = Field(None, description="公司名称")
    position: Optional[str] = Field(None, description="岗位")
    industry: Optional[str] = Field(None, description="所属行业")
    recruitment_type: Optional[str] = Field(None, description="招聘类型")


class GetJobPostingDetail(SchemaBase):
    """招聘信息详情"""

    id: int = Field(..., description="招聘信息 ID")
    company_name: str = Field(..., description="公司名称")
    company_type: Optional[str] = Field(None, description="公司类型")
    industry: Optional[str] = Field(None, description="所属行业")
    recruitment_type: Optional[str] = Field(None, description="招聘类型")
    work_location: Optional[str] = Field(None, description="工作地点")
    recruitment_object: Optional[str] = Field(None, description="招聘对象")
    position: str = Field(..., description="岗位")
    delivery_start: Optional[datetime] = Field(None, description="投递开始日期")
    delivery_end: Optional[datetime] = Field(None, description="投递截止日期")
    delivery_link: Optional[str] = Field(None, description="投递链接")
    recruitment_announcement: Optional[str] = Field(None, description="招聘公告")
    referral_code: Optional[str] = Field(None, description="内推码")
    remark: Optional[str] = Field(None, description="备注")
    salary_range: Optional[str] = Field(None, description="薪资范围")
    is_exempt_from_written_test: Optional[bool] = Field(None, description="是否免笔试")
    logo_url: Optional[str] = Field(None, description="公司Logo URL")

    model_config = {"from_attributes": True}


class JobPostingSchema(GetJobPostingDetail):
    """招聘信息"""

    pass
