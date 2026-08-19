#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase

SensitiveWordAction = Literal['replace', 'block', 'reject']
SensitiveWordStatus = Literal['active', 'disabled']


class CreateSensitiveWordParam(SchemaBase):
    """创建敏感词参数"""

    word: str = Field(min_length=1, max_length=128, description='敏感词')
    variants: list[str] = Field(default_factory=list, max_length=50, description='变体词库（拼音/谐音/缩写）')
    replacement: str | None = Field(None, min_length=1, max_length=128, description='替换词，如 ZF')
    action: SensitiveWordAction = Field(default='replace', description='replace 替换 / block 打码 / reject 拦截')
    status: SensitiveWordStatus = Field(default='active', description='active/disabled')
    remark: str | None = Field(None, max_length=255, description='备注')
    sort_order: int = Field(default=0, ge=0, description='排序')

    @model_validator(mode='after')
    def validate_replacement(self) -> 'CreateSensitiveWordParam':
        if self.action == 'replace' and not (self.replacement and self.replacement.strip()):
            raise ValueError('替换模式必须提供替换词')
        cleaned = [item.strip() for item in self.variants if item and item.strip()]
        self.variants = list(dict.fromkeys(cleaned))
        if self.word in self.variants:
            raise ValueError('变体词不能与主词重复')
        return self


class UpdateSensitiveWordParam(SchemaBase):
    """更新敏感词参数"""

    word: str | None = Field(None, min_length=1, max_length=128, description='敏感词')
    variants: list[str] | None = Field(None, max_length=50, description='变体词库')
    replacement: str | None = Field(None, min_length=1, max_length=128, description='替换词')
    action: SensitiveWordAction | None = Field(None, description='处理方式')
    status: SensitiveWordStatus | None = Field(None, description='状态')
    remark: str | None = Field(None, max_length=255, description='备注')
    sort_order: int | None = Field(None, ge=0, description='排序')


class GetSensitiveWordDetail(SchemaBase):
    """敏感词详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='敏感词 ID')
    word: str = Field(description='敏感词')
    variants: list[str] = Field(default_factory=list, description='变体词库')
    replacement: str | None = Field(None, description='替换词')
    action: str = Field(description='处理方式')
    status: str = Field(description='状态')
    remark: str | None = Field(None, description='备注')
    sort_order: int = Field(description='排序')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetSensitiveHitLogItem(SchemaBase):
    """敏感词命中日志项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志 ID')
    user_id: int = Field(description='触发者用户 ID')
    word: str = Field(description='敏感词快照')
    keyword: str = Field(description='实际命中的词/变体')
    word_id: int | None = Field(None, description='敏感词 ID')
    action: str = Field(description='处理方式')
    replacement: str | None = Field(None, description='替换词')
    hit_count: int = Field(description='命中次数')
    target_type: str | None = Field(None, description='命中内容类型')
    target_id: int | None = Field(None, description='命中内容 ID')
    snippet: str | None = Field(None, description='命中内容摘要')
    created_time: datetime = Field(description='命中时间')
