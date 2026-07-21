#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.common.pagination import _CustomPageParams

JobMode = Literal['preview', 'final']
JobStatus = Literal['accepted', 'running', 'succeeded', 'failed']
FieldType = Literal['string', 'integer', 'boolean', 'single_select', 'multi_select']
IssueLevel = Literal['error', 'warning']
BookKind = Literal['module', 'wrong', 'exam', 'custom']
RenderContentMode = Literal['questions_only', 'questions_with_answers']
RenderAnswerLayout = Literal['inline', 'appendix']
RenderDeliveryMode = Literal['single_pdf', 'split_pdf']
SolutionMode = Literal['none', 'separate', 'inline', 'appendix']
RenderVariant = Literal['questions_only', 'solutions_only', 'combined_inline', 'combined_appendix']
RenderFileKind = Literal['question_pdf', 'solution_pdf', 'combined_pdf']
RenderFileStatus = Literal['available', 'failed']
RenderStorageType = Literal['local', 'oss']
RenderArtifactKind = Literal['pdf', 'log']


LayoutMode = Literal['compact', 'standard', 'loose', 'single', 'pad_landscape', 'pad_portrait']
ThemeColor = Literal['blue', 'green', 'orange', 'purple', 'teal', 'crimson', 'indigo', 'amber']


class RenderOptions(BaseModel):
    include_answer: bool = False
    include_analysis: bool = False
    layout_mode: LayoutMode = 'standard'
    theme: ThemeColor = 'blue'
    dark_mode: bool = False
    show_source: bool = True


class RenderOutputTargets(BaseModel):
    question_pdf: bool = True
    solution_pdf: bool = False


class RenderFieldChoice(BaseModel):
    value: str
    label: str


class RenderFieldSpec(BaseModel):
    key: str
    label: str
    field_type: FieldType
    required: bool = False
    description: str = ''
    default: Any = None
    choices: list[RenderFieldChoice] = Field(default_factory=list)


class RenderTemplateSummary(BaseModel):
    key: str
    version: str = '1.0.0'
    digest: str = ''
    name: str
    description: str
    scene: str
    subject: str | None = None
    estimated_latency: Literal['fast', 'medium', 'slow'] = 'medium'
    default_variant: RenderVariant = 'questions_only'
    supported_variants: list[RenderVariant] = Field(default_factory=lambda: ['questions_only'])


class RenderTemplateDetail(RenderTemplateSummary):
    supported_modes: list[JobMode] = Field(default_factory=lambda: ['preview', 'final'])
    filter_fields: list[RenderFieldSpec] = Field(default_factory=list)
    option_fields: list[RenderFieldSpec] = Field(default_factory=list)
    default_options: RenderOptions = Field(default_factory=RenderOptions)
    notes: list[str] = Field(default_factory=list)


class RenderTemplateManifest(BaseModel):
    key: str
    version: str
    digest: str = ''
    name: str
    description: str = ''
    enabled: bool = True
    entrypoint: str = 'main.tex.j2'
    default_variant: RenderVariant = 'questions_only'
    supported_variants: list[RenderVariant] = Field(default_factory=lambda: ['questions_only'])
    variant_entrypoints: dict[str, str] = Field(default_factory=dict)


class RenderValidationIssue(BaseModel):
    field: str
    level: IssueLevel
    message: str


class RenderJobCreate(BaseModel):
    template_key: str = Field(..., min_length=1, max_length=100)
    template_version: str | None = Field(default=None, min_length=5, max_length=32, description='模板版本')
    book_kind: BookKind | None = Field(default=None, description='题本类型')
    content_mode: RenderContentMode | None = Field(default=None, description='导出内容模式')
    answer_layout: RenderAnswerLayout | None = Field(default=None, description='解析排版结构')
    delivery_mode: RenderDeliveryMode | None = Field(default=None, description='交付方式')
    solution_mode: SolutionMode | None = Field(default=None, description='解析排版方式')
    mode: JobMode = 'final'
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    filters: dict[str, Any] = Field(default_factory=dict)
    options: RenderOptions = Field(default_factory=RenderOptions)
    output_targets: RenderOutputTargets = Field(default_factory=RenderOutputTargets)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderTemplatePreviewRequest(RenderJobCreate):
    render_variant: RenderVariant | None = Field(default=None, description='指定预览渲染变体')
    layout_params: dict[str, Any] = Field(default_factory=dict, description='注入到模板 metadata 的版式参数')
    upload_to_oss: bool = Field(default=True, description='是否上传预览产物到 OSS')


