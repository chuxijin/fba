from decimal import Decimal
from typing import Literal

from pydantic import Field

from backend.common.schema import SchemaBase

BankKind = Literal['practice', 'paper', 'mock']


class ImportRowResult(SchemaBase):
    """导入结果行"""

    row_number: int = Field(description='Excel 行号')
    success: bool = Field(description='是否成功')
    question_id: int | None = Field(None, description='题目 ID')
    error_message: str | None = Field(None, description='错误信息')


class BankImportResult(SchemaBase):
    """题库导入结果"""

    bank_id: int = Field(description='题库 ID')
    bank_revision_id: int = Field(description='题库版本 ID')
    total: int = Field(description='总行数')
    success_count: int = Field(description='成功数')
    fail_count: int = Field(description='失败数')
    details: list[ImportRowResult] = Field(default_factory=list, description='逐行结果')
