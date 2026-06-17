"""反馈 Schema"""

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    """反馈创建请求"""

    type: str = Field(..., description='反馈类型', pattern='^(bug|feature|data|other)$')
    content: str = Field(..., min_length=1, max_length=1000, description='内容')
