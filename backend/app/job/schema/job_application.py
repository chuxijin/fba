from pydantic import Field
from typing import Optional

from backend.common.enums import ApplicationStatus
from backend.common.pagination import _CustomPageParams
from backend.common.schema import SchemaBase


class CreateJobApplication(SchemaBase):
    """创建投递记录入参"""

    job_posting_id: int = Field(..., description="招聘信息 ID")
    application_status: ApplicationStatus = Field(..., description="投递状态")


class UpdateJobApplication(CreateJobApplication):
    """更新投递记录入参"""

    pass


class GetJobApplicationListParams(_CustomPageParams):
    """获取投递记录列表参数"""

    job_posting_id: Optional[int] = Field(None, description="招聘信息 ID")
    application_status: Optional[ApplicationStatus] = Field(None, description="投递状态")


class GetJobApplicationDetail(SchemaBase):
    """投递记录详情"""

    id: int = Field(..., description="投递记录 ID")
    job_posting_id: int = Field(..., description="招聘信息 ID")
    application_status: ApplicationStatus = Field(..., description="投递状态")

    model_config = {"from_attributes": True}


class JobApplicationSchema(GetJobApplicationDetail):
    """投递记录"""

    pass
