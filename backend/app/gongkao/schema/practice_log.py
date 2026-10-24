from datetime import date, datetime
from typing import Literal, Self
from urllib.parse import urlparse

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase


class PracticeModuleValues(SchemaBase):
    """模块原始统计，子模块之间允许存在重叠"""

    module_name: str = Field(min_length=1, max_length=100, description='模块名称')
    total_questions: int = Field(ge=1, description='该模块题数')
    correct_count: int = Field(ge=0, description='该模块正确数')
    unanswered_count: int | None = Field(None, ge=0, description='未答题数，未知时为空')
    duration_seconds: int | None = Field(None, ge=0, description='该模块用时（秒）')
    seq_no: int = Field(default=0, description='排序序号')

    @model_validator(mode='after')
    def validate_counts(self) -> Self:
        self.module_name = self.module_name.strip()
        if not self.module_name:
            raise ValueError('模块名称不能为空')
        if self.correct_count + (self.unanswered_count or 0) > self.total_questions:
            raise ValueError('正确数与未答数之和不能超过题数')
        return self


class CreatePracticeSubModuleParam(PracticeModuleValues):
    model_config = ConfigDict(extra='forbid')


class CreatePracticeModuleParam(PracticeModuleValues):
    children: list[CreatePracticeSubModuleParam] = Field(default_factory=list, max_length=100, description='直属子模块')


class UpdatePracticeModuleParam(CreatePracticeModuleParam):
    pass


class CreatePracticeLogParam(SchemaBase):
    material_type: Literal['exam', 'practice', 'special'] = 'exam'
    material_title: str = Field(min_length=1, max_length=200, description='练习材料标题')
    subject_name: str = Field(default='行测', min_length=1, max_length=100, description='科目名称')
    total_questions: int = Field(ge=1, description='总题数')
    correct_count: int = Field(ge=0, description='正确数')
    unanswered_count: int | None = Field(None, ge=0, description='未答题数，未知时为空')
    duration_seconds: int | None = Field(None, ge=0, description='练习用时（秒）')
    practiced_at: date = Field(description='练习日期')
    remark: str | None = Field(None, description='备注')
    score: float | None = Field(None, ge=0, allow_inf_nan=False, description='得分')
    full_score: float | None = Field(None, gt=0, allow_inf_nan=False, description='满分')
    modules: list[CreatePracticeModuleParam] = Field(default_factory=list, max_length=100, description='模块列表')

    @model_validator(mode='after')
    def validate_counts(self) -> Self:
        if self.correct_count + (self.unanswered_count or 0) > self.total_questions:
            raise ValueError('正确数与未答数之和不能超过总题数')
        if self.score is not None and self.full_score is not None and self.score > self.full_score:
            raise ValueError('得分不能超过满分')
        return self


class ImportPracticeReportParam(CreatePracticeLogParam):
    source_platform: Literal['fenbi'] = 'fenbi'
    source_key: str = Field(pattern=r'^\d+_\d+_[A-Za-z0-9]+$', max_length=128, description='粉笔报告编号')
    source_url: str = Field(max_length=512, description='原始报告页面')
    source_updated_at: datetime | None = Field(None, description='平台更新时间（含时区）')
    time_source: Literal['history_updated', 'manual'] = 'manual'

    @model_validator(mode='after')
    def validate_report(self) -> Self:
        url = urlparse(self.source_url)
        if url.scheme != 'https' or url.netloc != 'spa.fenbi.com' or url.path != f'/ti/exam/solution/{self.source_key}':
            raise ValueError('报告地址与报告编号不匹配')
        if self.source_updated_at is not None and self.source_updated_at.tzinfo is None:
            raise ValueError('平台更新时间必须包含时区')
        if self.time_source == 'history_updated' and self.source_updated_at is None:
            raise ValueError('历史日期来源缺少平台更新时间')
        if not self.modules:
            raise ValueError('报告缺少模块统计')
        # 仅一级考试模块可合计；直属知识点可能重复覆盖同一道题。
        if sum(m.total_questions for m in self.modules) != self.total_questions:
            raise ValueError('一级模块题数与整卷不一致，请等待报告加载完整')
        if sum(m.correct_count for m in self.modules) != self.correct_count:
            raise ValueError('一级模块正确数与整卷不一致')
        return self


class UpdatePracticeLogParam(SchemaBase):
    material_type: Literal['exam', 'practice', 'special'] | None = None
    material_title: str | None = Field(None, min_length=1, max_length=200)
    subject_name: str | None = Field(None, min_length=1, max_length=100)
    total_questions: int | None = Field(None, ge=1)
    correct_count: int | None = Field(None, ge=0)
    unanswered_count: int | None = Field(None, ge=0)
    duration_seconds: int | None = Field(None, ge=0, description='练习用时（秒）')
    practiced_at: date | None = None
    remark: str | None = None
    score: float | None = Field(None, ge=0, allow_inf_nan=False)
    full_score: float | None = Field(None, gt=0, allow_inf_nan=False)
    modules: list[UpdatePracticeModuleParam] | None = Field(None, max_length=100)


class GetPracticeSubModuleDetail(PracticeModuleValues):
    model_config = ConfigDict(from_attributes=True)
    id: int
    accuracy_rate: float | None = None


class GetPracticeModuleDetail(GetPracticeSubModuleDetail):
    children: list[GetPracticeSubModuleDetail] = Field(default_factory=list)


class GetPracticeLogDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    material_type: str
    material_title: str
    subject_name: str = '行测'
    source_platform: str = 'manual'
    source_key: str | None = None
    source_url: str | None = None
    source_updated_at: datetime | None = None
    time_source: str = 'manual'
    total_questions: int
    correct_count: int
    unanswered_count: int | None = None
    accuracy_rate: float | None = None
    duration_seconds: int | None = Field(None, description='练习用时（秒）')
    score: float | None = None
    full_score: float | None = None
    practiced_at: date
    remark: str | None = None
    modules: list[GetPracticeModuleDetail] = Field(default_factory=list)
    created_time: datetime
    updated_time: datetime | None = None


class GetPracticeLogListItem(GetPracticeLogDetail):
    module_count: int = 0


class ImportPracticeReportResult(SchemaBase):
    created: bool
    record: GetPracticeLogDetail
