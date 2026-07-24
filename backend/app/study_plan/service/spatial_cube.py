#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.study_plan.crud.crud_spatial_cube import study_spatial_cube_pattern_dao
from backend.app.study_plan.model.spatial_cube import StudySpatialCubePattern
from backend.app.study_plan.schema.spatial_cube import (
    CreateSpatialCubePatternParam,
    GetSpatialCubePatternCatalog,
    GetSpatialCubePatternDetail,
    UpdateSpatialCubePatternParam,
)
from backend.common.exception import errors
from backend.database.redis import redis_client

SPATIAL_CUBE_PATTERN_CACHE_KEY = 'study:spatial_cube:patterns:active:v1'
SPATIAL_CUBE_PATTERN_CACHE_TTL = 600


def _validate_pattern(render_type: str, asset_url: str | None) -> None:
    """
    校验面素材渲染配置

    :param render_type: 渲染类型
    :param asset_url: 远程素材 URL
    :return:
    """
    if render_type == 'image' and not asset_url:
        raise errors.RequestError(msg='图片素材必须配置远程素材 URL')


def _build_catalog(patterns: list[StudySpatialCubePattern]) -> GetSpatialCubePatternCatalog:
    """
    构建面素材清单

    :param patterns: 面素材模型列表
    :return:
    """
    details = [GetSpatialCubePatternDetail.model_validate(pattern) for pattern in patterns]
    version_parts = [
        f'{pattern.id}:{pattern.asset_version}:{pattern.updated_time.isoformat() if pattern.updated_time else ""}'
        for pattern in patterns
    ]
    return GetSpatialCubePatternCatalog(version='|'.join(version_parts) or 'empty', patterns=details)


async def get_spatial_cube_pattern_catalog(*, db: AsyncSession) -> GetSpatialCubePatternCatalog:
    """
    获取启用的六面体面素材清单

    :param db: 数据库会话
    :return:
    """
    cached_catalog = await redis_client.get(SPATIAL_CUBE_PATTERN_CACHE_KEY)
    if cached_catalog:
        return GetSpatialCubePatternCatalog.model_validate_json(cached_catalog)

    patterns = list(await study_spatial_cube_pattern_dao.get_all(db, include_inactive=False))
    catalog = _build_catalog(patterns)
    await redis_client.set(
        SPATIAL_CUBE_PATTERN_CACHE_KEY,
        catalog.model_dump_json(),
        ex=SPATIAL_CUBE_PATTERN_CACHE_TTL,
    )
    return catalog


async def get_all_spatial_cube_patterns(*, db: AsyncSession) -> list[GetSpatialCubePatternDetail]:
    """
    获取全部六面体面素材

    :param db: 数据库会话
    :return:
    """
    patterns = await study_spatial_cube_pattern_dao.get_all(db, include_inactive=True)
    return [GetSpatialCubePatternDetail.model_validate(pattern) for pattern in patterns]


async def create_spatial_cube_pattern(
    *,
    db: AsyncSession,
    param: CreateSpatialCubePatternParam,
    user_id: int,
) -> GetSpatialCubePatternDetail:
    """
    创建六面体面素材

    :param db: 数据库会话
    :param param: 创建参数
    :param user_id: 创建者 ID
    :return:
    """
    if await study_spatial_cube_pattern_dao.get_by_code(db, param.code):
        raise errors.ConflictError(msg='面素材编码已存在')
    _validate_pattern(param.render_type, param.asset_url)
    pattern = await study_spatial_cube_pattern_dao.create(db, param, user_id)
    await redis_client.delete(SPATIAL_CUBE_PATTERN_CACHE_KEY)
    return GetSpatialCubePatternDetail.model_validate(pattern)


async def update_spatial_cube_pattern(
    *,
    db: AsyncSession,
    pk: int,
    param: UpdateSpatialCubePatternParam,
    user_id: int,
) -> GetSpatialCubePatternDetail:
    """
    更新六面体面素材

    :param db: 数据库会话
    :param pk: 素材 ID
    :param param: 更新参数
    :param user_id: 修改者 ID
    :return:
    """
    pattern = await study_spatial_cube_pattern_dao.get(db, pk)
    if not pattern:
        raise errors.NotFoundError(msg='面素材不存在')
    if param.code and param.code != pattern.code:
        existing = await study_spatial_cube_pattern_dao.get_by_code(db, param.code)
        if existing:
            raise errors.ConflictError(msg='面素材编码已存在')

    data = param.model_dump(exclude_unset=True)
    render_type = str(data.get('render_type', pattern.render_type))
    asset_url_value = data.get('asset_url', pattern.asset_url)
    asset_url = str(asset_url_value) if asset_url_value else None
    _validate_pattern(render_type, asset_url)
    await study_spatial_cube_pattern_dao.update(db, pk, data, user_id)
    await db.refresh(pattern)
    await redis_client.delete(SPATIAL_CUBE_PATTERN_CACHE_KEY)
    return GetSpatialCubePatternDetail.model_validate(pattern)


async def delete_spatial_cube_pattern(*, db: AsyncSession, pk: int) -> None:
    """
    删除六面体面素材

    :param db: 数据库会话
    :param pk: 素材 ID
    :return:
    """
    pattern = await study_spatial_cube_pattern_dao.get(db, pk)
    if not pattern:
        raise errors.NotFoundError(msg='面素材不存在')
    await study_spatial_cube_pattern_dao.delete(db, pk)
    await redis_client.delete(SPATIAL_CUBE_PATTERN_CACHE_KEY)
