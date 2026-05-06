#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.plugin.ocr.schema.ocr import OCRDocumentOutputFormat, OCRRecognizeScene


@dataclass
class OCRImagePayload:
    """OCR 图片载荷"""

    filename: str
    content: bytes
    content_type: str


@dataclass
class OCRRecognizeContext:
    """OCR 识别上下文"""

    images: list[OCRImagePayload]
    scene: OCRRecognizeScene


@dataclass
class OCRRecognizeResultData:
    """OCR 识别结果数据"""

    provider: str
    text: str
    lines: list[str]
    elapsed_ms: int
    raw_response: dict[str, Any] | None = None


@dataclass
class OCRDocumentPayload:
    """OCR 文档载荷"""

    filename: str
    content: bytes
    content_type: str


@dataclass
class OCRDocumentParseContext:
    """OCR 文档解析上下文"""

    document: OCRDocumentPayload
    output_format: OCRDocumentOutputFormat = 'markdown'
    images_dir_name: str = 'document'
    wait: bool = True
    download_images: bool | None = None


@dataclass
class OCRDocumentRecoverContext:
    """OCR 文档恢复上下文"""

    job_id: str
    output_format: OCRDocumentOutputFormat = 'markdown'
    images_dir_name: str = 'document'
    download_images: bool | None = None


@dataclass
class OCRDocumentParseResultData:
    """OCR 文档解析结果数据"""

    provider: str
    output_format: OCRDocumentOutputFormat
    content: str
    status: str
    elapsed_ms: int
    job_id: str | None = None
    text_content: str | None = None
    raw_response: dict[str, Any] | None = None


class OCRProvider(Protocol):
    """OCR provider 协议"""

    async def recognize(self, context: OCRRecognizeContext) -> OCRRecognizeResultData:
        """
        执行 OCR 识别

        :param context: 识别上下文
        :return:
        """
        ...


class OCRDocumentProvider(Protocol):
    """OCR 文档 provider 协议"""

    async def parse_document(self, context: OCRDocumentParseContext) -> OCRDocumentParseResultData:
        """
        执行文档解析

        :param context: 文档解析上下文
        :return:
        """
        ...

    async def recover_document(self, context: OCRDocumentRecoverContext) -> OCRDocumentParseResultData:
        """
        恢复云端文档解析结果

        :param context: 文档恢复上下文
        :return:
        """
        ...
