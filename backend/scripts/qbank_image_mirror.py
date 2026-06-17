#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import hashlib
import json
import mimetypes
import random
import re
import time

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.cache.local import local_cache_manager
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.plugin.oss.service.providers.base import ProviderUploadContext, StorageProvider
from backend.plugin.oss.service.storage_service import StorageRuntimeConfig, storage_service
from backend.utils.timezone import timezone

PROJECT_ROOT = Path(__file__).resolve().parents[2]

IMG_TAG_RE = re.compile(r'<img\b[^>]*>', re.IGNORECASE)
IMG_ATTR_RE = re.compile(r'(?P<name>src|_src|data-src)\s*=\s*(?P<quote>"|\')(?P<url>.*?)(?P=quote)', re.IGNORECASE)


@dataclass
class MirrorStats:
    """Image mirror stats."""

    scanned_html: int = 0
    scanned_images: int = 0
    replaced_images: int = 0
    uploaded_images: int = 0
    cache_hit: int = 0
    failed_images: int = 0
    public_urls: int = 0
    signed_urls: int = 0
    unknown_urls: int = 0


@dataclass
class MirrorRewriteSample:
    """Mirror rewrite sample row."""

    field_name: str
    scope_segment: str
    source_url: str
    mirrored_url: str
    from_cache: bool


