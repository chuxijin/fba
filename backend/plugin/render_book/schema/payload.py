#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase
from backend.plugin.render_book.schema.render import (
    BookKind,
    RenderAnswerLayout,
    RenderContentMode,
    RenderDeliveryMode,
    RenderOptions,
    RenderOutputTargets,
    RenderVariant,
    SolutionMode,
)


class RenderBookMeta(SchemaBase):
    title: str = Field(description='题本标题')
    subtitle: str | None = Field(default=None, description='题本副标题')
    meta_lines: list[str] = Field(default_factory=list, description='题本附加说明行')


class RenderMaterialPayload(SchemaBase):
    id: int = Field(description='材料 ID')
    title: str | None = Field(default=None, description='材料标题')
    content_text: str = Field(description='材料正文')
    source_text: str | None = Field(default=None, description='材料来源')
    year: int | None = Field(default=None, description='材料年份')
    bank_id: int | None = Field(default=None, description='所属题库 ID')
    bank_name: str | None = Field(default=None, description='所属题库名称')


class RenderQuestionOptionPayload(SchemaBase):
    key: str = Field(description='选项编码')
    content_text: str = Field(description='选项内容')


class RenderQuestionPayload(SchemaBase):
    number: int = Field(description='题号')
    question_id: int = Field(description='题目 ID')
    placement_id: int | None = Field(default=None, description='挂载 ID')
    type: str = Field(description='题型编码')
    type_label: str = Field(description='题型名称')
    stem_text: str = Field(description='题干文本/富文本原文')
    stem_tex: str | None = Field(default=None, description='题干 LaTeX 版本')
    options: list[RenderQuestionOptionPayload] = Field(default_factory=list, description='选项列表')
    answer_text: str | None = Field(default=None, description='答案文本')
    answer_raw: dict[str, Any] | None = Field(default=None, description='原始答案结构')
    analysis_text: str | None = Field(default=None, description='解析文本')
    source_text: str | None = Field(default=None, description='题目来源说明')
    source_label: str | None = Field(default=None, description='题目前短来源标签')
    difficulty: str | None = Field(default=None, description='难度')
    score: str | None = Field(default=None, description='分值文本')
    knowledge_points: list[str] = Field(default_factory=list, description='考点列表')
    bank_id: int | None = Field(default=None, description='题库 ID')
    bank_name: str | None = Field(default=None, description='题库名称')
    chapter_id: int | None = Field(default=None, description='章节 ID')
    chapter_name: str | None = Field(default=None, description='章节名称')
    material_ids: list[int] = Field(default_factory=list, description='关联材料 ID')
    tags: list[str] = Field(default_factory=list, description='扩展标签')


class RenderWordPayload(SchemaBase):
    """汉语词汇载荷"""

    name: str = Field(description='词语名称')
    type: str | None = Field(default=None, description='类型')
    pinyin: str | None = Field(default=None, description='拼音')
    baobian: str | None = Field(default=None, description='褒贬色彩')
    structure: str | None = Field(default=None, description='结构')
    definition_info: str | dict | None = Field(default=None, description='释义信息')
    detail_means: list | dict | None = Field(default=None, description='详细含义')
    liju: list | None = Field(default=None, description='例句')
    synonyms: list | None = Field(default=None, description='近义词')
    antonym: list | None = Field(default=None, description='反义词')
    chu_chu: dict | list | str | None = Field(default=None, description='出处')
    yin_zheng: dict | list | str | None = Field(default=None, description='引证')
    frequency: int = Field(default=0, description='频次')


class RenderSectionPayload(SchemaBase):
    """分节载荷"""

    key: str = Field(description='分节键')
    title: str = Field(description='分节标题')
    questions: list[RenderQuestionPayload] = Field(default_factory=list, description='题目列表')
    words: list[RenderWordPayload] = Field(default_factory=list, description='词汇列表')


class RenderPaperPayload(SchemaBase):
    """题本正文"""

    question_count: int = Field(default=0, description='题目总数')
    material_count: int = Field(default=0, description='材料总数')
    sections: list[RenderSectionPayload] = Field(default_factory=list, description='分节列表')
    materials: list[RenderMaterialPayload] = Field(default_factory=list, description='材料列表')


class RenderPlanPayload(SchemaBase):
    book_kind: BookKind = Field(description='题本类型')
    content_mode: RenderContentMode = Field(description='导出内容模式')
    answer_layout: RenderAnswerLayout | None = Field(default=None, description='解析排版结构')
    delivery_mode: RenderDeliveryMode = Field(description='交付方式')
    solution_mode: SolutionMode = Field(description='解析排版方式')
    output_targets: RenderOutputTargets = Field(description='输出目标')
    render_variants: list[RenderVariant] = Field(default_factory=list, description='建议渲染变体')


class RenderDocumentPayload(SchemaBase):
    template_key: str = Field(description='模板键')
    render_plan: RenderPlanPayload = Field(description='渲染计划')
    book: RenderBookMeta = Field(description='题本元信息')
    options: RenderOptions = Field(description='渲染选项')
    paper: RenderPaperPayload = Field(description='题本正文')
    metadata: dict[str, Any] = Field(default_factory=dict, description='附加上下文')
