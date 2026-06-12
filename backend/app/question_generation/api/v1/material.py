#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_generation.schema import (
    CreateMaterialParam,
    DeleteMaterialParam,
    GetMaterialDetail,
    GetMaterialListItem,
    MaterialQueryParam,
    UpdateMaterialParam,
)
from backend.app.question_generation.service import question_generation_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='获取出题素材列表',
    dependencies=[Depends(RequestPermission('question_generation:material:read')), DependsRBAC],
)
async def get_material_list(
    db: CurrentSession,
    exam: Annotated[str | None, Query(description='考试标识')] = None,
    subject: Annotated[str | None, Query(description='科目标识')] = None,
    section: Annotated[str | None, Query(description='模块标识')] = None,
    status: Annotated[str | None, Query(description='素材状态')] = None,
    keyword: Annotated[str | None, Query(description='关键字')] = None,
) -> ResponseSchemaModel[list[GetMaterialListItem]]:
    """
    获取出题素材列表

    :param db: 数据库会话
    :param exam: 考试标识
    :param subject: 科目标识
    :param section: 模块标识
    :param status: 素材状态
    :param keyword: 关键字
    :return:
    """
    params = MaterialQueryParam(
        exam=exam,
        subject=subject,
        section=section,
        status=status,
        keyword=keyword,
    )
    data = await question_generation_service.get_material_list(db=db, params=params)
    return response_base.success(data=data)


@router.get(
    '/{pk}',
    summary='获取出题素材详情',
    dependencies=[Depends(RequestPermission('question_generation:material:read')), DependsRBAC],
)
async def get_material(
    db: CurrentSession,
    pk: Annotated[int, Path(description='素材 ID')],
) -> ResponseSchemaModel[GetMaterialDetail]:
    """
    获取出题素材详情

    :param db: 数据库会话
    :param pk: 素材 ID
    :return:
    """
    data = await question_generation_service.get_material(db=db, pk=pk)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建出题素材',
    dependencies=[Depends(RequestPermission('question_generation:material:write')), DependsRBAC],
)
async def create_material(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateMaterialParam,
) -> ResponseSchemaModel[GetMaterialDetail]:
    """
    创建出题素材

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 创建参数
    :return:
    """
    data = await question_generation_service.create_material(
        db=db,
        obj=obj,
        created_by=request.user.id,
    )
    return response_base.success(data=data)


@router.put(
    '/{pk}',
    summary='更新出题素材',
    dependencies=[Depends(RequestPermission('question_generation:material:write')), DependsRBAC],
)
async def update_material(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='素材 ID')],
    obj: UpdateMaterialParam,
) -> ResponseModel:
    """
    更新出题素材

    :param request: 请求对象
    :param db: 数据库会话
    :param pk: 素材 ID
    :param obj: 更新参数
    :return:
    """
    count = await question_generation_service.update_material(
        db=db,
        pk=pk,
        obj=obj,
        updated_by=request.user.id,
    )
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除出题素材',
    dependencies=[Depends(RequestPermission('question_generation:material:delete')), DependsRBAC],
)
async def delete_material(
    db: CurrentSessionTransaction,
    obj: DeleteMaterialParam,
) -> ResponseModel:
    """
    删除出题素材

    :param db: 数据库会话
    :param obj: 删除参数
    :return:
    """
    count = await question_generation_service.delete_material(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