class QbankImageMirror:
    """Mirror external image urls to configured OSS provider."""

    def __init__(
        self,
        *,
        cache_file: Path | None = None,
        request_timeout: float = 20.0,
        object_expire_days: int | None = None,
        sample_limit: int = 0,
        safe_interval_seconds: float = 2.5,
        safe_interval_jitter_seconds: float = 0.5,
    ) -> None:
        self.cache_file = cache_file or (PROJECT_ROOT / 'backend' / 'scripts' / 'cache' / 'qbank_image_cache.json')
        self.request_timeout = request_timeout
        self.object_expire_days = object_expire_days
        self.sample_limit = max(0, sample_limit)
        self.safe_interval_seconds = max(0.0, safe_interval_seconds)
        self.safe_interval_jitter_seconds = max(0.0, safe_interval_jitter_seconds)

        self.stats = MirrorStats()
        self.cache: dict[str, dict[str, str]] = {}
        self._cache_dirty = False
        self.rewrite_samples: list[MirrorRewriteSample] = []
        self._last_download_at = 0.0

        self.runtime_cfg: StorageRuntimeConfig | None = None
        self.provider: StorageProvider | None = None
        self.own_domains: set[str] = set()

    def _add_sample(
        self,
        *,
        field_name: str,
        scope_segment: str,
        source_url: str,
        mirrored_url: str,
        from_cache: bool,
    ) -> None:
        """
        Add rewrite sample if collector is enabled.

        :param field_name: field name
        :param scope_segment: scope segment
        :param source_url: source url
        :param mirrored_url: mirrored url
        :param from_cache: whether mirrored url comes from cache
        :return:
        """
        if self.sample_limit <= 0:
            return
        if len(self.rewrite_samples) >= self.sample_limit:
            return
        self.rewrite_samples.append(
            MirrorRewriteSample(
                field_name=field_name,
                scope_segment=scope_segment,
                source_url=source_url,
                mirrored_url=mirrored_url,
                from_cache=from_cache,
            )
        )

    @staticmethod
    def _sanitize_segment(
        value: str,
        *,
        default: str,
        max_length: int = 64,
        lowercase: bool = False,
    ) -> str:
        """
        Build safe object key segment.

        :param value: source segment
        :param default: fallback segment
        :param max_length: max segment length
        :return:
        """
        raw = str(value or '').strip()
        if lowercase:
            raw = raw.lower()
        if not raw:
            return default
        safe = re.sub(r'[^a-zA-Z0-9_-]+', '_', raw).strip('_')
        if not safe:
            return default
        return safe[:max_length]

    @staticmethod
    def _normalize_url(url: str) -> str:
        """
        Normalize raw url.

        :param url: source url
        :return:
        """
        value = str(url or '').strip()
        if value.startswith('//'):
            return f'https:{value}'
        return value

    def _load_cache(self) -> None:
        """Load local cache file."""
        if not self.cache_file.exists():
            self.cache = {}
            return

        try:
            data = json.loads(self.cache_file.read_text(encoding='utf-8'))
        except Exception:
            self.cache = {}
            return

        if not isinstance(data, dict):
            self.cache = {}
            return
        self.cache = {str(key): value for key, value in data.items() if isinstance(value, dict)}

    def save_cache(self) -> None:
        """Persist local cache file."""
        if not self._cache_dirty:
            return
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(
            json.dumps(self.cache, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        self._cache_dirty = False

    @staticmethod
    def _append_domain(domain_set: set[str], raw: str) -> None:
        """
        Parse and append host part into domain set.

        :param domain_set: output set
        :param raw: raw domain text
        :return:
        """
        value = str(raw or '').strip()
        if not value:
            return

        parsed = urlparse(value if '://' in value else f'https://{value}')
        host = (parsed.netloc or parsed.path or '').strip().lower()
        if not host:
            return
        domain_set.add(host.split('/')[0])

    @staticmethod
    def _detect_url_type(url: str) -> str:
        """
        Detect url type from query markers.

        :param url: returned object url
        :return:
        """
        if not url:
            return 'unknown'

        parsed = urlparse(url)
        query_keys = {key.lower() for key in parse_qs(parsed.query)}
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

    async def initialize(self, db: AsyncSession) -> None:
        """
        Initialize runtime config and provider.

        :param db: db session
        :return:
        """
        await self._invalidate_storage_config_cache()
        self.runtime_cfg = await storage_service._load_runtime_config(db)  # noqa: SLF001
        self.provider = storage_service._resolve_provider(self.runtime_cfg.provider)  # noqa: SLF001
        self._load_cache()

        self.own_domains = set()
        for key in ['QINIU_KODO_DOMAIN', 'OSS_ENDPOINT', 'OSS_DOMAIN']:
            self._append_domain(self.own_domains, str(getattr(settings, key, '')).strip())
        print(
            '[MIRROR_CFG]'
            f' provider={self.runtime_cfg.provider}'
            f' key_prefix={self.runtime_cfg.key_prefix or "<empty>"}'
            f' use_signed={self.runtime_cfg.use_signed_url}'
            f' signed_expire={self.runtime_cfg.signed_url_expire_seconds}'
            f' object_expire_days={self.runtime_cfg.object_expire_days}'
            f' qiniu_domain={str(getattr(settings, "QINIU_KODO_DOMAIN", "")).strip() or "<empty>"}'
            f' safe_interval={self.safe_interval_seconds:.2f}s'
            f' jitter={self.safe_interval_jitter_seconds:.2f}s'
        )

    @staticmethod
    async def _invalidate_storage_config_cache() -> None:
        """Invalidate storage dynamic config cache for script process."""
        cache_prefix = settings.CACHE_CONFIG_REDIS_PREFIX
        if settings.CACHE_LOCAL_ENABLED:
            local_cache_manager.delete_prefix(cache_prefix)

        try:
            await redis_client.delete_prefix(cache_prefix)
        except Exception as exc:
            log.warning(f'clear config cache failed, continue with existing cache: {exc!s}')

    def _is_external_image_url(self, url: str) -> bool:
        """
        Check whether url should be mirrored.

        :param url: source url
        :return:
        """
        normalized = self._normalize_url(url)
        if not normalized:
            return False
        if normalized.startswith('data:'):
            return False
        if not normalized.startswith('http://') and not normalized.startswith('https://'):
            return False

        host = (urlparse(normalized).netloc or '').lower()
        if host and host in self.own_domains:
            return False
        return True

    @staticmethod
    def _guess_extension(url: str, content_type: str | None) -> str:
        """
        Guess extension from url and content type.

        :param url: source url
        :param content_type: response content type
        :return:
        """
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix and 1 < len(suffix) <= 10 and re.fullmatch(r'\.[a-z0-9]+', suffix):
            return suffix

        if content_type:
            mime = content_type.split(';', 1)[0].strip().lower()
            ext = mimetypes.guess_extension(mime)
            if ext:
                return ext
        return '.png'

    @staticmethod
    def _build_scope_segment(question_id: int | None, scope_segment: str | None) -> str:
        """
        Build stable scope segment for object path.

        :param question_id: optional question id
        :param scope_segment: explicit scope segment
        :return:
        """
        if scope_segment:
            return str(scope_segment).strip()
        if isinstance(question_id, int) and question_id > 0:
            return f'q_{question_id}'
        return 'content'

    async def _download_binary(self, client: httpx.AsyncClient, url: str) -> tuple[bytes, str | None]:
        """
        Download binary from remote url.

        :param client: http client
        :param url: source url
        :return:
        """
        await self._wait_safe_interval()
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        return response.content, response.headers.get('content-type')

    async def _wait_safe_interval(self) -> None:
        """Wait between remote image download requests to reduce risk-control pressure."""
        if self.safe_interval_seconds <= 0:
            self._last_download_at = time.monotonic()
            return

        target_interval = self.safe_interval_seconds
        if self.safe_interval_jitter_seconds > 0:
            jitter = random.uniform(0.0, self.safe_interval_jitter_seconds)
            target_interval += jitter

        elapsed = time.monotonic() - self._last_download_at
        if elapsed < target_interval:
            await asyncio.sleep(target_interval - elapsed)
        self._last_download_at = time.monotonic()

    async def _upload_binary(
        self,
        *,
        binary: bytes,
        filename: str,
        path: str,
        url_expire_seconds: int | None = None,
    ) -> tuple[str, str]:
        """
        Upload binary via configured provider.

        :param binary: file bytes
        :param filename: target filename
        :param path: target path
        :param url_expire_seconds: signed url expire seconds
        :return:
        """
        if self.runtime_cfg is None or self.provider is None:
            raise RuntimeError('mirror service not initialized')

        upload_file = UploadFile(file=BytesIO(binary), filename=filename)
        upload_path = storage_service._normalize_path(path)  # noqa: SLF001
        safe_filename = storage_service._normalize_filename(filename)  # noqa: SLF001
        object_key = storage_service._build_object_key(self.runtime_cfg.key_prefix, upload_path, safe_filename)  # noqa: SLF001
        context = ProviderUploadContext(
            file=upload_file,
            object_key=object_key,
            use_signed_url=self.runtime_cfg.use_signed_url,
            signed_url_expire_seconds=storage_service._resolve_signed_url_expire(  # noqa: SLF001
                url_expire_seconds,
                self.runtime_cfg.signed_url_expire_seconds,
            ),
            object_expire_days=storage_service._resolve_object_expire_days(  # noqa: SLF001
                self.object_expire_days,
                self.runtime_cfg.object_expire_days,
            ),
        )
        try:
            url = await self.provider.upload(context)
        finally:
            await upload_file.close()
        url_type = self._detect_url_type(url)
        if url_type == 'signed':
            self.stats.signed_urls += 1
        elif url_type == 'public':
            self.stats.public_urls += 1
        else:
            self.stats.unknown_urls += 1
        return url, object_key

    async def mirror_one(
        self,
        *,
        client: httpx.AsyncClient,
        source_url: str,
        bank_code: str,
        scope_segment: str,
        field_name: str,
        image_index: int,
    ) -> tuple[str, bool]:
        """
        Mirror one image url.

        :param client: http client
        :param source_url: source url
        :param bank_code: bank code
        :param scope_segment: path scope, for example q_123
        :param field_name: field name
        :param image_index: image index in the html field
        :return:
        """
        cached = self.cache.get(source_url)
        if cached and cached.get('url') and cached.get('object_key'):
            self.stats.cache_hit += 1
            return str(cached['url']), True

        binary, content_type = await self._download_binary(client, source_url)
        image_hash = hashlib.sha256(source_url.encode('utf-8')).hexdigest()[:10]
        extension = self._guess_extension(source_url, content_type)

        safe_bank = self._sanitize_segment(bank_code, default='bank')
        safe_scope = self._sanitize_segment(scope_segment, default='content')
        safe_field = self._sanitize_segment(field_name, default='content', lowercase=True)

        filename = f'{safe_field}_{image_index:02d}_{image_hash}{extension}'
        target_path = f'qbank/{safe_bank}/{safe_scope}/{safe_field}'
        url, object_key = await self._upload_binary(binary=binary, filename=filename, path=target_path)

        self.stats.uploaded_images += 1
        self.cache[source_url] = {
            'url': url,
            'object_key': object_key,
            'updated_at': timezone.now().isoformat(),
        }
        self._cache_dirty = True
        return url, False

    async def mirror_html(
        self,
        *,
        html: str,
        bank_code: str,
        field_name: str,
        question_id: int | None = None,
        scope_segment: str | None = None,
    ) -> str:
        """
        Mirror all image urls in html.

        :param html: html text
        :param bank_code: bank code
        :param field_name: field name
        :param question_id: optional question id
        :param scope_segment: optional explicit scope segment
        :return:
        """
        if not isinstance(html, str):
            return html
        if '<img' not in html.lower():
            return html

        self.stats.scanned_html += 1
        img_matches = list(IMG_TAG_RE.finditer(html))
        if not img_matches:
            return html

        resolved_scope = self._build_scope_segment(question_id, scope_segment)
        replacements: list[tuple[int, int, str]] = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(self.request_timeout)) as client:
            for image_index, tag_match in enumerate(img_matches, start=1):
                raw_tag = tag_match.group(0)
                attr_matches = list(IMG_ATTR_RE.finditer(raw_tag))
                if not attr_matches:
                    continue

                attr_map: dict[str, str] = {}
                for attr in attr_matches:
                    attr_map[attr.group('name').lower()] = self._normalize_url(attr.group('url'))

                source_url = ''
                for key in ('_src', 'src', 'data-src'):
                    candidate = attr_map.get(key, '')
                    if self._is_external_image_url(candidate):
                        source_url = candidate
                        break
                if not source_url:
                    continue

                self.stats.scanned_images += 1
                try:
                    mirrored_url, from_cache = await self.mirror_one(
                        client=client,
                        source_url=source_url,
                        bank_code=bank_code,
                        scope_segment=resolved_scope,
                        field_name=field_name,
                        image_index=image_index,
                    )
                except Exception as exc:
                    self.stats.failed_images += 1
                    log.warning(
                        'image mirror failed, keep original '
                        f'field={field_name} scope={resolved_scope} url={source_url} error={exc!s}'
                    )
                    continue

                def replace_attr(match_obj: re.Match[str]) -> str:
                    attr_name = match_obj.group('name')
                    quote = match_obj.group('quote')
                    return f'{attr_name}={quote}{mirrored_url}{quote}'

                new_tag = IMG_ATTR_RE.sub(replace_attr, raw_tag)
                if new_tag == raw_tag:
                    continue
                self._add_sample(
                    field_name=field_name,
                    scope_segment=resolved_scope,
                    source_url=source_url,
                    mirrored_url=mirrored_url,
                    from_cache=from_cache,
                )
                replacements.append((tag_match.start(), tag_match.end(), new_tag))
                self.stats.replaced_images += 1

        if not replacements:
            return html

        chunks: list[str] = []
        last_pos = 0
        for start_pos, end_pos, replacement in replacements:
            chunks.append(html[last_pos:start_pos])
            chunks.append(replacement)
            last_pos = end_pos
        chunks.append(html[last_pos:])
        return ''.join(chunks)
