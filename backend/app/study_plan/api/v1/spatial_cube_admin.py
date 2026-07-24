#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.study_plan.crud.crud_spatial_cube import study_spatial_cube_pattern_dao
from backend.app.study_plan.schema.spatial_cube import (
    CreateSpatialCubePatternParam,
    GetSpatialCubePatternDetail,
    SpatialCubePatternRenderType,
    UpdateSpatialCubePatternParam,
)
from backend.app.study_plan.service.spatial_cube import (
    create_spatial_cube_pattern,
    delete_spatial_cube_pattern,
    update_spatial_cube_pattern,
)
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/patterns',
    summary='分页获取六面体面素材',
    dependencies=[Depends(RequestPermission('study_plan:admin:read')), DependsRBAC, DependsPagination],
)
async def get_spatial_cube_patterns_page_api(
    db: CurrentSession,
    keyword: Annotated[str | None, Query(description='名称、编码或素材地址关键词')] = None,
    render_type: Annotated[SpatialCubePatternRenderType | None, Query(description='渲染类型')] = None,
    status: Annotated[Literal['active', 'inactive'] | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetSpatialCubePatternDetail]]:
    """
    分页获取六面体面素材

    :param db: 数据库会话
    :param keyword: 名称、编码或素材地址关键词
    :param render_type: 渲染类型
    :param status: 状态
    :return:
    """
    is_active = None
    if status is not None:
        is_active = status == 'active'
    stmt = study_spatial_cube_pattern_dao.get_select(
        include_inactive=True,
        keyword=keyword,
        render_type=render_type,
        is_active=is_active,
    )
    page_data = await paging_data(db, stmt, schema_cls=GetSpatialCubePatternDetail)
    return response_base.success(data=page_data)


@router.post(
    '/patterns',
    summary='创建六面体面素材',
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def create_spatial_cube_pattern_api(
    request: Request,
    db: CurrentSessionTransaction,
    param: CreateSpatialCubePatternParam,
) -> ResponseSchemaModel[GetSpatialCubePatternDetail]:
    """
    创建六面体面素材

    :param request: 请求对象
    :param db: 数据库事务会话
    :param param: 创建参数
    :return:
    """
    pattern = await create_spatial_cube_pattern(db=db, param=param, user_id=request.user.id)
    return response_base.success(data=pattern)


@router.put(
    '/patterns/{pk}',
    summary='更新六面体面素材',
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def update_spatial_cube_pattern_api(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='素材 ID')],
    param: UpdateSpatialCubePatternParam,
) -> ResponseSchemaModel[GetSpatialCubePatternDetail]:
    """
    更新六面体面素材

    :param request: 请求对象
    :param db: 数据库事务会话
    :param pk: 素材 ID
    :param param: 更新参数
    :return:
    """
    pattern = await update_spatial_cube_pattern(db=db, pk=pk, param=param, user_id=request.user.id)
    return response_base.success(data=pattern)


@router.delete(
    '/patterns/{pk}',
    summary='删除六面体面素材',
    dependencies=[Depends(RequestPermission('study_plan:admin:write')), DependsRBAC],
)
async def delete_spatial_cube_pattern_api(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='素材 ID')],
) -> ResponseModel:
    """
    删除六面体面素材

    :param db: 数据库事务会话
    :param pk: 素材 ID
    :return:
    """
    await delete_spatial_cube_pattern(db=db, pk=pk)
    return response_base.success()
