#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import UploadFile

from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.ocr.schema.ocr import OCRRecognizeScene
from backend.plugin.ocr.service.providers.baidu_provider import BaiduOCRProvider
from backend.plugin.ocr.service.providers.base import OCRImagePayload, OCRProvider, OCRRecognizeContext, OCRRecognizeResultData
from backend.utils.file_ops import upload_file_verify


class OCRService:
    """OCR 服务"""

    def __init__(self) -> None:
        baidu_provider = BaiduOCRProvider()
        self.provider_mapping: dict[str, OCRProvider] = {
            'baidu': baidu_provider,
        }

    @staticmethod
    def _normalize_provider(provider: str | None) -> str:
        """
        规范化 provider 名称

        :param provider: provider 名称
        :return:
        """
        normalized = str(provider or '').strip().lower()
        if normalized:
            return normalized
        return str(settings.OCR_PROVIDER).strip().lower() or 'baidu'

    @staticmethod
    def _resolve_max_count() -> int:
        """获取最大图片数"""
        try:
            value = int(settings.OCR_IMAGE_MAX_COUNT)
        except Exception:
            value = 3
        if value <= 0:
            return 3
        return value

    @staticmethod
    def _guess_content_type(file: UploadFile) -> str:
        """
        推断图片 MIME 类型

        :param file: 上传文件
        :return:
        """
        content_type = str(file.content_type or '').strip()
        if content_type.startswith('image/'):
            return content_type

        filename = str(file.filename or '').lower()
        if filename.endswith('.png'):
            return 'image/png'
        if filename.endswith('.webp'):
            return 'image/webp'
        if filename.endswith('.gif'):
            return 'image/gif'
        return 'image/jpeg'

    def _get_provider(self, provider: str | None = None) -> OCRProvider:
        """
        获取 OCR provider

        :param provider: provider 名称
        :return:
        """
        provider_name = self._normalize_provider(provider)
        provider_instance = self.provider_mapping.get(provider_name)
        if provider_instance is None:
            raise errors.RequestError(msg=f'不支持的 OCR provider：{provider_name}')
        return provider_instance

    async def _build_image_payloads(self, files: list[UploadFile]) -> list[OCRImagePayload]:
        """
        构建 OCR 图片载荷

        :param files: 上传文件
        :return:
        """
        payloads: list[OCRImagePayload] = []
        for file in files:
            upload_file_verify(file)
            content = await file.read()
            if not content:
                continue

            payloads.append(
                OCRImagePayload(
                    filename=str(file.filename or 'image.jpg'),
                    content=content,
                    content_type=self._guess_content_type(file),
                )
            )

        return payloads

    async def recognize_upload_files(
        self,
        *,
        files: list[UploadFile],
        scene: OCRRecognizeScene = 'general',
        provider: str | None = None,
    ) -> OCRRecognizeResultData:
        """
        识别上传图片

        :param files: 上传文件
        :param scene: 识别场景
        :param provider: provider 名称
        :return:
        """
        if not files:
            raise errors.RequestError(msg='请至少上传 1 张图片')
        if len(files) > self._resolve_max_count():
            raise errors.RequestError(msg=f'最多上传 {self._resolve_max_count()} 张图片')

        image_payloads = await self._build_image_payloads(files)
        if not image_payloads:
            raise errors.RequestError(msg='上传图片为空，请重新选择')

        provider_instance = self._get_provider(provider)
        return await provider_instance.recognize(
            OCRRecognizeContext(
                images=image_payloads,
                scene=scene,
            )
        )


ocr_service = OCRService()
