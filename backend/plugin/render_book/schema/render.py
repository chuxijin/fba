#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

JobMode = Literal['preview', 'final']
JobStatus = Literal['accepted', 'running', 'succeeded', 'failed']
FieldType = Literal['string', 'integer', 'boolean', 'single_select', 'multi_select']
IssueLevel = Literal['error', 'warning']


class RenderOptions(BaseModel):
    include_answer: bool = False
    include_analysis: bool = False
    density: Literal['compact', 'standard', 'loose'] = 'standard'
    theme: Literal['blue', 'green', 'orange', 'purple'] = 'blue'
    show_source: bool = True


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
    name: str
    description: str
    scene: str
    subject: str | None = None
    estimated_latency: Literal['fast', 'medium', 'slow'] = 'medium'


class RenderTemplateDetail(RenderTemplateSummary):
    supported_modes: list[JobMode] = Field(default_factory=lambda: ['preview', 'final'])
    filter_fields: list[RenderFieldSpec] = Field(default_factory=list)
    option_fields: list[RenderFieldSpec] = Field(default_factory=list)
    default_options: RenderOptions = Field(default_factory=RenderOptions)
    notes: list[str] = Field(default_factory=list)


class RenderValidationIssue(BaseModel):
    field: str
    level: IssueLevel
    message: str


class RenderJobCreate(BaseModel):
    template_key: str = Field(..., min_length=1, max_length=100)
    mode: JobMode = 'final'
    title: str = Field(..., min_length=1, max_length=200)
    subtitle: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=100)
    filters: dict[str, Any] = Field(default_factory=dict)
    options: RenderOptions = Field(default_factory=RenderOptions)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RenderJobValidationResult(BaseModel):
    valid: bool
    normalized_title: str
    template: RenderTemplateSummary | None = None
    issues: list[RenderValidationIssue] = Field(default_factory=list)


class RenderJobRead(BaseModel):
    job_id: str
    status: JobStatus
    mode: JobMode
    template_key: str
    title: str
    subtitle: str | None = None
    subject: str | None = None
    filters: dict[str, Any] = Field(default_factory=dict)
    options: RenderOptions
    metadata: dict[str, Any] = Field(default_factory=dict)
    output_path: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
