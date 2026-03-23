#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.plugin.oss.service.providers.aliyun_provider import AliyunOssProvider
from backend.plugin.oss.service.providers.base import ProviderUploadContext, StorageProvider
from backend.plugin.oss.service.providers.qiniu_provider import QiniuKodoProvider
from backend.utils.dynamic_config import load_storage_config
from backend.utils.file_ops import build_filename


@dataclass
class StorageRuntimeConfig:
    """存储运行配置"""

    provider: str
    key_prefix: str
    use_signed_url: bool
    signed_url_expire_seconds: int
    object_expire_days: int | None


class StorageService:
    """云存储服务"""

    def __init__(self) -> None:
        aliyun_provider = AliyunOssProvider()
        qiniu_provider = QiniuKodoProvider()
        self.provider_mapping: dict[str, StorageProvider] = {
            'aliyun_oss': aliyun_provider,
            'oss': aliyun_provider,
            'aliyun': aliyun_provider,
            'qiniu_kodo': qiniu_provider,
            'qiniu': qiniu_provider,
            'kodo': qiniu_provider,
        }

    @staticmethod
    def _to_bool(value: str | bool | None, default: bool) -> bool:
        """
        Parse bool value from sys config or settings.

        :param value: source value
        :param default: default bool
        :return:
        """
        if value is None:
            return default
        if isinstance(value, bool):
            return value

        text = str(value).strip().lower()
        if text in {'1', 'true', 'yes', 'y', 'on'}:
            return True
        if text in {'0', 'false', 'no', 'n', 'off'}:
            return False
        return default

    @staticmethod
    def _safe_int(value: str | int | None, default: int) -> int:
        """
        Parse int value safely.

        :param value: source value
        :param default: default int
        :return:
        """
        try:
            return int(value) if value is not None else default
        except Exception:
            return default

    @staticmethod
    def _normalize_path(path: str | None) -> str:
        """
        Normalize object path and reject parent traversal.

        :param path: source path
        :return:
        """
        if not path:
            return ''

        normalized = path.replace('\\', '/').strip('/')
        if not normalized:
            return ''

        segments: list[str] = []
        for part in normalized.split('/'):
            segment = part.strip()
            if not segment or segment == '.':
                continue
            if segment == '..':
                raise errors.RequestError(msg='上传路径不合法')
            segments.append(segment)
        return '/'.join(segments)

    @staticmethod
    def _normalize_filename(filename: str) -> str:
        """
        Normalize filename and strip path separators.

        :param filename: source filename
        :return:
        """
        value = str(filename or '').strip().replace('\\', '/')
        value = value.split('/')[-1].strip()
        if not value:
            raise errors.RequestError(msg='文件名不合法')
        return value

    @staticmethod
    def _resolve_signed_url_expire(value: int | None, default: int) -> int:
        """
        Resolve signed url expire seconds.

        :param value: request override value
        :param default: runtime default value
        :return:
        """
        expire_seconds = default if value is None else int(value)
        if expire_seconds <= 0:
            raise errors.RequestError(msg='URL 过期时间必须大于 0')
        return expire_seconds

    @staticmethod
    def _resolve_object_expire_days(value: int | None, default: int | None) -> int | None:
        """
        Resolve object expire days.

        :param value: request override value
        :param default: runtime default value
        :return:
        """
        if value is None:
            return default

        expire_days = int(value)
        if expire_days <= 0:
            return None
        return expire_days

    @staticmethod
    def _build_object_key(key_prefix: str, upload_path: str, filename: str) -> str:
        """
        Build object key.

        :param key_prefix: configured key prefix
        :param upload_path: request upload path
        :param filename: generated filename
        :return:
        """
        key_parts = [part for part in [key_prefix, upload_path, filename] if part]
        return '/'.join(key_parts)

    def _build_upload_context(
        self,
        cfg: StorageRuntimeConfig,
        file: UploadFile,
        object_key: str,
        use_signed_url: bool | None,
        url_expire_seconds: int | None,
        object_expire_days: int | None,
    ) -> ProviderUploadContext:
        """
        Build upload context.

        :param cfg: runtime config
        :param file: upload file
        :param object_key: object key
        :param use_signed_url: whether force signed url
        :param url_expire_seconds: request url expire seconds
        :param object_expire_days: request object expire days
        :return:
        """
        signed_url_expire = self._resolve_signed_url_expire(url_expire_seconds, cfg.signed_url_expire_seconds)
        effective_object_expire_days = self._resolve_object_expire_days(object_expire_days, cfg.object_expire_days)
        effective_use_signed_url = cfg.use_signed_url if use_signed_url is None else bool(use_signed_url)
        return ProviderUploadContext(
            file=file,
            object_key=object_key,
            use_signed_url=effective_use_signed_url,
            signed_url_expire_seconds=signed_url_expire,
            object_expire_days=effective_object_expire_days,
        )

    @staticmethod
    def _detect_url_type(url: str) -> str:
        """
        Detect whether returned url looks like signed or public.

        :param url: returned object url
        :return:
        """
        if not url:
            return 'unknown'

        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        query_keys = {key.lower() for key in query}
        signed_markers = {
            'e',
            'token',
            'expires',
            'signature',
            'ossaccesskeyid',
            'x-oss-signature',
            'x-oss-credential',
            'x-oss-date',
        }
        if query_keys & signed_markers:
            return 'signed'
        return 'public'

    @staticmethod
    def _safe_url_preview(url: str) -> str:
        """
        Build compact url preview for logs.

        :param url: returned object url
        :return:
        """
        if not url:
            return ''
        parsed = urlparse(url)
        host = parsed.netloc
        path = parsed.path
        return f'{host}{path}'

    async def _load_runtime_config(self, db: AsyncSession) -> StorageRuntimeConfig:
        """
        Load runtime config from plugin defaults and sys_config.

        :param db: db session
        :return:
        """
        try:
            await load_storage_config(db)
        except Exception as exc:
            log.warning(f'加载存储动态配置失败，使用默认配置: {exc!s}')

        provider = str(settings.STORAGE_PROVIDER).strip() or 'aliyun_oss'
        key_prefix = self._normalize_path(settings.STORAGE_KEY_PREFIX)
        use_signed_url = self._to_bool(settings.STORAGE_USE_SIGNED_URL, True)

        signed_url_expire_seconds = self._safe_int(settings.STORAGE_SIGNED_URL_EXPIRE_SECONDS, 300)
        if signed_url_expire_seconds <= 0:
            signed_url_expire_seconds = 300

        object_expire_days_raw = self._safe_int(settings.STORAGE_OBJECT_EXPIRE_DAYS, 0)
        object_expire_days = object_expire_days_raw if object_expire_days_raw > 0 else None

        return StorageRuntimeConfig(
            provider=provider,
            key_prefix=key_prefix,
            use_signed_url=use_signed_url,
            signed_url_expire_seconds=signed_url_expire_seconds,
            object_expire_days=object_expire_days,
        )

    def _resolve_provider(self, provider_name: str) -> StorageProvider:
        """
        Resolve storage provider.

        :param provider_name: configured provider name
        :return:
        """
        provider = self.provider_mapping.get(provider_name.lower())
        if provider:
            return provider
        raise errors.RequestError(msg=f'不支持的云存储 provider: {provider_name}')

    async def upload(
        self,
        db: AsyncSession,
        file: UploadFile,
        path: str | None = None,
        use_signed_url: bool | None = None,
        url_expire_seconds: int | None = None,
        object_expire_days: int | None = None,
    ) -> tuple[str, str]:
        """
        Upload file by selected provider.

        :param db: db session
        :param file: upload file
        :param path: request upload path
        :param use_signed_url: whether force signed url
        :param url_expire_seconds: request url expire seconds
        :param object_expire_days: request object expire days
        :return:
        """
        cfg = await self._load_runtime_config(db)
        filename = build_filename(file)
        upload_path = self._normalize_path(path)
        object_key = self._build_object_key(cfg.key_prefix, upload_path, filename)

        provider = self._resolve_provider(cfg.provider)
        context = self._build_upload_context(
            cfg=cfg,
            file=file,
            object_key=object_key,
            use_signed_url=use_signed_url,
            url_expire_seconds=url_expire_seconds,
            object_expire_days=object_expire_days,
        )
        log.info(
            f'[OSS] upload begin provider={cfg.provider} object_key={object_key} '
            f'configured_signed={cfg.use_signed_url} effective_signed={context.use_signed_url} ' 
            f'expire_seconds={context.signed_url_expire_seconds}'
        )
        url = await provider.upload(context)
        url_type = self._detect_url_type(url)
        log.info(
            f'[OSS] upload done provider={cfg.provider} object_key={object_key} '
            f'url_type={url_type} url={self._safe_url_preview(url)}'
        )
        return url, object_key

    async def upload_with_filename(
        self,
        db: AsyncSession,
        file: UploadFile,
        filename: str,
        path: str | None = None,
        use_signed_url: bool | None = None,
        url_expire_seconds: int | None = None,
        object_expire_days: int | None = None,
    ) -> tuple[str, str]:
        """
        Upload file with deterministic filename.

        :param db: db session
        :param file: upload file
        :param filename: custom filename
        :param path: request upload path
        :param use_signed_url: whether force signed url
        :param url_expire_seconds: request url expire seconds
        :param object_expire_days: request object expire days
        :return:
        """
        cfg = await self._load_runtime_config(db)
        upload_path = self._normalize_path(path)
        safe_filename = self._normalize_filename(filename)
        object_key = self._build_object_key(cfg.key_prefix, upload_path, safe_filename)

        provider = self._resolve_provider(cfg.provider)
        context = self._build_upload_context(
            cfg=cfg,
            file=file,
            object_key=object_key,
            use_signed_url=use_signed_url,
            url_expire_seconds=url_expire_seconds,
            object_expire_days=object_expire_days,
        )
        log.info(
            f'[OSS] upload begin provider={cfg.provider} object_key={object_key} '
            f'configured_signed={cfg.use_signed_url} effective_signed={context.use_signed_url} ' 
            f'expire_seconds={context.signed_url_expire_seconds}'
        )
        url = await provider.upload(context)
        url_type = self._detect_url_type(url)
        log.info(
            f'[OSS] upload done provider={cfg.provider} object_key={object_key} '
            f'url_type={url_type} url={self._safe_url_preview(url)}'
        )
        return url, object_key


storage_service = StorageService()
