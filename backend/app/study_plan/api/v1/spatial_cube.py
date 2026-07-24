#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.study_plan.schema.spatial_cube import GetSpatialCubePatternCatalog
from backend.app.study_plan.service.spatial_cube import get_spatial_cube_pattern_catalog
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/patterns',
    summary='获取六面体面素材清单',
)
async def get_spatial_cube_patterns(db: CurrentSession) -> ResponseSchemaModel[GetSpatialCubePatternCatalog]:
    """
    获取六面体面素材清单

    :param db: 数据库会话
    :return:
    """
    catalog = await get_spatial_cube_pattern_catalog(db=db)
    return response_base.success(data=catalog)
