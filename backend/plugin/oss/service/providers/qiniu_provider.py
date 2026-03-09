#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import tempfile
import traceback

from asgiref.sync import sync_to_async
from pathlib import Path

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.plugin.oss.service.providers.base import ProviderUploadContext


class QiniuKodoProvider:
    """七牛云 Kodo provider"""

    _REGION_IDS: tuple[str, ...] = ('z0', 'z1', 'z2', 'na0', 'as0')

    @staticmethod
    def _to_bool(value: str | bool | None, default: bool) -> bool:
        """
        Parse bool value.

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
    def _cleanup_region_cache() -> None:
        """Cleanup qiniu region cache files."""
        temp_dir = Path(tempfile.gettempdir())
        cache_files = (
            temp_dir / 'qn-regions-cache.jsonl',
            temp_dir / 'qn-regions-cache.jsonl.shrink',
        )
        for cache_file in cache_files:
            if not cache_file.exists():
                continue
            try:
                cache_file.unlink()
            except OSError:
                continue

    @staticmethod
    def _disable_region_persist_cache() -> None:
        """Disable qiniu sdk region file cache to avoid Windows cache race and Python 3.14 strftime issues."""
        try:
            from qiniu.http import regions_provider

            scope = getattr(regions_provider, '_global_cache_scope', None)
            if scope is None:
                return
            persist_path = getattr(scope, 'persist_path', None)
            if not persist_path:
                return
            regions_provider._global_cache_scope = scope._replace(persist_path='')  # noqa: SLF001
        except Exception:
            return

    @staticmethod
    def _should_try_region_fallback(exc: Exception) -> bool:
        """
        Check whether exception should use explicit region fallback.

        :param exc: source exception
        :return:
        """
        text = str(exc)
        return (
            'Query regions failed' in text
            or 'Invalid format string' in text
            or isinstance(exc, TypeError)
            or isinstance(exc, ValueError)
        )

    @staticmethod
    def _build_public_url(domain: str, object_key: str, use_https: bool) -> str:
        """
        Build public url from domain and object key.

        :param domain: qiniu domain
        :param object_key: object key
        :param use_https: whether use https
        :return:
        """
        base = domain.rstrip('/')
        if not base.startswith('http://') and not base.startswith('https://'):
            scheme = 'https' if use_https else 'http'
            base = f'{scheme}://{base}'
        return f'{base}/{object_key}'

    async def upload(self, context: ProviderUploadContext) -> str:
        """
        Upload file by qiniu kodo.

        :param context: upload context
        :return:
        """
        return await self._upload_sync(context)

    @sync_to_async
    def _upload_sync(self, context: ProviderUploadContext) -> str:
        """
        Upload file by qiniu kodo in sync thread.

        :param context: upload context
        :return:
        """
        try:
            from qiniu import Auth, put_data

            self._disable_region_persist_cache()

            access_key = str(settings.QINIU_KODO_ACCESS_KEY).strip()
            secret_key = str(settings.QINIU_KODO_SECRET_KEY).strip()
            bucket_name = str(settings.QINIU_KODO_BUCKET).strip() or str(settings.QINIU_KODO_BUCKET_NAME).strip()
            domain = str(settings.QINIU_KODO_DOMAIN).strip()
            use_https = self._to_bool(settings.QINIU_KODO_USE_HTTPS, True)

            if not access_key or not secret_key or not bucket_name or not domain:
                raise errors.RequestError(msg='七牛云 Kodo 配置不完整，请检查环境变量')

            token_policy: dict[str, int] | None = None
            if context.object_expire_days:
                token_policy = {'deleteAfterDays': context.object_expire_days}

            auth = Auth(access_key, secret_key)
            token = auth.upload_token(
                bucket_name,
                context.object_key,
                context.signed_url_expire_seconds,
                token_policy,
            )

            context.file.file.seek(0)
            content = context.file.file.read()

            def put_data_once(regions: list | None = None) -> None:
                result_inner, info_inner = put_data(token, context.object_key, content, regions=regions)
                status_code_inner = getattr(info_inner, 'status_code', 0)
                if status_code_inner >= 400:
                    body = getattr(info_inner, 'text_body', None)
                    raise RuntimeError(f'qiniu put_data failed, status={status_code_inner}, body={body}')
                if not isinstance(result_inner, dict) or result_inner.get('key') != context.object_key:
                    raise RuntimeError('qiniu response key mismatch')

            def put_data_with_region_fallback(origin_exc: Exception) -> None:
                if not self._should_try_region_fallback(origin_exc):
                    raise origin_exc

                from qiniu.http.region import Region

                scheme = 'https' if use_https else 'http'
                last_error: Exception = origin_exc
                for region_id in self._REGION_IDS:
                    try:
                        region = Region.from_region_id(region_id, preferred_scheme=scheme)
                        put_data_once(regions=[region])
                        return
                    except Exception as region_exc:
                        last_error = region_exc
                raise last_error

            try:
                put_data_once()
            except OSError as exc:
                if getattr(exc, 'winerror', None) != 183:
                    raise
                self._cleanup_region_cache()
                try:
                    put_data_once()
                except Exception as retry_exc:
                    put_data_with_region_fallback(retry_exc)
            except Exception as exc:
                put_data_with_region_fallback(exc)

            public_url = self._build_public_url(domain, context.object_key, use_https)
            if context.use_signed_url:
                return auth.private_download_url(public_url, expires=context.signed_url_expire_seconds)
            return public_url
        except errors.RequestError:
            raise
        except Exception as exc:
            stack_text = traceback.format_exc()
            log.error(f'七牛云上传失败 object_key={context.object_key}: [{type(exc).__name__}] {exc!r}\n{stack_text}')
            raise errors.RequestError(msg='上传文件失败')
