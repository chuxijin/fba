#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Publish generated spatial cube face patterns to object storage and database."""

from __future__ import annotations

import argparse
import asyncio
import json

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

from fastapi import UploadFile

from backend.app.study_plan.crud.crud_spatial_cube import study_spatial_cube_pattern_dao
from backend.app.study_plan.schema.spatial_cube import CreateSpatialCubePatternParam
from backend.database.db import async_db_session, async_engine
from backend.database.redis import redis_client
from backend.plugin.oss.service.storage_service import storage_service
from backend.scripts.generate_spatial_cube_patterns import PatternAsset

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.app.study_plan.model.spatial_cube import StudySpatialCubePattern


@dataclass(slots=True)
class PublishStats:
    """素材发布统计。"""

    created: int = 0
    deleted: int = 0
    updated: int = 0
    uploaded: int = 0


def load_manifest(manifest_path: Path) -> tuple[str, list[PatternAsset]]:
    """
    读取生成素材清单。

    :param manifest_path: 清单文件路径
    :return: 素材版本和素材列表
    """
    payload = json.loads(manifest_path.read_text(encoding='utf-8'))
    version = str(payload.get('version', '')).strip()
    raw_assets = payload.get('assets')
    if not version or not isinstance(raw_assets, list):
        raise ValueError('素材清单格式不正确')
    assets = [PatternAsset(**item) for item in raw_assets]
    if len(assets) != 137 or len({asset.code for asset in assets}) != len(assets):
        raise ValueError('素材清单数量或编码不正确')
    return version, assets


async def upload_asset(
    *,
    db: AsyncSession,
    manifest_dir: Path,
    asset: PatternAsset,
    version: str,
) -> str:
    """
    上传单个 WebP 素材并返回公开地址。

    :param db: 数据库会话
    :param manifest_dir: 清单所在目录
    :param asset: 素材定义
    :param version: 素材版本
    :return: 公开素材地址
    """
    webp_path = manifest_dir / asset.webp_file
    if not webp_path.is_file():
        raise FileNotFoundError(f'素材文件不存在: {webp_path}')

    upload_file = UploadFile(
        file=BytesIO(webp_path.read_bytes()),
        filename=webp_path.name,
        headers={'content-type': 'image/webp'},
    )
    try:
        url, _ = await storage_service.upload_with_filename(
            db=db,
            file=upload_file,
            filename=webp_path.name,
            path=f'study/spatial-cube-patterns/{version}',
            use_signed_url=False,
        )
        return url
    finally:
        await upload_file.close()


async def verify_public_url(url: str) -> None:
    """
    验证对象存储地址可以公开读取。

    :param url: 待验证的素材地址
    :return:
    """
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url, headers={'Range': 'bytes=0-0'})
    if response.status_code not in {200, 206}:
        raise RuntimeError(f'素材公开地址不可访问，status={response.status_code}: {url}')


async def delete_version_assets(
    *,
    db: AsyncSession,
    assets: list[PatternAsset],
    version: str,
) -> int:
    """
    删除指定旧版本的全部对象存储素材。

    :param db: 数据库会话
    :param assets: 素材定义列表
    :param version: 待删除的素材版本
    :return: 成功删除数量
    """
    runtime_config = await storage_service._load_runtime_config(db)
    deleted = 0
    for asset in assets:
        object_key = storage_service._build_object_key(
            runtime_config.key_prefix,
            f'study/spatial-cube-patterns/{version}',
            Path(asset.webp_file).name,
        )
        if not await storage_service.delete_object(db=db, object_key=object_key):
            raise RuntimeError(f'旧素材删除失败: {object_key}')
        deleted += 1
    return deleted


def build_create_param(
    *,
    asset: PatternAsset,
    asset_url: str,
    version: str,
    sort_offset: int,
) -> CreateSpatialCubePatternParam:
    """
    构建素材数据库参数。

    :param asset: 素材定义
    :param asset_url: 公开素材地址
    :param version: 素材版本
    :param sort_offset: 排序偏移量
    :return: 创建参数
    """
    return CreateSpatialCubePatternParam(
        code=asset.code,
        name=asset.name,
        render_type='image',
        asset_url=asset_url,
        asset_version=version,
        rotation_period=asset.rotation_period,
        sort=sort_offset + asset.sort,
        is_active=True,
    )


