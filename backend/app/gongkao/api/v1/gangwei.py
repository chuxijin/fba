#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, File, Path, Query, Request, UploadFile

from backend.app.gongkao.schema.gangwei import (
    CreateGangweiParam,
    DeleteGangweiParam,
    GangweiParam,
    GetGangweiDetail,
    ImportGangweiResult,
    UpdateGangweiParam,
)
from backend.app.gongkao.service.gangwei_service import gangwei_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取岗位详情')
async def get_gangwei(
    db: CurrentSession,
    pk: Annotated[int, Path(description='岗位 ID')],
) -> ResponseSchemaModel[GetGangweiDetail]:
    """获取岗位详情"""
    data = await gangwei_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取岗位列表')
async def get_gangwei_list(
    db: CurrentSession,
    year: Annotated[int | None, Query(description='年度')] = None,
    org_name: Annotated[str | None, Query(description='单位名称')] = None,
    org_region: Annotated[str | None, Query(description='单位所属地区')] = None,
    position_name: Annotated[str | None, Query(description='职位名称')] = None,
    position_code: Annotated[str | None, Query(description='职位代码')] = None,
    page: Annotated[int, Query(ge=1, description='页码')] = 1,
    size: Annotated[int, Query(ge=1, le=100, description='每页数量')] = 20,
) -> ResponseSchemaModel[dict]:
    """获取岗位列表（分页）"""
    params = GangweiParam(
        year=year,
        org_name=org_name,
        org_region=org_region,
        position_name=position_name,
        position_code=position_code,
    )
    offset = (page - 1) * size
    total, data = await gangwei_service.get_list(db=db, params=params, offset=offset, limit=size)
    return response_base.success(
        data={
            'items': [GetGangweiDetail.model_validate(item) for item in data],
            'total': total,
            'page': page,
            'size': size,
        }
    )


@router.post(
    '',
    summary='创建岗位',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:create')),
        DependsRBAC,
    ],
)
async def create_gangwei(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateGangweiParam,
) -> ResponseModel:
    """创建岗位"""
    await gangwei_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新岗位',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:update')),
        DependsRBAC,
    ],
)
async def update_gangwei(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='岗位 ID')],
    obj: UpdateGangweiParam,
) -> ResponseModel:
    """更新岗位"""
    count = await gangwei_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除岗位',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:delete')),
        DependsRBAC,
    ],
)
async def delete_gangwei(db: CurrentSessionTransaction, obj: DeleteGangweiParam) -> ResponseModel:
    """删除岗位"""
    count = await gangwei_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post(
    '/import',
    summary='批量导入岗位',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:import')),
        DependsRBAC,
    ],
)
async def import_gangwei(
    request: Request,
    db: CurrentSessionTransaction,
    file: UploadFile = File(..., description='Excel 或 CSV 文件'),
) -> ResponseSchemaModel[ImportGangweiResult]:
    """批量导入岗位（支持 Excel、CSV 格式）"""
    result = await gangwei_service.import_from_file(db=db, file=file, created_by=request.user.id)
    return response_base.success(data=result)
