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
    ImportScoreResult,
    ImportWithMappingParam,
    UpdateGangweiParam,
)
from backend.app.gongkao.service.gangwei_service import gangwei_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
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
    exam_type: Annotated[str | None, Query(description='考试类型')] = None,
    region: Annotated[str | None, Query(description='所属地区')] = None,
    dept_name: Annotated[str | None, Query(description='部门名称')] = None,
    position_name: Annotated[str | None, Query(description='职位名称')] = None,
    position_code: Annotated[str | None, Query(description='职位代码')] = None,
    page: Annotated[int, Query(ge=1, description='页码')] = 1,
    size: Annotated[int, Query(ge=1, le=100, description='每页数量')] = 20,
) -> ResponseSchemaModel[dict]:
    """获取岗位列表（分页）"""
    params = GangweiParam(
        year=year,
        exam_type=exam_type,
        region=region,
        dept_name=dept_name,
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
    '/import/parse',
    summary='解析导入文件表头',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:import')),
        DependsRBAC,
    ],
)
async def parse_import_file(
    file: Annotated[UploadFile, File(description='Excel 或 CSV 文件')],
) -> ResponseSchemaModel[dict]:
    """
    解析上传文件的表头，返回表头列表、预览数据和智能匹配建议

    用于导入前的字段映射配置
    """
    result = await gangwei_service.parse_file_header(file=file)
    return response_base.success(data=result)


@router.post(
    '/import/reparse',
    summary='重新解析表头',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:import')),
        DependsRBAC,
    ],
)
async def reparse_import_file(
    file_key: Annotated[str, Query(description='临时文件标识')],
    header_row: Annotated[int, Query(ge=0, le=20, description='表头所在行（0 开始）')] = 0,
) -> ResponseSchemaModel[dict]:
    """使用指定的表头行重新解析已上传的文件"""
    result = await gangwei_service.reparse_file_header(file_key=file_key, header_row=header_row)
    return response_base.success(data=result)


@router.post(
    '/import/execute',
    summary='执行带映射的导入',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:import')),
        DependsRBAC,
    ],
)
async def execute_import_with_mapping(
    request: Request,
    db: CurrentSessionTransaction,
    obj: ImportWithMappingParam,
) -> ResponseSchemaModel[ImportGangweiResult]:
    """使用用户指定的字段映射关系执行导入"""
    result = await gangwei_service.import_with_mapping(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=result)


# ==================== 分数导入 ====================


@router.post(
    '/score/import/parse',
    summary='解析分数导入文件表头',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:import')),
        DependsRBAC,
    ],
)
async def parse_score_import_file(
    file: Annotated[UploadFile, File(description='Excel 或 CSV 文件')],
) -> ResponseSchemaModel[dict]:
    """解析分数导入文件的表头，返回表头列表、预览数据和智能匹配建议"""
    result = await gangwei_service.parse_score_file_header(file=file)
    return response_base.success(data=result)


@router.post(
    '/score/import/reparse',
    summary='重新解析分数导入表头',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:import')),
        DependsRBAC,
    ],
)
async def reparse_score_import_file(
    file_key: Annotated[str, Query(description='临时文件标识')],
    header_row: Annotated[int, Query(ge=0, le=20, description='表头所在行（0 开始）')] = 0,
) -> ResponseSchemaModel[dict]:
    """使用指定的表头行重新解析已上传的分数文件"""
    result = await gangwei_service.reparse_score_file_header(file_key=file_key, header_row=header_row)
    return response_base.success(data=result)


@router.post(
    '/score/import/execute',
    summary='执行分数导入',
    dependencies=[
        Depends(RequestPermission('gongkao:gangwei:import')),
        DependsRBAC,
    ],
)
async def execute_score_import_with_mapping(
    request: Request,
    db: CurrentSessionTransaction,
    obj: ImportWithMappingParam,
) -> ResponseSchemaModel[ImportScoreResult]:
    """使用用户指定的字段映射关系执行分数导入"""
    result = await gangwei_service.import_scores_with_mapping(db=db, obj=obj, updated_by=request.user.id)
    return response_base.success(data=result)
