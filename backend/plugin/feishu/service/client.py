import asyncio
import time

from typing import Any

import httpx

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.redis import redis_client


class FeishuClient:
    """飞书开放平台客户端（应用身份）"""

    # 开放平台接口基地址
    BASE_URL = 'https://open.feishu.cn/open-apis'
    # 换 token 接口
    TOKEN_PATH = '/auth/v3/tenant_access_token/internal'
    # token 失效类错误码，命中后清缓存并重试一次
    TOKEN_INVALID_CODES = frozenset({99991661, 99991663, 99991668})
    # Redis 操作超时时间（秒），超时或异常时降级为不使用缓存
    REDIS_TIMEOUT = 3
    # Redis 不可用后的冷却时间（秒），冷却期内不再尝试
    REDIS_COOLDOWN_SECONDS = 60

    def __init__(self, app_id: str | None = None, app_secret: str | None = None) -> None:
        """
        初始化客户端

        :param app_id: 应用 App ID，为空时使用全局配置
        :param app_secret: 应用 App Secret，为空时使用全局配置
        """
        self.app_id = (app_id or settings.FEISHU_APP_ID or '').strip()
        self.app_secret = (app_secret or settings.FEISHU_APP_SECRET or '').strip()
        self._redis_disabled_until = 0.0
        self._local_token: str | None = None
        self._local_token_expire_at = 0.0

    @property
    def cache_key(self) -> str:
        """token 缓存键"""
        return f'{settings.FEISHU_TOKEN_REDIS_PREFIX}:{self.app_id}'

    def _redis_available(self) -> bool:
        """Redis 是否处于可用状态"""
        return time.time() >= self._redis_disabled_until

    def _mark_redis_down(self, exc: Exception) -> None:
        """标记 Redis 不可用，进入冷却期"""
        self._redis_disabled_until = time.time() + self.REDIS_COOLDOWN_SECONDS
        log.warning(f'飞书 token 缓存不可用，{self.REDIS_COOLDOWN_SECONDS}s 内降级为直连: {exc!s}')

    def _ensure_credentials(self) -> None:
        """校验应用凭证是否已配置"""
        if not self.app_id or not self.app_secret:
            raise errors.ForbiddenError(msg='飞书 App ID 或 App Secret 未配置')

    async def _clear_token_cache(self) -> None:
        """清除本地 token 缓存"""
        self._local_token = None
        self._local_token_expire_at = 0.0
        if not self._redis_available():
            return
        try:
            await asyncio.wait_for(redis_client.delete(self.cache_key), timeout=self.REDIS_TIMEOUT)
        except Exception as exc:
            self._mark_redis_down(exc)

    def _read_local_token(self) -> str | None:
        """读取进程内缓存的 token"""
        if self._local_token and time.time() < self._local_token_expire_at:
            return self._local_token
        return None

    def _write_local_token(self, token: str, expire_seconds: int) -> None:
        """写入进程内缓存的 token"""
        self._local_token = token
        self._local_token_expire_at = time.time() + max(expire_seconds - 300, 60)

    async def _read_cached_token(self) -> str | None:
        """读取缓存的 token，Redis 不可用时降级为进程内缓存"""
        local = self._read_local_token()
        if local:
            return local
        if not self._redis_available():
            return None
        try:
            cached = await asyncio.wait_for(redis_client.get(self.cache_key), timeout=self.REDIS_TIMEOUT)
        except Exception as exc:
            self._mark_redis_down(exc)
            return None
        return str(cached) if cached else None

    async def _write_cached_token(self, token: str, expire_seconds: int) -> None:
        """写入 token 缓存（进程内 + Redis）"""
        self._write_local_token(token, expire_seconds)
        if not self._redis_available():
            return
        ttl = max(expire_seconds - 300, 60)
        try:
            await asyncio.wait_for(
                redis_client.setex(self.cache_key, ttl, token),
                timeout=self.REDIS_TIMEOUT,
            )
        except Exception as exc:
            self._mark_redis_down(exc)

    async def get_tenant_access_token(self) -> str:
        """
        获取 tenant_access_token（带 Redis 缓存）

        :return:
        """
        self._ensure_credentials()

        cached = await self._read_cached_token()
        if cached:
            return cached

        async with httpx.AsyncClient(timeout=settings.FEISHU_REQUEST_TIMEOUT) as client:
            response = await client.post(
                f'{self.BASE_URL}{self.TOKEN_PATH}',
                json={'app_id': self.app_id, 'app_secret': self.app_secret},
            )

        try:
            payload: dict[str, Any] = response.json()
        except Exception as exc:
            raise errors.GatewayError(msg=f'飞书鉴权响应解析失败: {exc!s}') from exc

        token = payload.get('tenant_access_token')
        if payload.get('code') != 0 or not token:
            log.error(f'飞书 tenant_access_token 获取失败: {payload}')
            raise errors.GatewayError(msg=f'飞书鉴权失败: {payload.get("msg") or "未知错误"}')

        await self._write_cached_token(str(token), int(payload.get('expire') or 7200))
        return str(token)

    async def _send(
        self,
        method: str,
        path: str,
        token: str,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        发送单次请求

        :param method: HTTP 方法
        :param path: 接口路径（以 / 开头）
        :param token: 访问令牌
        :param json_body: 请求体
        :param params: URL 查询参数
        :return:
        """
        async with httpx.AsyncClient(timeout=settings.FEISHU_REQUEST_TIMEOUT) as client:
            response = await client.request(
                method,
                f'{self.BASE_URL}{path}',
                json=json_body,
                params=params,
                headers={'Authorization': f'Bearer {token}'},
            )

        try:
            return response.json()
        except Exception as exc:
            raise errors.GatewayError(msg=f'飞书接口响应解析失败: {exc!s}') from exc

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        发起飞书 API 请求，自动附带 token 并在 token 失效时刷新重试一次

        :param method: HTTP 方法
        :param path: 接口路径（以 / 开头）
        :param json_body: 请求体
        :param params: URL 查询参数
        :return:
        """
        token = await self.get_tenant_access_token()
        payload = await self._send(method, path, token, json_body, params)

        if payload.get('code') in self.TOKEN_INVALID_CODES:
            await self._clear_token_cache()
            token = await self.get_tenant_access_token()
            payload = await self._send(method, path, token, json_body, params)

        if payload.get('code') != 0:
            log.error(
                f'飞书 API 请求失败 method={method} path={path} code={payload.get("code")} msg={payload.get("msg")}'
            )
            raise errors.GatewayError(msg=f'飞书接口调用失败: {payload.get("msg") or payload.get("code")}')

        return payload.get('data') or {}
