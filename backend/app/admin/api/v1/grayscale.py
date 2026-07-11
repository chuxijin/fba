#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Path

from backend.app.admin.schema.grayscale import GrayscaleConfigSchema, GrayscaleListResponse
from backend.common.grayscale import GrayscaleConfig, delete_config, list_configs, set_config
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth

router = APIRouter(prefix='/grayscale', dependencies=[DependsJwtAuth])


@router.get('', summary='列出所有灰度配置', response_model=ResponseSchemaModel[GrayscaleListResponse])
async def grayscale_list() -> ResponseSchemaModel[GrayscaleListResponse]:
    configs = await list_configs()
    features = [
        {
            'feature': feature,
            'enabled': cfg.enabled,
            'whitelist': cfg.whitelist,
            'ratio': cfg.ratio,
        }
        for feature, cfg in configs.items()
    ]
    return response_base.success(data=GrayscaleListResponse(features=features))


@router.get('/{feature}', summary='查看单个灰度配置', response_model=ResponseSchemaModel[GrayscaleConfigSchema])
async def grayscale_get(
    feature: str = Path(description='功能名称'),
) -> ResponseSchemaModel[GrayscaleConfigSchema]:
    from backend.common.grayscale import get_config

    config = await get_config(feature)
    if config is None:
        return response_base.success(
            data=GrayscaleConfigSchema(enabled=True, whitelist=[], ratio=0.0),
        )
    return response_base.success(
        data=GrayscaleConfigSchema(
            enabled=config.enabled,
            whitelist=config.whitelist,
            ratio=config.ratio,
        ),
    )


@router.put('/{feature}', summary='创建或更新灰度配置', response_model=ResponseModel)
async def grayscale_put(
    body: GrayscaleConfigSchema,
    feature: str = Path(description='功能名称'),
) -> ResponseModel:
    await set_config(
        feature,
        GrayscaleConfig(enabled=body.enabled, whitelist=body.whitelist, ratio=body.ratio),
    )
    return response_base.success()


@router.delete('/{feature}', summary='删除灰度配置（全量上线）', response_model=ResponseModel)
async def grayscale_delete(
    feature: str = Path(description='功能名称'),
) -> ResponseModel:
    await delete_config(feature)
    return response_base.success()