#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Literal

from pydantic import Field

from backend.common.schema import SchemaBase

OCRRecognizeScene = Literal['general', 'subjective_answer']
OCRDocumentOutputFormat = Literal['markdown', 'text']


class OCRRecognizeResult(SchemaBase):
    """OCR 识别结果"""

    provider: str = Field(description='OCR provider')
    text: str = Field(description='合并后的识别文本')
    lines: list[str] = Field(default_factory=list, description='逐行识别文本')
    elapsed_ms: int = Field(description='耗时毫秒数')


class OCRDocumentRecoverParam(SchemaBase):
    """文档恢复参数"""

    job_id: str = Field(description='云端任务 ID')
    provider: str | None = Field(default=None, description='OCR provider')
    output_format: OCRDocumentOutputFormat = Field(default='markdown', description='输出格式')
    images_dir_name: str | None = Field(default=None, description='图片保存目录名')
    download_images: bool | None = Field(default=None, description='是否下载图片到本地')


class OCRDocumentParseResult(SchemaBase):
    """文档解析结果"""

    provider: str = Field(description='OCR provider')
    job_id: str | None = Field(default=None, description='云端任务 ID')
    status: str = Field(description='云端任务状态')
    output_format: OCRDocumentOutputFormat = Field(description='输出格式')
    content: str = Field(description='解析内容')
    elapsed_ms: int = Field(description='耗时毫秒数')
