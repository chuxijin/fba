#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from collections.abc import Awaitable
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import TypeVar
from unittest.mock import AsyncMock

import pytest

from backend.app.study_plan.schema.spatial_cube import (
    CreateSpatialCubePatternParam,
    GetSpatialCubePatternCatalog,
    UpdateSpatialCubePatternParam,
)
from backend.app.study_plan.service import spatial_cube as spatial_cube_service
from backend.common.exception import errors

ResultType = TypeVar('ResultType')


def run(coro: Awaitable[ResultType]) -> ResultType:
    """
    同步运行协程

    :param coro: 待运行的协程
    :return:
    """
    return asyncio.run(coro)


class FakeRedis:
    """面素材缓存替身"""

    def __init__(self, cached_value: str | None = None) -> None:
        self.cached_value = cached_value
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.deleted_keys: list[str] = []

    async def get(self, key: str) -> str | None:
        """
        获取缓存

        :param key: 缓存键
        :return:
        """
        return self.cached_value

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """
        记录缓存写入

        :param key: 缓存键
        :param value: 缓存值
        :param ex: 过期秒数
        :return:
        """
        self.set_calls.append((key, value, ex))

    async def delete(self, key: str) -> None:
        """
        记录缓存删除

        :param key: 缓存键
        :return:
        """
        self.deleted_keys.append(key)


def make_pattern(pattern_id: int = 1, **overrides) -> SimpleNamespace:
    """
    构造面素材模型替身

    :param pattern_id: 素材 ID
    :param overrides: 覆盖字段
    :return:
    """
    values = {
        'id': pattern_id,
        'code': f'pattern-{pattern_id}',
        'name': f'素材 {pattern_id}',
        'render_type': 'builtin',
        'asset_url': None,
        'asset_version': 'builtin-v1',
        'rotation_period': 360,
        'sort': pattern_id,
        'is_active': True,
        'created_time': datetime(2026, 7, 22, tzinfo=timezone.utc),
        'updated_time': datetime(2026, 7, 22, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_catalog_cache_hit_skips_database(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证缓存命中时跳过数据库

    :param monkeypatch: pytest monkeypatch
    :return:
    """
    expected = GetSpatialCubePatternCatalog(version='cached', patterns=[])
    fake_redis = FakeRedis(expected.model_dump_json())

    fail_get_all = AsyncMock(side_effect=AssertionError('缓存命中时不应查询数据库'))

    monkeypatch.setattr(spatial_cube_service, 'redis_client', fake_redis)
    monkeypatch.setattr(spatial_cube_service.study_spatial_cube_pattern_dao, 'get_all', fail_get_all)

    catalog = run(spatial_cube_service.get_spatial_cube_pattern_catalog(db=None))

    assert catalog == expected
    assert fake_redis.set_calls == []


def test_catalog_cache_miss_loads_active_patterns(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证缓存未命中时仅查询启用素材并回填缓存

    :param monkeypatch: pytest monkeypatch
    :return:
    """
    fake_redis = FakeRedis()
    fake_get_all = AsyncMock(return_value=[make_pattern()])

    monkeypatch.setattr(spatial_cube_service, 'redis_client', fake_redis)
    monkeypatch.setattr(spatial_cube_service.study_spatial_cube_pattern_dao, 'get_all', fake_get_all)

    catalog = run(spatial_cube_service.get_spatial_cube_pattern_catalog(db=None))

    fake_get_all.assert_awaited_once_with(None, include_inactive=False)
    assert [pattern.code for pattern in catalog.patterns] == ['pattern-1']
    assert fake_redis.set_calls[0][0] == spatial_cube_service.SPATIAL_CUBE_PATTERN_CACHE_KEY
    assert fake_redis.set_calls[0][2] == spatial_cube_service.SPATIAL_CUBE_PATTERN_CACHE_TTL


def test_create_image_pattern_requires_asset_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证图片素材必须配置远程 URL

    :param monkeypatch: pytest monkeypatch
    :return:
    """
    monkeypatch.setattr(
        spatial_cube_service.study_spatial_cube_pattern_dao,
        'get_by_code',
        AsyncMock(return_value=None),
    )
    param = CreateSpatialCubePatternParam(code='remote', name='远程素材', render_type='image')

    with pytest.raises(errors.RequestError):
        run(spatial_cube_service.create_spatial_cube_pattern(db=None, param=param, user_id=1))


def test_create_passes_schema_to_crud_and_invalidates_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证创建服务向 CRUD 传递 Schema 并清理缓存

    :param monkeypatch: pytest monkeypatch
    :return:
    """
    fake_redis = FakeRedis()
    fake_get_by_code = AsyncMock(return_value=None)
    fake_create = AsyncMock(return_value=make_pattern(code='custom', name='自定义素材'))

    monkeypatch.setattr(spatial_cube_service, 'redis_client', fake_redis)
    monkeypatch.setattr(spatial_cube_service.study_spatial_cube_pattern_dao, 'get_by_code', fake_get_by_code)
    monkeypatch.setattr(spatial_cube_service.study_spatial_cube_pattern_dao, 'create', fake_create)
    param = CreateSpatialCubePatternParam(code='custom', name='自定义素材')

    result = run(spatial_cube_service.create_spatial_cube_pattern(db=None, param=param, user_id=7))

    fake_create.assert_awaited_once_with(None, param, 7)
    assert result.code == 'custom'
    assert fake_redis.deleted_keys == [spatial_cube_service.SPATIAL_CUBE_PATTERN_CACHE_KEY]


def test_update_image_pattern_rejects_cleared_asset_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    验证图片素材不能清空远程 URL

    :param monkeypatch: pytest monkeypatch
    :return:
    """
    monkeypatch.setattr(
        spatial_cube_service.study_spatial_cube_pattern_dao,
        'get',
        AsyncMock(return_value=make_pattern(render_type='image', asset_url='https://example.com/pattern.webp')),
    )
    param = UpdateSpatialCubePatternParam(asset_url=None)

    with pytest.raises(errors.RequestError):
        run(spatial_cube_service.update_spatial_cube_pattern(db=None, pk=1, param=param, user_id=7))
