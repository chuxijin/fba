from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.question_bank_v2.schema.question import QuestionType
from backend.common.schema import SchemaBase


class CreateBankSectionParam(SchemaBase):
    """创建题库版本章节参数"""

    code: str = Field(min_length=1, max_length=64, description='版本内章节编码')
    name: str = Field(min_length=1, max_length=160, description='章节名称')
    parent_id: int | None = Field(None, gt=0, description='同题库版本内父章节 ID')
    sort_order: int = Field(default=0, description='同层排序')


class UpdateBankSectionParam(SchemaBase):
    """更新题库版本章节参数"""

    code: str | None = Field(None, min_length=1, max_length=64, description='版本内章节编码')
    name: str | None = Field(None, min_length=1, max_length=160, description='章节名称')
    parent_id: int | None = Field(None, gt=0, description='同题库版本内父章节 ID')
    sort_order: int | None = Field(None, description='同层排序')


class GetBankSectionDetail(SchemaBase):
    """题库版本章节详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='章节 ID')
    bank_revision_id: int = Field(description='题库版本 ID')
    code: str = Field(description='版本内章节编码')
    name: str = Field(description='章节名称')
    parent_id: int | None = Field(None, description='父章节 ID')
    depth: int = Field(description='章节树深度')
    sort_order: int = Field(description='同层排序')
    question_count: int = Field(default=0, ge=0, description='含后代章节的启用题目数')
    question_type_counts: dict[str, int] = Field(default_factory=dict, description='含后代章节的各题型题目数')
    children: list['GetBankSectionDetail'] = Field(default_factory=list, description='子章节列表')


class CreateBankItemParam(SchemaBase):
    """创建题库版本题目编排参数"""

    item_key: str = Field(min_length=1, max_length=64, description='版本内稳定题号或业务键')
    question_id: int = Field(gt=0, description='题目稳定身份 ID')
    section_id: int | None = Field(None, gt=0, description='同题库版本内章节 ID')
    exam_year: int | None = Field(None, ge=1900, le=2100, description='试题年份；非真题可为空')
    score: Decimal = Field(default=Decimal('1.00'), ge=0, description='本题分值')
    sort_order: int = Field(default=0, ge=0, description='题目顺序')
    is_required: bool = Field(default=True, description='是否必答')
    is_active: bool = Field(default=True, description='是否启用')
    settings: dict[str, Any] = Field(default_factory=dict, description='题库上下文展示或随机化设置')


class UpdateBankItemParam(SchemaBase):
    """更新题库版本题目编排参数"""

    item_key: str | None = Field(None, min_length=1, max_length=64, description='版本内稳定题号或业务键')
    question_id: int | None = Field(None, gt=0, description='题目稳定身份 ID')
    section_id: int | None = Field(None, gt=0, description='同题库版本内章节 ID')
    exam_year: int | None = Field(None, ge=1900, le=2100, description='试题年份；非真题可为空')
    score: Decimal | None = Field(None, ge=0, description='本题分值')
    sort_order: int | None = Field(None, ge=0, description='题目顺序')
    is_required: bool | None = Field(None, description='是否必答')
    is_active: bool | None = Field(None, description='是否启用')
    settings: dict[str, Any] | None = Field(None, description='题库上下文展示或随机化设置')


class GetBankItemDetail(SchemaBase):
    """题库版本题目编排详情"""

    id: int = Field(description='题目编排 ID')
    bank_revision_id: int = Field(description='题库版本 ID')
    item_key: str = Field(description='版本内稳定题号或业务键')
    question_id: int = Field(description='题目稳定身份 ID')
    section_id: int | None = Field(None, description='章节 ID')
    exam_year: int | None = Field(None, description='试题年份')
    score: Decimal = Field(description='本题分值')
    sort_order: int = Field(description='题目顺序')
    is_required: bool = Field(description='是否必答')
    is_active: bool = Field(description='是否启用')
    settings: dict[str, Any] = Field(description='题库上下文展示或随机化设置')
    question_type: QuestionType = Field(description='固定题目版本的题型')
    stem: str = Field(description='固定题目版本的题干')
    created_time: datetime = Field(description='创建时间')


class GetBankCompositionDetail(SchemaBase):
    """题库版本编排详情"""

    bank_id: int = Field(description='题库稳定身份 ID')
    bank_revision_id: int = Field(description='题库版本 ID')
    revision_status: str = Field(description='题库版本状态')
    sections: list[GetBankSectionDetail] = Field(default_factory=list, description='章节树')
    items: list[GetBankItemDetail] = Field(
        default_factory=list,
        description='兼容字段，始终为空；题目编排通过分页 items 接口读取',
    )
