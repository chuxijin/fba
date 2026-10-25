from datetime import date
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, JsonValue, model_validator

from backend.app.question_bank_v2.schema.question import (
    ContentFormat,
    QuestionAnswerParam,
    QuestionExplanationParam,
    QuestionOption,
    QuestionType,
)
from backend.app.question_bank_v2.schema.review import ExternalMaterialParam, ExternalQuestionAssetParam
from backend.common.schema import SchemaBase


class ImportPracticeQuestionParam(SchemaBase):
    """外部报告的一道题及当次作答；题号由原试卷提供，不能从答案字典顺序推断。"""

    model_config = ConfigDict(extra='forbid')

    source_question_key: str = Field(min_length=1, max_length=160, description='平台内稳定题目标识')
    position: int = Field(ge=1, le=500, description='原卷题号，从 1 开始')
    module_path: list[str] = Field(min_length=1, max_length=3, description='模块/子模块/具体题型，不包含科目')
    stem: str = Field(min_length=1, max_length=1_000_000, description='题干富文本')
    content_format: ContentFormat = 'html'
    question_type: QuestionType = 'single_choice'
    options: list[QuestionOption] = Field(default_factory=list, max_length=20)
    answer: QuestionAnswerParam | None = Field(None, description='来源未提供时为空，后续可补全')
    explanations: list[QuestionExplanationParam] = Field(default_factory=list, max_length=20)
    materials: list[ExternalMaterialParam] = Field(default_factory=list, max_length=5)
    assets: list[ExternalQuestionAssetParam] = Field(default_factory=list, max_length=20)
    status: Literal['correct', 'wrong', 'unanswered']
    response_data: JsonValue = Field(default=None, description='本次实际答案；未答时为空')
    duration_seconds: int | None = Field(None, ge=0, le=86_400, description='原平台逐题用时，未知为空，0 为零秒')
    score: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=2)
    max_score: Decimal | None = Field(None, ge=0, max_digits=8, decimal_places=2)

    @model_validator(mode='after')
    def validate_question(self) -> Self:
        self.source_question_key = self.source_question_key.strip()
        self.module_path = [part.strip() for part in self.module_path]
        if not self.source_question_key or not self.stem.strip() or not all(self.module_path):
            raise ValueError('题目标识、题干和题型路径不能为空')
        if self.status == 'unanswered' and self.response_data not in (None, '', [], {}):
            raise ValueError('未答题不能带有已提交答案')
        if self.status != 'unanswered' and self.response_data in (None, '', [], {}):
            raise ValueError('已答题必须提供当次实际答案')
        if self.status == 'unanswered':
            self.response_data = None
        if self.score is not None and self.max_score is not None and self.score > self.max_score:
            raise ValueError('单题得分不能超过单题满分')
        self._validate_choices()
        self._validate_content_links()
        return self

    def _validate_choices(self) -> None:
        codes = [option.option_code for option in self.options]
        if len(codes) != len(set(codes)):
            raise ValueError('选项编码不能重复')
        if self.question_type in {'single_choice', 'multiple_choice'} and len(codes) < 2:
            raise ValueError('选择题至少提供两个选项')
        if self.question_type in {'single_choice', 'multiple_choice'}:
            if self.answer is not None and not self.answer.answer_data.get('correct'):
                raise ValueError('选择题标准答案必须包含 correct 选项编码')
            for value in (self.response_data, self.answer.answer_data.get('correct') if self.answer else None):
                if value is None:
                    continue
                choices = value if isinstance(value, list) else [value]
                if not choices or any(choice not in codes for choice in choices):
                    raise ValueError('选择题答案必须对应原始选项编码')
                if self.question_type == 'single_choice' and len(choices) != 1:
                    raise ValueError('单选题只能选择一个选项')

    def _validate_content_links(self) -> None:
        if len({item.explanation_type for item in self.explanations}) != len(self.explanations):
            raise ValueError('解析类型不能重复')
        if self.explanations and sum(item.is_default for item in self.explanations) != 1:
            raise ValueError('提供解析时必须且只能有一个默认解析')
        if len({(item.link_key, item.role) for item in self.materials}) != len(self.materials):
            raise ValueError('材料关联不能重复')
        if len({item.link_key for item in self.assets}) != len(self.assets):
            raise ValueError('资源引用键不能重复')


class GetImportedPracticeQuestion(ImportPracticeQuestionParam):
    session_item_id: int
    question_id: int
    attempt_id: int | None = None
    missing_content: list[str] = Field(default_factory=list, description='尚缺少的标准答案或解析')


class GetImportedPracticeDetail(SchemaBase):
    practice_log_id: int
    session_key: str | None = None
    detail_status: Literal['none', 'partial', 'complete'] = 'none'
    total_questions: int
    imported_questions: int = 0
    practiced_at: date
    source_summary: dict[str, Any] = Field(default_factory=dict, description='平台报告原始汇总，独立于用户编辑')
    items: list[GetImportedPracticeQuestion] = Field(default_factory=list)


class ImportPracticeDetailResult(SchemaBase):
    session_key: str
    imported_questions: int
    detail_status: Literal['partial', 'complete']
    added_questions: int = 0
    supplemented_questions: int = 0
