#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.jia.schema.tag import CreateTagParam, DeleteTagParam, GetTagDetail, UpdateTagParam
from backend.app.jia.service.tag_service import tag_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取标签详情', dependencies=[DependsJwtAuth])
async def get_jia_tag(
    db: CurrentSession, pk: Annotated[int, Path(description='标签 ID')]
) -> ResponseSchemaModel[GetTagDetail]:
    data = await tag_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取标签列表', dependencies=[DependsJwtAuth])
async def get_jia_tag_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='标签名称')] = None,
    sync_status: Annotated[str | None, Query(description='同步状态')] = None,
) -> ResponseSchemaModel[list[GetTagDetail]]:
    data = await tag_service.get_list(db=db, name=name, sync_status=sync_status)
    return response_base.success(data=data)


@router.get('/all', summary='获取所有标签', dependencies=[DependsJwtAuth])
async def get_all_jia_tags(db: CurrentSession, request: Request) -> ResponseSchemaModel[list[GetTagDetail]]:
    data = await tag_service.get_all(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('', summary='创建标签', dependencies=[DependsJwtAuth])
async def create_jia_tag(db: CurrentSessionTransaction, request: Request, obj: CreateTagParam) -> ResponseModel:
    await tag_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put('/{pk}', summary='更新标签', dependencies=[DependsJwtAuth])
async def update_jia_tag(
    db: CurrentSessionTransaction,
    request: Request,
    pk: Annotated[int, Path(description='标签 ID')],
    obj: UpdateTagParam,
) -> ResponseModel:
    count = await tag_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='批量删除标签', dependencies=[DependsJwtAuth])
async def delete_jia_tag(db: CurrentSessionTransaction, obj: DeleteTagParam) -> ResponseModel:
    count = await tag_service.delete(db=db, pks=obj.pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()