class RenderTemplatePresetPayload(BaseModel):
    title: str = Field(default='', max_length=200)
    subtitle: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    book_kind: BookKind | None = Field(default=None, description='题本类型')
    content_mode: RenderContentMode | None = Field(default=None, description='导出内容模式')
    answer_layout: RenderAnswerLayout | None = Field(default=None, description='解析排版结构')
    delivery_mode: RenderDeliveryMode | None = Field(default=None, description='交付方式')
    solution_mode: SolutionMode | None = Field(default=None, description='解析排版方式')
    filters: dict[str, Any] = Field(default_factory=dict)
    options: RenderOptions = Field(default_factory=RenderOptions)
    output_targets: RenderOutputTargets = Field(default_factory=RenderOutputTargets)
    metadata: dict[str, Any] = Field(default_factory=dict)
    render_variant: RenderVariant | None = Field(default=None, description='默认预览变体')
    layout_params: dict[str, Any] = Field(default_factory=dict)


class RenderTemplatePresetCreate(BaseModel):
    template_key: str = Field(..., min_length=1, max_length=100)
    preset_name: str = Field(..., min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool = True
    is_default: bool = False
    sort_order: int = 0
    payload: RenderTemplatePresetPayload = Field(default_factory=RenderTemplatePresetPayload)
    remark: str | None = Field(default=None)


class RenderTemplatePresetUpdate(BaseModel):
    preset_name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    is_default: bool | None = None
    sort_order: int | None = None
    payload: RenderTemplatePresetPayload | None = None
    remark: str | None = None


class RenderJobValidationResult(BaseModel):
    valid: bool
    normalized_title: str
    template: RenderTemplateSummary | None = None
    issues: list[RenderValidationIssue] = Field(default_factory=list)


class RenderJobFileRead(BaseModel):
    file_kind: RenderFileKind
    render_variant: RenderVariant | None = None
    storage_type: RenderStorageType = 'local'
    status: RenderFileStatus = 'available'
    filename: str
    content_type: str = 'application/pdf'
    size_bytes: int | None = None
    local_path: str | None = None
    object_key: str | None = None
    url: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class RenderJobRead(BaseModel):
    job_id: str
    status: JobStatus
    mode: JobMode
    template_key: str
    template_version: str = '1.0.0'
    template_digest: str = ''
    title: str
    subtitle: str | None = None
    subject: str | None = None
    book_kind: BookKind | None = None
    content_mode: RenderContentMode | None = None
    answer_layout: RenderAnswerLayout | None = None
    delivery_mode: RenderDeliveryMode | None = None
    solution_mode: SolutionMode | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    options: RenderOptions
    output_targets: RenderOutputTargets = Field(default_factory=RenderOutputTargets)
    render_variants: list[RenderVariant] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    payload_path: str | None = None
    question_count: int | None = None
    material_count: int | None = None
    output_path: str | None = None
    error_message: str | None = None
    files: list[RenderJobFileRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class RenderJobListParams(_CustomPageParams):
    job_id: str | None = Field(default=None, description='任务 ID')
    status: JobStatus | None = Field(default=None, description='任务状态')
    template_key: str | None = Field(default=None, description='模板键')
    mode: JobMode | None = Field(default=None, description='任务模式')
    user_id: int | None = Field(default=None, ge=1, description='用户 ID')
    keyword: str | None = Field(default=None, description='标题/副标题/任务 ID 模糊查询')
    cat_id: int | None = Field(default=None, ge=1, description='题库目录分类 ID')
    kp_cat_id: int | None = Field(default=None, ge=1, description='知识点分类 ID')


class RenderTemplatePreviewResponse(BaseModel):
    job: RenderJobRead
    render_variant: RenderVariant
    pdf_url: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    resolved_metadata: dict[str, Any] = Field(default_factory=dict)


class RenderTemplatePresetRead(BaseModel):
    id: int
    template_key: str
    preset_name: str
    description: str | None = None
    is_active: bool = True
    is_default: bool = False
    sort_order: int = 0
    payload: RenderTemplatePresetPayload = Field(default_factory=RenderTemplatePresetPayload)
    remark: str | None = None
    created_at: datetime
    updated_at: datetime
