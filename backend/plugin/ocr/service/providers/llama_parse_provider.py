#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.core.path_conf import UPLOAD_DIR
from backend.plugin.ocr.schema.ocr import OCRDocumentOutputFormat
from backend.plugin.ocr.service.providers.base import (
    OCRDocumentParseContext,
    OCRDocumentParseResultData,
    OCRDocumentPayload,
    OCRDocumentRecoverContext,
    OCRRecognizeContext,
    OCRRecognizeResultData,
)
from backend.utils.path_safety import safe_path_segment


class LlamaParseOCRProvider:
    """LlamaParse OCR provider"""

    _FILES_URL = 'https://api.cloud.llamaindex.ai/api/v1/beta/files'
    _PARSE_URL = 'https://api.cloud.llamaindex.ai/api/v2/parse'

    @staticmethod
    def _headers() -> dict[str, str]:
        """构建 LlamaParse 请求头"""
        api_key = str(settings.OCR_LLAMA_CLOUD_API_KEY or settings.LLAMA_CLOUD_API_KEY or '').strip()
        if not api_key:
            raise errors.RequestError(msg='OCR_LLAMA_CLOUD_API_KEY 未配置，无法调用 LlamaParse')

        return {'Authorization': f'Bearer {api_key}', 'accept': 'application/json'}

    @staticmethod
    def _timeout() -> httpx.Timeout:
        """构建 HTTP 超时配置"""
        connect_timeout = float(settings.OCR_LLAMA_CONNECT_TIMEOUT)
        read_timeout = float(settings.OCR_LLAMA_READ_TIMEOUT)
        write_timeout = float(settings.OCR_LLAMA_WRITE_TIMEOUT)
        pool_timeout = float(settings.OCR_LLAMA_POOL_TIMEOUT)
        return httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )

    @staticmethod
    def _retry_count() -> int:
        """获取请求重试次数"""
        value = int(settings.OCR_LLAMA_REQUEST_RETRY_COUNT)
        if value <= 0:
            return 3
        return value

    @staticmethod
    def _retry_delay_seconds() -> int:
        """获取请求重试延迟"""
        value = int(settings.OCR_LLAMA_REQUEST_RETRY_DELAY_SECONDS)
        if value <= 0:
            return 5
        return value

    @staticmethod
    def _poll_interval_seconds() -> int:
        """获取轮询间隔"""
        value = int(settings.OCR_LLAMA_POLL_INTERVAL_SECONDS)
        if value <= 0:
            return 60
        return value

    @staticmethod
    def _max_poll_attempts() -> int:
        """获取最大轮询次数"""
        value = int(settings.OCR_LLAMA_MAX_POLL_ATTEMPTS)
        if value <= 0:
            return 30
        return value

    @staticmethod
    def _save_images_enabled() -> bool:
        """是否让 LlamaParse 保存文档图片"""
        return bool(settings.OCR_LLAMA_SAVE_IMAGES)

    @staticmethod
    def _download_images_enabled(download_images: bool | None = None) -> bool:
        """
        是否下载 LlamaParse 文档图片到本地

        :param download_images: 单次调用覆盖值
        :return:
        """
        if download_images is not None:
            return download_images
        return bool(settings.OCR_LLAMA_DOWNLOAD_IMAGES)

    @staticmethod
    def _inline_images_enabled() -> bool:
        """是否在 Markdown 中内联图片引用"""
        return bool(settings.OCR_LLAMA_INLINE_IMAGES)

    @staticmethod
    def _split_config_values(value: Any, default: list[str]) -> list[str]:
        """
        拆分逗号配置

        :param value: 配置值
        :param default: 默认值
        :return:
        """
        if isinstance(value, list):
            values = [str(item).strip() for item in value if str(item).strip()]
            if values:
                return values
            return default

        value_text = str(value or '').strip()
        if not value_text:
            return default

        values = [item.strip() for item in value_text.split(',') if item.strip()]
        if values:
            return values
        return default

    @classmethod
    def _languages(cls) -> list[str]:
        """获取 OCR 语言列表"""
        return cls._split_config_values(settings.OCR_LLAMA_LANGUAGES, ['ch_sim', 'en'])

    @classmethod
    def _images_to_save(cls) -> list[str]:
        """获取云端保存图片类型"""
        return cls._split_config_values(settings.OCR_LLAMA_IMAGES_TO_SAVE, ['embedded'])

    @classmethod
    def _default_expand_fields(cls) -> list[str]:
        """获取默认展开字段"""
        return cls._split_config_values(settings.OCR_LLAMA_EXPAND, ['markdown_full', 'text_full'])

    async def _request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        *,
        retry_count: int | None = None,
        **kwargs,
    ) -> httpx.Response:
        """
        带重试调用 LlamaParse HTTP 接口

        :param client: HTTP 客户端
        :param method: 请求方法
        :param url: 请求地址
        :param retry_count: 重试次数
        :return:
        """
        last_error: Exception | None = None
        max_retry_count = retry_count or self._retry_count()
        for attempt in range(1, max_retry_count + 1):
            try:
                response = await client.request(method, url, **kwargs)
                if response.status_code >= 500 and attempt < max_retry_count:
                    log.warning(
                        f'LlamaParse 接口 {method} {url} 返回 {response.status_code}，准备第 {attempt + 1} 次重试'
                    )
                    await asyncio.sleep(self._retry_delay_seconds() * attempt)
                    continue
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError:
                raise
            except httpx.RequestError as exc:
                last_error = exc
                if attempt >= max_retry_count:
                    break
                log.warning(
                    f'LlamaParse 接口 {method} {url} 网络异常 {exc.__class__.__name__}，准备第 {attempt + 1} 次重试'
                )
                await asyncio.sleep(self._retry_delay_seconds() * attempt)

        raise RuntimeError(f'LlamaParse 网络连接失败：{last_error.__class__.__name__ if last_error else "未知错误"}')

    @staticmethod
    def _parse_payload(file_id: str) -> dict[str, Any]:
        """
        构建解析请求载荷

        :param file_id: LlamaParse 文件 ID
        :return:
        """
        output_options: dict[str, Any] = {
            'markdown': {
                'annotate_links': True,
                'inline_images': LlamaParseOCRProvider._inline_images_enabled(),
                'tables': {
                    'output_tables_as_markdown': bool(settings.OCR_LLAMA_TABLES_AS_MARKDOWN),
                    'merge_continued_tables': bool(settings.OCR_LLAMA_MERGE_CONTINUED_TABLES),
                },
            },
        }
        if LlamaParseOCRProvider._save_images_enabled():
            output_options['images_to_save'] = LlamaParseOCRProvider._images_to_save()

        custom_prompt = str(settings.OCR_LLAMA_CUSTOM_PROMPT or '').strip()
        if not custom_prompt:
            custom_prompt = (
                '你是一个专业的文档 OCR 和结构化解析助手。'
                '请完整保留公式、题目描述、选项内容、图片和表格位置。'
                '遇到复杂表格时优先保留为图片或稳定的版式内容。'
            )

        return {
            'file_id': file_id,
            'tier': str(settings.OCR_LLAMA_TIER or 'agentic'),
            'version': str(settings.OCR_LLAMA_VERSION or 'latest'),
            'agentic_options': {
                'custom_prompt': custom_prompt,
            },
            'output_options': output_options,
            'processing_options': {
                'ignore': {
                    'ignore_diagonal_text': bool(settings.OCR_LLAMA_IGNORE_DIAGONAL_TEXT),
                    'ignore_text_in_image': bool(settings.OCR_LLAMA_IGNORE_TEXT_IN_IMAGE),
                    'ignore_hidden_text': bool(settings.OCR_LLAMA_IGNORE_HIDDEN_TEXT),
                },
                'cost_optimizer': {'enable': bool(settings.OCR_LLAMA_COST_OPTIMIZER_ENABLED)},
                'ocr_parameters': {
                    'languages': LlamaParseOCRProvider._languages(),
                },
            },
        }

    async def _upload_document(self, client: httpx.AsyncClient, document: OCRDocumentPayload) -> str:
        """
        上传文档并返回文件 ID

        :param client: HTTP 客户端
        :param document: 文档载荷
        :return:
        """
        files = {
            'file': (
                document.filename,
                document.content,
                document.content_type or 'application/octet-stream',
            )
        }
        upload_res = await self._request(
            client,
            'POST',
            self._FILES_URL,
            headers=self._headers(),
            files=files,
            data={'purpose': 'parse'},
        )
        file_id = str(upload_res.json().get('id') or '').strip()
        if not file_id:
            raise errors.GatewayError(msg='LlamaParse 上传成功但未返回 FileID')
        log.info(f'文件上传成功，FileID: {file_id}')
        return file_id

    async def _submit_parse_job(self, client: httpx.AsyncClient, file_id: str) -> str:
        """
        提交解析任务

        :param client: HTTP 客户端
        :param file_id: LlamaParse 文件 ID
        :return:
        """
        job_res = await self._request(
            client,
            'POST',
            self._PARSE_URL,
            headers=self._headers(),
            json=self._parse_payload(file_id),
        )
        if job_res.status_code == 422:
            log.error(f'LlamaParse 提交解析失败 (422): {job_res.text}')
        job_id = str(job_res.json().get('id') or '').strip()
        if not job_id:
            raise errors.GatewayError(msg='LlamaParse 未返回 JobID')
        log.info(f'文档已提交，正在云端进行解析，JobID: {job_id}')
        return job_id

    async def _get_job_status(self, client: httpx.AsyncClient, job_id: str) -> tuple[str | None, dict[str, Any]]:
        """
        获取任务状态

        :param client: HTTP 客户端
        :param job_id: LlamaParse 任务 ID
        :return:
        """
        status_res = await self._request(
            client,
            'GET',
            f'{self._PARSE_URL}/{job_id}',
            headers=self._headers(),
        )
        status_data = status_res.json()
        return status_data.get('job', {}).get('status'), status_data

    @staticmethod
    def _extract_content(payload: dict[str, Any], output_format: OCRDocumentOutputFormat) -> str:
        """
        从 LlamaParse 响应抽取内容

        :param payload: LlamaParse 响应
        :param output_format: 输出格式
        :return:
        """
        if output_format == 'text':
            return LlamaParseOCRProvider._extract_text_content(payload)

        md_content = payload.get('markdown_full')
        if isinstance(md_content, str) and md_content.strip():
            return md_content

        md_data = payload.get('markdown')
        if isinstance(md_data, dict):
            pages = md_data.get('pages', [])
            if isinstance(pages, list):
                return '\n\n'.join([
                    str(page.get('markdown') or '').strip()
                    for page in pages
                    if isinstance(page, dict) and str(page.get('markdown') or '').strip()
                ])

        return ''

    @staticmethod
    def _extract_text_content(payload: dict[str, Any]) -> str:
        """
        从 LlamaParse 响应抽取纯文本

        :param payload: LlamaParse 响应
        :return:
        """
        text_content = payload.get('text_full')
        if isinstance(text_content, str) and text_content.strip():
            return text_content

        text_data = payload.get('text')
        if isinstance(text_data, str) and text_data.strip():
            return text_data
        if isinstance(text_data, dict):
            pages = text_data.get('pages', [])
            if isinstance(pages, list):
                page_text = '\n\n'.join([
                    str(page.get('text') or '').strip()
                    for page in pages
                    if isinstance(page, dict) and str(page.get('text') or '').strip()
                ])
                if page_text:
                    return page_text

        return ''

    async def _fetch_completed_content(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        output_format: OCRDocumentOutputFormat,
        images_dir_name: str,
        download_images: bool | None,
    ) -> tuple[str, dict[str, Any]]:
        """
        拉取已完成任务内容

        :param client: HTTP 客户端
        :param job_id: LlamaParse 任务 ID
        :param output_format: 输出格式
        :param images_dir_name: 图片保存目录名
        :param download_images: 是否下载图片到本地
        :return:
        """
        expand_fields = self._build_expand_fields(output_format, download_images)
        params = {'expand': ','.join(expand_fields)}
        full_res = await self._request(
            client,
            'GET',
            f'{self._PARSE_URL}/{job_id}',
            headers=self._headers(),
            params=params,
        )
        status_data = full_res.json()
        content = self._extract_content(status_data, output_format)

        if not content:
            params_list = [('expand', expand_field) for expand_field in expand_fields]
            full_res = await self._request(
                client,
                'GET',
                f'{self._PARSE_URL}/{job_id}',
                headers=self._headers(),
                params=params_list,
            )
            status_data = full_res.json()
            content = self._extract_content(status_data, output_format)

        if not content:
            raise errors.GatewayError(msg=f'云端已完成解析，但未返回 {output_format} 内容')

        if output_format == 'markdown' and self._download_images_enabled(download_images):
            content = await self._download_images(client, status_data, content, images_dir_name)

        return content, status_data

    def _build_expand_fields(
        self,
        output_format: OCRDocumentOutputFormat,
        download_images: bool | None,
    ) -> list[str]:
        """
        构建完成结果展开字段

        :param output_format: 输出格式
        :param download_images: 是否下载图片到本地
        :return:
        """
        if output_format == 'text':
            return ['text_full', 'text']

        expand_fields = self._default_expand_fields()
        if not any(field in {'markdown', 'markdown_full'} for field in expand_fields):
            expand_fields.insert(0, 'markdown_full')
        if self._download_images_enabled(download_images):
            expand_fields.append('images_content_metadata')
        return list(dict.fromkeys(expand_fields))

    async def _download_images(
        self,
        client: httpx.AsyncClient,
        status_data: dict[str, Any],
        md_content: str,
        images_dir_name: str,
    ) -> str:
        """
        下载 Markdown 中的图片

        :param client: HTTP 客户端
        :param status_data: LlamaParse 响应
        :param md_content: Markdown 内容
        :param images_dir_name: 图片保存目录
        :return:
        """
        safe_images_dir_name = safe_path_segment(images_dir_name, default='document')
        images_dir = UPLOAD_DIR / 'parsed_images' / safe_images_dir_name
        images_dir.mkdir(parents=True, exist_ok=True)

        images_metadata = status_data.get('images_content_metadata', {}).get('images', [])
        image_name_map: dict[str, str] = {}
        used_img_names: set[str] = set()
        if not images_metadata:
            log.info('该文档未检测到图片。')
        if isinstance(images_metadata, list) and images_metadata:
            log.info(f'探测到 {len(images_metadata)} 张图片，开始下载...')
            for img_info in images_metadata:
                if not isinstance(img_info, dict):
                    continue

                img_name = img_info.get('filename')
                presigned_url = img_info.get('presigned_url')
                if not img_name or not presigned_url:
                    continue

                try:
                    img_res = await self._request(client, 'GET', str(presigned_url), retry_count=2)
                    safe_img_name = safe_path_segment(Path(str(img_name)).name, default='image')
                    safe_img_path = Path(safe_img_name)
                    img_name_index = 1
                    while safe_img_name in used_img_names:
                        safe_img_name = f'{safe_img_path.stem}_{img_name_index}{safe_img_path.suffix}'
                        img_name_index += 1
                    used_img_names.add(safe_img_name)
                    image_name_map[str(img_name)] = safe_img_name
                    await asyncio.to_thread((images_dir / safe_img_name).write_bytes, img_res.content)
                except Exception as exc:
                    log.warning(f'下载图片 {img_name} 失败: {exc!s}')

        for raw_img_name, safe_img_name in image_name_map.items():
            if raw_img_name != safe_img_name:
                md_content = md_content.replace(raw_img_name, safe_img_name)

        md_file_path = images_dir / f'{safe_images_dir_name}.md'
        await asyncio.to_thread(md_file_path.write_text, md_content, encoding='utf-8')
        return md_content

    async def parse_document(self, context: OCRDocumentParseContext) -> OCRDocumentParseResultData:
        """
        执行 LlamaParse 文档解析

        :param context: 文档解析上下文
        :return:
        """
        started_at = perf_counter()
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            try:
                file_id = await self._upload_document(client, context.document)
                job_id = await self._submit_parse_job(client, file_id)
                if not context.wait:
                    return OCRDocumentParseResultData(
                        provider='llama_parse',
                        output_format=context.output_format,
                        content='',
                        status='SUBMITTED',
                        elapsed_ms=int((perf_counter() - started_at) * 1000),
                        job_id=job_id,
                    )

                result = await self._wait_and_fetch(
                    client=client,
                    job_id=job_id,
                    output_format=context.output_format,
                    images_dir_name=context.images_dir_name,
                    download_images=context.download_images,
                    started_at=started_at,
                )
                return result
            except httpx.HTTPStatusError as exc:
                response_text = exc.response.text[:500] if exc.response is not None else ''
                status_code = exc.response.status_code if exc.response is not None else 'unknown'
                log.error(f'LlamaParse HTTP 调用失败: status={status_code}, body={response_text}')
                raise errors.GatewayError(msg=f'LlamaParse 返回 HTTP {status_code}')
            except (httpx.RequestError, RuntimeError) as exc:
                log.error(f'LlamaParse 网络调用失败: {exc.__class__.__name__}: {exc!s}')
                raise errors.GatewayError(msg=f'LlamaParse 网络连接异常（{exc.__class__.__name__}）')

    async def _wait_and_fetch(
        self,
        *,
        client: httpx.AsyncClient,
        job_id: str,
        output_format: OCRDocumentOutputFormat,
        images_dir_name: str,
        download_images: bool | None,
        started_at: float,
    ) -> OCRDocumentParseResultData:
        """
        等待云端任务完成并拉取内容

        :param client: HTTP 客户端
        :param job_id: LlamaParse 任务 ID
        :param output_format: 输出格式
        :param images_dir_name: 图片目录名
        :param download_images: 是否下载图片到本地
        :param started_at: 开始时间
        :return:
        """
        status: str | None = None
        for _ in range(self._max_poll_attempts()):
            await asyncio.sleep(self._poll_interval_seconds())
            status, status_data = await self._get_job_status(client, job_id)
            if status == 'COMPLETED':
                content, raw_response = await self._fetch_completed_content(
                    client,
                    job_id,
                    output_format,
                    images_dir_name,
                    download_images,
                )
                return OCRDocumentParseResultData(
                    provider='llama_parse',
                    output_format=output_format,
                    content=content,
                    status='COMPLETED',
                    elapsed_ms=int((perf_counter() - started_at) * 1000),
                    job_id=job_id,
                    text_content=self._extract_text_content(raw_response),
                    raw_response=raw_response,
                )

            if status in {'ERROR', 'FAILED'}:
                log.error(f'LlamaParse 任务失败: {status_data}')
                raise errors.GatewayError(msg=f'云端解析出错: {status_data.get("error_message", "未知错误")}')

        waited_seconds = self._poll_interval_seconds() * self._max_poll_attempts()
        raise errors.GatewayError(msg=f'任务超时未完成，已等待 {waited_seconds} 秒，JobID: {job_id}')

    async def recover_document(self, context: OCRDocumentRecoverContext) -> OCRDocumentParseResultData:
        """
        恢复 LlamaParse 云端文档解析结果

        :param context: 文档恢复上下文
        :return:
        """
        started_at = perf_counter()
        clean_job_id = ''.join([char for char in context.job_id.strip() if char.isalnum() or char in ('_', '-')])
        if not clean_job_id:
            raise errors.RequestError(msg='请输入有效的 LlamaParse JobID')

        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            try:
                status, status_data = await self._get_job_status(client, clean_job_id)
                if status in {'ERROR', 'FAILED'}:
                    log.error(f'LlamaParse 任务失败: {status_data}')
                    raise errors.GatewayError(msg=f'云端解析出错: {status_data.get("error_message", "未知错误")}')

                if status != 'COMPLETED':
                    raise errors.RequestError(msg=f'云端任务尚未完成，当前状态：{status or "未知"}')

                content, raw_response = await self._fetch_completed_content(
                    client,
                    clean_job_id,
                    context.output_format,
                    context.images_dir_name,
                    context.download_images,
                )
                return OCRDocumentParseResultData(
                    provider='llama_parse',
                    output_format=context.output_format,
                    content=content,
                    status='COMPLETED',
                    elapsed_ms=int((perf_counter() - started_at) * 1000),
                    job_id=clean_job_id,
                    text_content=self._extract_text_content(raw_response),
                    raw_response=raw_response,
                )
            except httpx.HTTPStatusError as exc:
                response_text = exc.response.text[:500] if exc.response is not None else ''
                status_code = exc.response.status_code if exc.response is not None else 'unknown'
                log.error(f'LlamaParse HTTP 调用失败: status={status_code}, body={response_text}')
                raise errors.GatewayError(msg=f'LlamaParse 返回 HTTP {status_code}')
            except (httpx.RequestError, RuntimeError) as exc:
                log.error(f'LlamaParse 网络调用失败: {exc.__class__.__name__}: {exc!s}')
                raise errors.GatewayError(msg=f'LlamaParse 网络连接异常（{exc.__class__.__name__}）')

    async def recognize(self, context: OCRRecognizeContext) -> OCRRecognizeResultData:
        """
        执行图片 OCR 识别

        :param context: 识别上下文
        :return:
        """
        started_at = perf_counter()
        all_lines: list[str] = []
        image_texts: list[str] = []
        last_payload: dict[str, Any] | None = None

        for image in context.images:
            parse_result = await self.parse_document(
                OCRDocumentParseContext(
                    document=OCRDocumentPayload(
                        filename=image.filename,
                        content=image.content,
                        content_type=image.content_type,
                    ),
                    output_format='text',
                    images_dir_name=Path(image.filename).stem or 'image',
                    wait=True,
                )
            )
            last_payload = parse_result.raw_response
            text = parse_result.content.strip()
            if not text:
                continue

            image_texts.append(text)
            all_lines.extend([line.strip() for line in text.splitlines() if line.strip()])

        merged_text = '\n'.join(image_texts).strip()
        if not merged_text:
            raise errors.RequestError(msg='图片识别结果为空，请重试或改用手动输入')

        return OCRRecognizeResultData(
            provider='llama_parse',
            text=merged_text,
            lines=all_lines,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
            raw_response=last_payload,
        )
