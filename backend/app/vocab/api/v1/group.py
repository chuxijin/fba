#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.vocab.schema.group import (
    CreateGroupParam,
    GetGroupDetail,
    GroupAddWordsParam,
    GroupRemoveWordsParam,
    UpdateGroupParam,
)
from backend.app.vocab.service.group_service import group_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/vocab/groups', tags=['学习组'], dependencies=[DependsJwtAuth])


@router.post('', summary='创建学习组')
async def create_group(
    request: Request, db: CurrentSession, obj: CreateGroupParam
) -> ResponseSchemaModel[GetGroupDetail]:
    """创建学习组"""
    data = await group_service.create_group(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.put('/{pk}', summary='更新学习组')
async def update_group(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='学习组 ID')],
    obj: UpdateGroupParam,
) -> ResponseModel:
    """更新学习组"""
    count = await group_service.update_group(db=db, pk=pk, user_id=request.user.id, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/{pk}', summary='删除学习组')
async def delete_group(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='学习组 ID')],
) -> ResponseModel:
    """删除学习组"""
    count = await group_service.delete_group(db=db, pk=pk, user_id=request.user.id)
    return response_base.success(data={'deleted': count})


@router.get('', summary='我的学习组列表', dependencies=[DependsPagination])
async def get_group_list(request: Request, db: CurrentSession) -> ResponseModel:
    """获取我的学习组列表"""
    data = await group_service.get_group_list(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/{pk}/words', summary='添加单词到学习组')
async def add_words_to_group(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='学习组 ID')],
    obj: GroupAddWordsParam,
) -> ResponseModel:
    """向学习组添加单词"""
    count = await group_service.add_words(db=db, pk=pk, user_id=request.user.id, obj=obj)
    return response_base.success(data={'added': count})


@router.delete('/{pk}/words', summary='从学习组移除单词')
async def remove_words_from_group(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='学习组 ID')],
    obj: GroupRemoveWordsParam,
) -> ResponseModel:
    """从学习组移除单词"""
    count = await group_service.remove_words(db=db, pk=pk, user_id=request.user.id, word_ids=obj.word_ids)
    return response_base.success(data={'removed': count})
