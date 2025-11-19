#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.jia.schema.note import (
    CreateNoteParam,
    DeleteNoteParam,
    GetNoteDetail,
    UpdateNoteParam,
)
from backend.app.jia.service.note_service import note_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取笔记详情', dependencies=[DependsJwtAuth])
async def get_jia_note(
    db: CurrentSession, pk: Annotated[int, Path(description='笔记 ID')]
) -> ResponseSchemaModel[GetNoteDetail]:
    data = await note_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取笔记列表', dependencies=[DependsJwtAuth])
async def get_jia_note_list(
    db: CurrentSession,
    type: Annotated[str | None, Query(description='类型')] = None,
    parent_id: Annotated[int | None, Query(description='父级 ID')] = None,
    name: Annotated[str | None, Query(description='名称')] = None,
    is_pinned: Annotated[int | None, Query(description='是否置顶')] = None,
    is_favorite: Annotated[int | None, Query(description='是否收藏')] = None,
    sync_status: Annotated[str | None, Query(description='同步状态')] = None,
) -> ResponseSchemaModel[list[GetNoteDetail]]:
    data = await note_service.get_list(
        db=db,
        type=type,
        parent_id=parent_id,
        name=name,
        is_pinned=is_pinned,
        is_favorite=is_favorite,
        sync_status=sync_status,
    )
    return response_base.success(data=data)


@router.get('/{pk}/children', summary='获取子笔记/文件夹列表', dependencies=[DependsJwtAuth])
async def get_jia_note_children(
    db: CurrentSession, pk: Annotated[int, Path(description='父级 ID')]
) -> ResponseSchemaModel[list[GetNoteDetail]]:
    data = await note_service.get_children(db=db, parent_id=pk)
    return response_base.success(data=data)


@router.post('', summary='创建笔记', dependencies=[DependsJwtAuth])
async def create_jia_note(
    db: CurrentSessionTransaction, request: Request, obj: CreateNoteParam
) -> ResponseModel:
    await note_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put('/{pk}', summary='更新笔记', dependencies=[DependsJwtAuth])
async def update_jia_note(
    db: CurrentSessionTransaction,
    request: Request,
    pk: Annotated[int, Path(description='笔记 ID')],
    obj: UpdateNoteParam,
) -> ResponseModel:
    count = await note_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='批量删除笔记', dependencies=[DependsJwtAuth])
async def delete_jia_note(db: CurrentSessionTransaction, obj: DeleteNoteParam) -> ResponseModel:
    count = await note_service.delete(db=db, pks=obj.pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()

