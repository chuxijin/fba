from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from backend.common.schema import SchemaBase


class AutolabelParam(SchemaBase):
    """AI 自动标注的入参（页面上那些表单字段）。"""

    system_id: int = Field(gt=0, description='知识体系 ID')

    # ---- 题源：三选一，至少填一个 ----
    section_ids: list[int] = Field(default_factory=list, description='章节 ID 列表')
    bank_ids: list[int] = Field(default_factory=list, description='题库 ID 列表')
    question_ids: list[int] = Field(default_factory=list, description='指定题目 ID 列表')

    # ---- 候选知识点范围 ----
    point_ids: list[int] = Field(default_factory=list, description='指定候选知识点；留空则按 root/leaves 取')
    root_point_id: int | None = Field(None, gt=0, description='限定在某棵子树内')
    leaves_only: bool = Field(True, description='只把叶子知识点作为候选（推荐）')

    # ---- 引擎 ----
    engine: Literal['jev', 'chat'] = Field('jev', description='jev=决策模型，chat=对话模型')
    provider_id: int | None = Field(None, gt=0, description='AI 供应商 ID；留空自动取')
    model_id: str | None = Field(None, description='模型 ID；留空自动取')

    # ---- 行为开关 ----
    threshold: float = Field(0.6, ge=0, le=1, description='低于此置信度直接丢弃')
    limit: int = Field(200, ge=1, le=2000, description='最多处理多少题（同步执行，上限 2000）')
    write: bool = Field(False, description='False=干跑只统计不落库，True=真正写入')
    include_labeled: bool = Field(True, description='是否包含已标注的题（重标要开）')
    overwrite_manual: bool = Field(False, description='是否允许覆盖人工标注（source=manual）')
    use_description: bool = Field(True, description='用知识点说明做特征描述（页面上可维护）')
    with_other: bool = Field(False, description='是否给模型一个「都不属于」兜底项')
    sleep: float = Field(0.05, ge=0, le=5, description='每题之间的间隔秒数')

    @field_validator('section_ids', 'bank_ids', 'question_ids', 'point_ids')
    @classmethod
    def _drop_empty(cls, value: list[int]) -> list[int]:
        return [item for item in value if item > 0]

    @model_validator(mode='after')
    def _check_scope(self) -> AutolabelParam:
        """⚠️ 用 model_validator 而不是手写 validate_scope() ——
        后者抛的 ValueError 会变500，pydantic 才保证 422 + 明确报错信息。"""
        if not any([self.section_ids, self.bank_ids, self.question_ids]):
            msg = '必须至少选择章节、题库或题目之一，避免误伤全库'
            raise ValueError(msg)
        return self


class AutolabelItem(SchemaBase):
    """单题结果。低置信度的（status=skipped）不返回。"""

    question_id: int
    point_id: int | None = None
    point_name: str | None = None
    confidence: float | None = None
    status: Literal['written', 'dry_run', 'skipped', 'abstain', 'invalid', 'failed']
    note: str = ''


class AutolabelBankSummary(SchemaBase):
    bank_id: int
    bank_name: str
    categories: str = '(无分类)'
    questions: int


class AutolabelResult(SchemaBase):
    total_matched: int = Field(description='筛选条件命中的总题数')
    processed: int = Field(description='本次实际处理数（受 limit 限制）')
    candidates: list[str] = Field(description='本次的候选知识点（完整路径）')
    bank_summary: list[AutolabelBankSummary] = Field(description='按题库汇总，先看清这批题是什么域')
    items: list[AutolabelItem]
    statistics: dict[str, int] = Field(description='written/dry_run/skipped/abstain/invalid/failed 计数')
    write: bool
    threshold: float
    engine: str
    elapsed_seconds: float
    truncated: bool = Field(False, description='命中数超过 limit，本次只跑了一部分')


class DecisionModelItem(SchemaBase):
    """给页面的模型下拉用。"""

    provider_id: int
    provider_name: str
    api_host: str
    model_id: str
    model_id_pk: int


class ChapterNode(SchemaBase):
    id: int
    name: str
    parent_id: int | None = None
    bank_revision_id: int
    bank_id: int
    question_count: int = 0
    children: list[ChapterNode] = Field(default_factory=list)


class ChapterTreeGroup(SchemaBase):
    bank_id: int
    sections: list[ChapterNode]


class CandidatePointItem(SchemaBase):
    """候选知识点预览，带说明 —— 页面上顺带就能改说明。"""

    id: int
    name: str
    description: str = ''
    depth: int
    path_text: str


class CandidatePointList(SchemaBase):
    points: list[CandidatePointItem]
    total: int


class PreviewParam(SchemaBase):
    """干跑预览：只算命中数与按题库汇总，不调模型。"""

    system_id: int = Field(gt=0)
    section_ids: list[int] = Field(default_factory=list)
    bank_ids: list[int] = Field(default_factory=list)
    question_ids: list[int] = Field(default_factory=list)
    include_labeled: bool = True
    overwrite_manual: bool = False

    @field_validator('section_ids', 'bank_ids', 'question_ids')
    @classmethod
    def _drop_empty(cls, value: list[int]) -> list[int]:
        return [item for item in value if item > 0]

    @model_validator(mode='after')
    def _check_scope(self) -> PreviewParam:
        if not any([self.section_ids, self.bank_ids, self.question_ids]):
            msg = '必须至少选择章节、题库或题目之一，避免误伤全库'
            raise ValueError(msg)
        return self


class PreviewResult(SchemaBase):
    total_matched: int
    bank_summary: list[AutolabelBankSummary]
    payload: dict[str, Any] = Field(default_factory=dict, description='实际用的筛选 SQL 片段与参数')
