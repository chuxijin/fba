from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from backend.common.schema import SchemaBase


class CreateFeedbackParam(BaseModel):
    type: str = Field(..., description='反馈类型')
    content: str = Field(..., description='反馈内容')
    target_source: Optional[str] = Field(None, description='关联链接/目标')
    images: Optional[list[str]] = Field(None, description='图片附件列表')
    contact: Optional[str] = Field(None, description='联系方式')


class UpdateFeedbackParam(BaseModel):
    status: Optional[str] = Field(None, description='处理状态')
    reply: Optional[str] = Field(None, description='管理员回复/备注')
    view_status: Optional[int] = Field(None, description='查看状态 0未读 1已读')


class DeleteFeedbackParam(BaseModel):
    ids: list[int] = Field(..., description='反馈ID列表')


class FeedbackParam(BaseModel):
    type: Optional[str] = Field(None, description='反馈类型')
    status: Optional[str] = Field(None, description='处理状态')
    content: Optional[str] = Field(None, description='内容模糊搜索')
    contact: Optional[str] = Field(None, description='联系方式模糊搜索')
    view_status: Optional[int] = Field(None, description='查看状态')


class GetFeedbackDetail(SchemaBase):
    id: int
    type: str
    content: str
    target_source: Optional[str] = None
    images: Optional[list[str]] = None
    contact: Optional[str] = None
    status: str
    reply: Optional[str] = None
    ip_address: Optional[str] = None
    view_status: int
    created_time: datetime
    updated_time: datetime

    class Config:
        from_attributes = True
