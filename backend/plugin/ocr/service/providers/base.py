#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from backend.plugin.ocr.schema.ocr import OCRRecognizeScene


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


class OCRProvider(Protocol):
    """OCR provider 协议"""

    async def recognize(self, context: OCRRecognizeContext) -> OCRRecognizeResultData:
        """
        执行 OCR 识别

        :param context: 识别上下文
        :return:
        """
        ...
