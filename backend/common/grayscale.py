#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import json

from fastapi import Request

import cachebox

from backend.common.exception import errors
from backend.common.log import log
from backend.database.redis import redis_client

GRAYSCALE_REDIS_PREFIX = 'fba:grayscale'
GRAYSCALE_LOCAL_CACHE_MAXSIZE = 1000
GRAYSCALE_LOCAL_CACHE_TTL = 10

_grayscale_cache = cachebox.TTLCache(GRAYSCALE_LOCAL_CACHE_MAXSIZE, GRAYSCALE_LOCAL_CACHE_TTL)


class GrayscaleConfig:
    """灰度功能配置"""

    __slots__ = ('enabled', 'whitelist', 'ratio')

    def __init__(self, *, enabled: bool = True, whitelist: list[int] | None = None, ratio: float = 0.0) -> None:
        self.enabled = enabled
        self.whitelist = whitelist or []
        self.ratio = ratio

    def to_json(self) -> str:
        return json.dumps({'enabled': self.enabled, 'whitelist': self.whitelist, 'ratio': self.ratio})

    @classmethod
    def from_json(cls, raw: str) -> 'GrayscaleConfig':
        data = json.loads(raw)
        return cls(enabled=data.get('enabled', True), whitelist=data.get('whitelist', []), ratio=data.get('ratio', 0.0))

    def to_dict(self) -> dict:
        return {'enabled': self.enabled, 'whitelist': self.whitelist, 'ratio': self.ratio}


def _redis_key(feature: str) -> str:
    return f'{GRAYSCALE_REDIS_PREFIX}:{feature}'


def _user_bucket(user_id: int, feature: str) -> int:
    """确定性分桶，同一用户对同一功能结果稳定"""
    key = f'{user_id}:{feature}'
    digest = hashlib.md5(key.encode()).hexdigest()
    return int(digest, 16) % 10000


async def get_config(feature: str) -> GrayscaleConfig | None:
    """
    获取灰度配置

    优先本地缓存，未命中则查 Redis
    key 不存在返回 None（全量上线）

    :param feature: 功能名称
    :return:
    """
    cache_key = _redis_key(feature)
    cached = _grayscale_cache.get(cache_key)
    if cached is not None:
        return cached

    try:
        raw = await redis_client.get(cache_key)
    except Exception as e:
        log.warning(f'[Grayscale] Redis 读取失败 feature={feature}: {e}')
        return None

    if raw is None:
        _grayscale_cache[cache_key] = None
        return None

    try:
        config = GrayscaleConfig.from_json(raw)
    except Exception as e:
        log.error(f'[Grayscale] 配置解析失败 feature={feature}: {e}')
        return None

    _grayscale_cache[cache_key] = config
    return config


async def set_config(feature: str, config: GrayscaleConfig) -> None:
    """
    设置灰度配置

    写 Redis 并清本地缓存

    :param feature: 功能名称
    :param config: 灰度配置
    :return:
    """
    cache_key = _redis_key(feature)
    await redis_client.set(cache_key, config.to_json())
    try:
        del _grayscale_cache[cache_key]
    except KeyError:
        pass


async def delete_config(feature: str) -> None:
    """
    删除灰度配置

    删 Redis 并清本地缓存，表示全量上线

    :param feature: 功能名称
    :return:
    """
    cache_key = _redis_key(feature)
    await redis_client.delete(cache_key)
    try:
        del _grayscale_cache[cache_key]
    except KeyError:
        pass


async def list_configs() -> dict[str, GrayscaleConfig]:
    """
    列出所有灰度配置

    :return:
    """
    keys = await redis_client.get_by_prefix(GRAYSCALE_REDIS_PREFIX)
    result: dict[str, GrayscaleConfig] = {}
    for key in keys:
        feature = key.removeprefix(f'{GRAYSCALE_REDIS_PREFIX}:')
        raw = await redis_client.get(key)
        if raw:
            try:
                result[feature] = GrayscaleConfig.from_json(raw)
            except Exception:
                pass
    return result


async def check_grayscale(user_id: int, feature: str) -> bool:
    """
    检查用户是否通过灰度

    :param user_id: 用户 ID
    :param feature: 功能名称
    :return:
    """
    config = await get_config(feature)
    if config is None:
        return True
    if not config.enabled:
        return False
    if user_id in config.whitelist:
        return True
    if config.ratio <= 0:
        return False
    return _user_bucket(user_id, feature) < int(config.ratio * 10000)


class GrayscaleGate:
    """灰度门禁依赖注入校验器"""

    def __init__(self, feature: str) -> None:
        self.feature = feature

    async def __call__(self, request: Request) -> None:
        user = getattr(request, 'user', None)
        user_id = getattr(user, 'id', None)
        if user_id is None:
            raise errors.AuthorizationError(msg='请先登录')
        if not await check_grayscale(user_id, self.feature):
            raise errors.ForbiddenError(msg='功能尚未对您开放')


def require_grayscale(feature: str) -> GrayscaleGate:
    """创建灰度门禁实例"""
    return GrayscaleGate(feature)