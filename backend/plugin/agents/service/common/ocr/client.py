#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from backend.common.exception import errors
from backend.plugin.ocr.schema.ocr import OCRRecognizeScene
from backend.plugin.ocr.service.ocr_service import ocr_service
from backend.plugin.ocr.service.providers.base import OCRImagePayload, OCRRecognizeContext


class OCRClient:
    """OCR 客户端, 接受 bytes 输入返回归一化文本"""

    def __init__(self, provider_name: str | None = None) -> None:
        self._provider_name = provider_name

    async def recognize_images(
        self,
        images: list[tuple[bytes, str, str]],
        scene: OCRRecognizeScene = 'subjective_answer',
    ) -> str:
        """
        识别多张图片返回拼接后的归一化文本

        :param images: 图片三元组列表 (content_bytes, filename, content_type)
        :param scene: 识别场景
        :return:
        """
        if not images:
            raise errors.RequestError(msg='OCR 输入图片为空')

        payloads = [
            OCRImagePayload(filename=filename, content=content, content_type=content_type)
            for (content, filename, content_type) in images
            if content
        ]
        if not payloads:
            raise errors.RequestError(msg='OCR 输入图片内容为空')

        provider = ocr_service._get_provider(self._provider_name)
        result = await provider.recognize(
            OCRRecognizeContext(images=payloads, scene=scene),
        )
        return self._normalize_text(result.text)

    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        归一化 OCR 文本, 合并多余空白与连续空行

        :param text: 原始识别文本
        :return:
        """
        if not text:
            return ''
        normalized = re.sub(r'[ \t]+', ' ', text)
        normalized = re.sub(r'\n{3,}', '\n\n', normalized)
        return normalized.strip()
