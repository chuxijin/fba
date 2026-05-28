#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from pydantic import BaseModel, Field


class PromptTemplate(BaseModel):
    """Prompt 模板"""

    version: str = Field(default='1', description='版本号, 用于锁定回归测试基线')
    description: str = Field(default='', description='模板说明')
    system: str = Field(description='系统提示词')
    user: str = Field(description='用户提示词')
    output_schema: dict[str, Any] | None = Field(default=None, description='期望输出的 JSON Schema')
