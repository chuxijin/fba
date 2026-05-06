#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from fastapi import UploadFile

from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.ocr.schema.ocr import OCRDocumentOutputFormat, OCRRecognizeScene
from backend.plugin.ocr.service.providers.baidu_provider import BaiduOCRProvider
from backend.plugin.ocr.service.providers.base import (
    OCRDocumentParseContext,
    OCRDocumentParseResultData,
    OCRDocumentPayload,
    OCRDocumentProvider,
    OCRDocumentRecoverContext,
    OCRImagePayload,
    OCRProvider,
    OCRRecognizeContext,
    OCRRecognizeResultData,
)
from backend.plugin.ocr.service.providers.llama_parse_provider import LlamaParseOCRProvider
from backend.utils.file_ops import upload_file_verify


class OCRService:
    """OCR 服务"""

    def __init__(self) -> None:
        baidu_provider = BaiduOCRProvider()
        llama_parse_provider = LlamaParseOCRProvider()
        self.provider_mapping: dict[str, OCRProvider] = {
            'baidu': baidu_provider,
            'llama_parse': llama_parse_provider,
        }
        self.document_provider_mapping: dict[str, OCRDocumentProvider] = {
            'llama_parse': llama_parse_provider,
        }

    @staticmethod
    def _normalize_provider_name(provider: str | None, fallback_setting: str, default: str = 'llama_parse') -> str:
        """
        规范化 provider 名称

        :param provider: provider 名称
        :param fallback_setting: 配置项回退值
        :param default: 最终默认值
        :return:
        """
        normalized = str(provider or '').strip().lower()
        if normalized:
            return normalized
        return str(fallback_setting).strip().lower() or default

    def _normalize_provider(self, provider: str | None) -> str:
        """规范化 OCR provider 名称"""
        return self._normalize_provider_name(provider, settings.OCR_PROVIDER)

    def _normalize_document_provider(self, provider: str | None) -> str:
        """规范化文档 provider 名称"""
        return self._normalize_provider_name(provider, settings.OCR_DOCUMENT_PROVIDER)

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
        if filename.endswith('.pdf'):
            return 'application/pdf'
        if filename.endswith('.md'):
            return 'text/markdown'
        if filename.endswith('.docx'):
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        if filename.endswith('.xlsx'):
            return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
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

    def _get_document_provider(self, provider: str | None = None) -> OCRDocumentProvider:
        """
        获取 OCR 文档 provider

        :param provider: provider 名称
        :return:
        """
        provider_name = self._normalize_document_provider(provider)
        provider_instance = self.document_provider_mapping.get(provider_name)
        if provider_instance is None:
            raise errors.RequestError(msg=f'不支持的 OCR 文档 provider：{provider_name}')
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

    async def _build_document_payload(self, file: UploadFile) -> OCRDocumentPayload:
        """
        构建 OCR 文档载荷

        :param file: 上传文件
        :return:
        """
        content = await file.read()
        if not content:
            raise errors.RequestError(msg='上传文件为空，请重新选择')

        return OCRDocumentPayload(
            filename=str(file.filename or 'document'),
            content=content,
            content_type=self._guess_content_type(file),
        )

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

    async def parse_upload_document(
        self,
        *,
        file: UploadFile,
        output_format: OCRDocumentOutputFormat = 'markdown',
        provider: str | None = None,
        images_dir_name: str | None = None,
        wait: bool = True,
        download_images: bool | None = None,
    ) -> OCRDocumentParseResultData:
        """
        解析上传文档

        :param file: 上传文件
        :param output_format: 输出格式
        :param provider: provider 名称
        :param images_dir_name: 图片保存目录名
        :param wait: 是否等待完成
        :param download_images: 是否下载图片到本地
        :return:
        """
        document_payload = await self._build_document_payload(file)
        provider_instance = self._get_document_provider(provider)
        return await provider_instance.parse_document(
            OCRDocumentParseContext(
                document=document_payload,
                output_format=output_format,
                images_dir_name=images_dir_name or document_payload.filename.rsplit('.', 1)[0],
                wait=wait,
                download_images=download_images,
            )
        )

    async def parse_document_bytes(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str,
        output_format: OCRDocumentOutputFormat = 'markdown',
        provider: str | None = None,
        images_dir_name: str | None = None,
        wait: bool = True,
        download_images: bool | None = None,
    ) -> OCRDocumentParseResultData:
        """
        解析文档二进制内容

        :param filename: 文件名
        :param content: 文件内容
        :param content_type: 文件 MIME 类型
        :param output_format: 输出格式
        :param provider: provider 名称
        :param images_dir_name: 图片保存目录名
        :param wait: 是否等待完成
        :param download_images: 是否下载图片到本地
        :return:
        """
        if not content:
            raise errors.RequestError(msg='文档内容为空')

        provider_instance = self._get_document_provider(provider)
        return await provider_instance.parse_document(
            OCRDocumentParseContext(
                document=OCRDocumentPayload(
                    filename=filename,
                    content=content,
                    content_type=content_type,
                ),
                output_format=output_format,
                images_dir_name=images_dir_name or filename.rsplit('.', 1)[0],
                wait=wait,
                download_images=download_images,
            )
        )

    async def recover_document(
        self,
        *,
        job_id: str,
        output_format: OCRDocumentOutputFormat = 'markdown',
        provider: str | None = None,
        images_dir_name: str | None = None,
        download_images: bool | None = None,
    ) -> OCRDocumentParseResultData:
        """
        恢复云端文档解析结果

        :param job_id: 云端任务 ID
        :param output_format: 输出格式
        :param provider: provider 名称
        :param images_dir_name: 图片保存目录名
        :param download_images: 是否下载图片到本地
        :return:
        """
        provider_instance = self._get_document_provider(provider)
        return await provider_instance.recover_document(
            OCRDocumentRecoverContext(
                job_id=job_id,
                output_format=output_format,
                images_dir_name=images_dir_name or job_id,
                download_images=download_images,
            )
        )


ocr_service = OCRService()
