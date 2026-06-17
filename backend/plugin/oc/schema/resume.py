"""简历 Schema"""

from pydantic import BaseModel, Field
from datetime import datetime


class SaveResumeParam(BaseModel):
    """保存简历参数（加密数据）"""

    encrypted_data: str = Field(..., description='加密的简历数据')
    data_hash: str = Field(..., description='数据哈希')


class GetResumeDetail(BaseModel):
    """简历详情"""

    id: int
    user_id: int
    encrypted_data: str
    data_hash: str
    created_time: datetime
    updated_time: datetime | None


class FieldInfo(BaseModel):
    """表单字段信息"""

    index: int
    tagName: str
    type: str
    name: str = ''
    id: str = ''
    placeholder: str = ''
    label: str = ''
    ariaLabel: str = ''
    nearby_text: str = ''
    options: list[str] | None = None


class IdentifyFieldsParam(BaseModel):
    """AI 识别字段参数"""

    fields: list[FieldInfo]


class FieldMapping(BaseModel):
    """字段映射结果"""

    fieldIndex: int
    resumeField: str
    confidence: float


class IdentifyFieldsResult(BaseModel):
    """AI 识别结果"""

    mappings: list[FieldMapping]


class SelectorFillParam(BaseModel):
    """下拉选项匹配参数"""

    resume_key: str = Field(..., description='简历字段 key，如 ;gender@性别')
    resume_value: str = Field(..., description='简历中的值，如 女')
    candidates_value: list[str] = Field(..., description='下拉框可选项列表')
    label: str = Field('', description='字段标签')
    resume_data: dict | None = Field(None, description='完整简历数据（用于 AI 上下文）')


class SelectorFillResult(BaseModel):
    """下拉选项匹配结果"""

    matched_value: str | None = Field(None, description='匹配到的选项值，None 表示无匹配')


class ParsePdfParam(BaseModel):
    """PDF 解析参数"""

    text: str = Field(..., description='PDF 提取的文本内容')
