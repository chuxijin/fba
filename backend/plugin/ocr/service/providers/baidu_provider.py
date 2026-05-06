#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import base64

from time import perf_counter
from urllib.parse import urlencode

import httpx

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.ocr.service.providers.base import OCRRecognizeContext, OCRRecognizeResultData


class BaiduOCRProvider:
    """百度 OCR provider"""

    _TOKEN_URL = 'https://aip.baidubce.com/oauth/2.0/token'

    @staticmethod
    def _cache_key() -> str:
        """获取 token 缓存键"""
        return f'{settings.OCR_TOKEN_REDIS_PREFIX}:baidu'

    @staticmethod
    def _build_headers() -> dict[str, str]:
        """构建请求头"""
        return {'Content-Type': 'application/x-www-form-urlencoded'}

    @staticmethod
    def _normalize_lines(payload: dict) -> list[str]:
        """
        解析百度 OCR 行结果

        :param payload: 百度返回数据
        :return:
        """
        words_result = payload.get('words_result')
        if not isinstance(words_result, list):
            return []

        lines: list[str] = []
        for item in words_result:
            if not isinstance(item, dict):
                continue
            text = str(item.get('words') or '').strip()
            if text:
                lines.append(text)
        return lines

    @staticmethod
    def _merge_text(image_texts: list[str]) -> str:
        """
        合并多张图文本

        :param image_texts: 单图文本列表
        :return:
        """
        normalized = [text.strip() for text in image_texts if text and text.strip()]
        return '\n'.join(normalized).strip()

    @staticmethod
    def _build_body(image_bytes: bytes) -> str:
        """
        构建百度 OCR 请求体

        :param image_bytes: 图片二进制
        :return:
        """
        encoded = base64.b64encode(image_bytes).decode('utf-8')
        return urlencode({'image': encoded})

    async def _get_access_token(self) -> str:
        """获取百度 access token"""
        cache_key = self._cache_key()
        try:
            cached = await redis_client.get(cache_key)
            if cached:
                return str(cached)
        except Exception as exc:
            log.warning(f'读取百度 OCR token 缓存失败，将直接请求新 token: {exc!s}')

        api_key = str(settings.BAIDU_OCR_API_KEY).strip()
        secret_key = str(settings.BAIDU_OCR_SECRET_KEY).strip()
        if not api_key or not secret_key:
            raise errors.RequestError(msg='百度 OCR 配置不完整，请检查环境变量')

        params = {
            'grant_type': 'client_credentials',
            'client_id': api_key,
            'client_secret': secret_key,
        }

        timeout = httpx.Timeout(timeout=float(settings.OCR_REQUEST_TIMEOUT))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(self._TOKEN_URL, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            log.error(f'百度 OCR token 请求失败: {exc!s}')
            raise errors.GatewayError(msg='百度 OCR 鉴权失败，请稍后重试')

        try:
            payload = response.json()
        except Exception as exc:
            log.error(f'百度 OCR token 返回非 JSON: {exc!s}')
            raise errors.GatewayError(msg='百度 OCR 鉴权失败，请稍后重试')

        token = str(payload.get('access_token') or '').strip()
        expires_in = int(payload.get('expires_in') or 0)
        if not token:
            log.error(f'百度 OCR token 获取失败: {payload}')
            raise errors.GatewayError(msg='百度 OCR 鉴权失败，请稍后重试')

        cache_seconds = max(expires_in - 120, 60) if expires_in > 0 else 60 * 25
        try:
            await redis_client.setex(cache_key, cache_seconds, token)
        except Exception as exc:
            log.warning(f'写入百度 OCR token 缓存失败: {exc!s}')

        return token

    async def _request_ocr(self, *, url: str, image_bytes: bytes, allow_retry: bool = True) -> dict:
        """
        调用百度 OCR 接口

        :param url: 接口地址
        :param image_bytes: 图片二进制
        :param allow_retry: 是否允许重试
        :return:
        """
        token = await self._get_access_token()
        timeout = httpx.Timeout(timeout=float(settings.OCR_REQUEST_TIMEOUT))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f'{url}?access_token={token}',
                    content=self._build_body(image_bytes),
                    headers=self._build_headers(),
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            log.error(f'百度 OCR HTTP 请求失败: {exc!s}')
            raise errors.GatewayError(msg='百度 OCR 服务暂时不可用，请稍后重试')

        try:
            payload = response.json()
        except Exception as exc:
            log.error(f'百度 OCR 返回非 JSON: {exc!s}')
            raise errors.GatewayError(msg='百度 OCR 服务暂时不可用，请稍后重试')

        error_code = payload.get('error_code')
        if error_code:
            error_msg = str(payload.get('error_msg') or '未知错误')
            if int(error_code) in {110, 111} and allow_retry:
                try:
                    await redis_client.delete(self._cache_key())
                except Exception:
                    pass
                return await self._request_ocr(url=url, image_bytes=image_bytes, allow_retry=False)
            log.error(f'百度 OCR 请求失败 error_code={error_code}, error_msg={error_msg}')
            raise errors.GatewayError(msg=f'百度 OCR 识别失败：{error_msg}')

        return payload

    async def _recognize_single_image(self, *, image_bytes: bytes, scene: str) -> tuple[list[str], dict]:
        """
        识别单张图片

        :param image_bytes: 图片二进制
        :param scene: 识别场景
        :return:
        """
        if scene == 'subjective_answer':
            payload = await self._request_ocr(url=str(settings.BAIDU_OCR_HANDWRITING_URL), image_bytes=image_bytes)
            lines = self._normalize_lines(payload)
            if lines or not settings.BAIDU_OCR_SUBJECTIVE_FALLBACK_ENABLED:
                return lines, payload

            fallback_payload = await self._request_ocr(
                url=str(settings.BAIDU_OCR_ACCURATE_BASIC_URL),
                image_bytes=image_bytes,
            )
            return self._normalize_lines(fallback_payload), fallback_payload

        payload = await self._request_ocr(url=str(settings.BAIDU_OCR_GENERAL_BASIC_URL), image_bytes=image_bytes)
        return self._normalize_lines(payload), payload

    async def recognize(self, context: OCRRecognizeContext) -> OCRRecognizeResultData:
        """
        执行百度 OCR 识别

        :param context: 识别上下文
        :return:
        """
        started_at = perf_counter()
        all_lines: list[str] = []
        image_texts: list[str] = []
        last_payload: dict | None = None

        for image in context.images:
            lines, payload = await self._recognize_single_image(
                image_bytes=image.content,
                scene=context.scene,
            )
            last_payload = payload
            if not lines:
                continue

            all_lines.extend(lines)
            image_text = '\n'.join(lines).strip()
            if image_text:
                image_texts.append(image_text)

        merged_text = self._merge_text(image_texts)
        if not merged_text:
            raise errors.RequestError(msg='图片识别结果为空，请重试或改用手动输入')

        return OCRRecognizeResultData(
            provider='baidu',
            text=merged_text,
            lines=all_lines,
            elapsed_ms=int((perf_counter() - started_at) * 1000),
            raw_response=last_payload,
        )
