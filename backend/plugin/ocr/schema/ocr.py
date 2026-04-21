#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Literal

from pydantic import Field

from backend.common.schema import SchemaBase

OCRRecognizeScene = Literal['general', 'subjective_answer']


class OCRRecognizeResult(SchemaBase):
    """OCR 识别结果"""

    provider: str = Field(description='OCR provider')
    text: str = Field(description='合并后的识别文本')
    lines: list[str] = Field(default_factory=list, description='逐行识别文本')
    elapsed_ms: int = Field(description='耗时毫秒数')