async def upsert_pattern(
    *,
    db: AsyncSession,
    existing: StudySpatialCubePattern | None,
    param: CreateSpatialCubePatternParam,
    user_id: int,
) -> bool:
    """
    按素材编码新增或更新数据库记录。

    :param db: 数据库会话
    :param existing: 已存在的素材记录
    :param param: 素材参数
    :param user_id: 操作用户 ID
    :return: 是否为新增记录
    """
    if existing is None:
        await study_spatial_cube_pattern_dao.create(db, param, user_id)
        return True

    await study_spatial_cube_pattern_dao.update(
        db,
        existing.id,
        param.model_dump(),
        user_id,
    )
    return False


async def publish_assets(
    *,
    manifest_path: Path,
    sort_offset: int,
    user_id: int,
    apply: bool,
    delete_old_version: str | None,
) -> PublishStats:
    """
    预演或发布全部六面体素材。

    :param manifest_path: 素材清单路径
    :param sort_offset: 排序偏移量
    :param user_id: 数据库操作用户 ID
    :param apply: 是否执行上传和写库
    :param delete_old_version: 发布成功后删除的旧素材版本
    :return: 发布统计
    """
    version, assets = load_manifest(manifest_path)
    if delete_old_version == version:
        raise ValueError('不能删除当前正在发布的素材版本')
    stats = PublishStats()
    published_rows: list[dict[str, Any]] = []
    async with async_db_session.begin() as db:
        current_patterns = await study_spatial_cube_pattern_dao.get_all(db, include_inactive=True)
        existing_by_code = {pattern.code: pattern for pattern in current_patterns}
        stats.created = sum(asset.code not in existing_by_code for asset in assets)
        stats.updated = len(assets) - stats.created
        if not apply:
            return stats

        for index, asset in enumerate(assets):
            asset_url = await upload_asset(
                db=db,
                manifest_dir=manifest_path.parent,
                asset=asset,
                version=version,
            )
            if index == 0:
                await verify_public_url(asset_url)
            param = build_create_param(
                asset=asset,
                asset_url=asset_url,
                version=version,
                sort_offset=sort_offset,
            )
            await upsert_pattern(
                db=db,
                existing=existing_by_code.get(asset.code),
                param=param,
                user_id=user_id,
            )
            published_rows.append({**param.model_dump(), 'category': asset.category})
            stats.uploaded += 1

    await redis_client.delete('study:spatial_cube:patterns:active:v1')
    published_manifest = {
        'version': version,
        'assets': published_rows,
    }
    (manifest_path.parent / 'published-manifest.json').write_text(
        json.dumps(published_manifest, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    if delete_old_version:
        async with async_db_session() as db:
            stats.deleted = await delete_version_assets(
                db=db,
                assets=assets,
                version=delete_old_version,
            )
    return stats


def parse_args() -> argparse.Namespace:
    """解析发布参数。"""
    parser = argparse.ArgumentParser(description='发布六面体面素材到 OSS 和数据库')
    parser.add_argument(
        '--manifest',
        type=Path,
        default=Path('assets/spatial-cube-patterns/generated-v1/manifest.json'),
        help='生成素材清单路径',
    )
    parser.add_argument('--sort-offset', type=int, default=100, help='数据库排序偏移量')
    parser.add_argument('--user-id', type=int, default=0, help='数据库操作用户 ID')
    parser.add_argument('--delete-old-version', help='发布成功后删除指定旧版本 OSS 素材')
    parser.add_argument('--apply', action='store_true', help='执行上传和数据库写入')
    return parser.parse_args()


async def async_main() -> None:
    """执行素材发布命令。"""
    args = parse_args()
    try:
        stats = await publish_assets(
            manifest_path=args.manifest,
            sort_offset=args.sort_offset,
            user_id=args.user_id,
            apply=args.apply,
            delete_old_version=args.delete_old_version,
        )
        mode = 'apply' if args.apply else 'dry-run'
        print(
            f'mode={mode} created={stats.created} updated={stats.updated} '
            f'uploaded={stats.uploaded} deleted={stats.deleted}',
        )
    finally:
        await async_engine.dispose()


def main() -> None:
    """运行异步发布流程。"""
    asyncio.run(async_main())


if __name__ == '__main__':
    main()
