import re

from decimal import Decimal
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase

EXAM_TARGET_DICT_CODE = 'study_exam_target'
DomainCode = Literal['gongkao', 'kaoyan', 'cet', 'jiaozhi']


class GoalSchema(SchemaBase):
    model_config = ConfigDict(extra='forbid')


class ExamModule(GoalSchema):
    knowledge_point_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=160)
    count: int = Field(ge=1, le=500)


class ExamCategory(GoalSchema):
    code: str = Field(min_length=1, max_length=32, pattern=r'^[a-z0-9_]+$')
    name: str = Field(min_length=1, max_length=64)
    children: list['ExamCategory'] = Field(default_factory=list, max_length=50)


class ExamTemplate(GoalSchema):
    key: str = Field(min_length=1, max_length=32, pattern=r'^[a-z0-9_]+$')
    name: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=32, pattern=r'^[a-z0-9_]+$')
    subject_name: str = Field(min_length=1, max_length=32)
    category_code: str | None = Field(None, min_length=1, max_length=32, pattern=r'^[a-z0-9_]+$')
    years: list[int] = Field(default_factory=list, max_length=30, description='留空沿用目标年度；非空仅限这些年度')
    knowledge_system_id: int = Field(gt=0)
    bank_id: int = Field(gt=0, description='显式题池范围；沿用原题库准入，不以文字匹配地区')
    total: int = Field(ge=1, le=500)
    duration_minutes: int = Field(ge=1, le=600)
    modules: list[ExamModule] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def check_quotas(self) -> 'ExamTemplate':
        ids = [item.knowledge_point_id for item in self.modules]
        if len(set(ids)) != len(ids) or sum(item.count for item in self.modules) != self.total:
            raise ValueError('模块不能重复，且模块题量之和必须等于总题数')
        return self


class ExamTargetConfig(GoalSchema):
    version: str = Field(min_length=1, max_length=32)
    domain_code: DomainCode
    region_code: str | None = Field(None, max_length=32)
    exam_kind: str = Field(min_length=1, max_length=32)
    years: list[int] = Field(min_length=1, max_length=30, description='明确适用的报考年度')
    subjects: dict[str, str] = Field(min_length=1, max_length=20, description='科目编码与名称；可以先建目录，后补模板')
    categories: list[ExamCategory] = Field(default_factory=list, max_length=50, description='地区下的考试类别树，仅末级可选')
    templates: list[ExamTemplate] = Field(default_factory=list, max_length=30)

    def category_path(self, code: str | None) -> list[ExamCategory]:
        pending = [(node, [node]) for node in self.categories]
        while pending:
            node, path = pending.pop()
            if node.code == code:
                return path
            pending.extend((child, [*path, child]) for child in node.children)
        return []

    @model_validator(mode='after')
    def check_config(self) -> 'ExamTargetConfig':
        if len(set(self.years)) != len(self.years) or any(year < 1900 or year > 2100 for year in self.years):
            raise ValueError('报考年度不能重复且应在1900至2100之间')
        keys = [item.key for item in self.templates]
        if len(keys) != len(set(keys)):
            raise ValueError('组卷模板编码不能重复')
        category_codes: set[str] = set()
        leaf_codes: set[str] = set()
        pending = [(node, 1) for node in self.categories]
        while pending:
            node, depth = pending.pop()
            if depth > 5 or len(category_codes) >= 200:
                raise ValueError('考试类别最多5层、200个节点')
            if node.code in category_codes or not node.name.strip():
                raise ValueError('目标内考试类别编码不能重复，名称不能为空')
            category_codes.add(node.code)
            if not node.children:
                leaf_codes.add(node.code)
            pending.extend((child, depth + 1) for child in node.children)
        for template in self.templates:
            if (self.categories and template.category_code not in leaf_codes) or (
                not self.categories and template.category_code is not None
            ):
                raise ValueError('组卷模板必须绑定本目标的末级考试类别；无类别目录不能指定类别')
            if len(set(template.years)) != len(template.years) or any(year not in self.years for year in template.years):
                raise ValueError('模板年度不能重复且必须属于目标年度')
        if any(
            re.fullmatch(r'[a-z0-9_]{1,32}', key) is None or not name.strip() or len(name) > 32
            for key, name in self.subjects.items()
        ):
            raise ValueError('科目编码仅允许小写字母、数字和下划线，科目名称不能为空且最多32字符')
        if any(
            item.subject not in self.subjects or item.subject_name != self.subjects[item.subject]
            for item in self.templates
        ):
            raise ValueError('组卷模板科目必须与目录一致')
        return self


class StudyGoal(GoalSchema):
    exam_target_code: str = Field(min_length=1, max_length=32, pattern=r'^[a-z0-9_]+$')
    exam_year: int = Field(ge=1900, le=2100)
    category_code: str | None = Field(None, min_length=1, max_length=32, pattern=r'^[a-z0-9_]+$')
    subjects: list[str] = Field(min_length=1, max_length=20)
    target_scores: dict[str, Decimal] = Field(default_factory=dict)

    @model_validator(mode='after')
    def check_subjects(self) -> 'StudyGoal':
        if len(set(self.subjects)) != len(self.subjects):
            raise ValueError('备考科目不能重复')
        if any(not value or len(value) > 32 for value in self.subjects):
            raise ValueError('备考科目编码无效')
        if any(
            key not in self.subjects or not score.is_finite() or score < 0 or score > 1000
            for key, score in self.target_scores.items()
        ):
            raise ValueError('目标成绩必须对应已选科目且为0至1000的有限数值')
        return self


class GetExamTarget(GoalSchema):
    code: str
    name: str
    config_revision: str
    config: ExamTargetConfig


class CreateGoalExamParam(GoalSchema):
    exam_target_code: str = Field(min_length=1, max_length=32)
    exam_year: int = Field(ge=1900, le=2100)
    category_code: str | None = Field(None, min_length=1, max_length=32, pattern=r'^[a-z0-9_]+$')
    template_key: str = Field(min_length=1, max_length=32)
    config_revision: str = Field(min_length=64, max_length=64)
    session_key: str = Field(min_length=8, max_length=64)
