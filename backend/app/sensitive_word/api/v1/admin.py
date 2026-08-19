#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.sensitive_word.schema.sensitive_word import (
    CreateSensitiveWordParam,
    GetSensitiveWordDetail,
    UpdateSensitiveWordParam,
)
from backend.app.sensitive_word.service.sensitive_word_service import sensitive_word_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/sensitive-words/admin', tags=['敏感词管理'], dependencies=[DependsJwtAuth])

# 处理方式 可选项，供前端展示
SENSITIVE_ACTION_OPTIONS = [
    {'label': '替换', 'value': 'replace'},
    {'label': '屏蔽打码', 'value': 'block'},
    {'label': '拦截拒绝', 'value': 'reject'},
]


@router.get('/options', summary='敏感词处理方式选项', name='sensitive_admin_get_options')
async def get_action_options() -> ResponseSchemaModel[list[dict[str, str]]]:
    """返回敏感词处理方式选项"""
    return response_base.success(data=SENSITIVE_ACTION_OPTIONS)


@router.post('/words', summary='创建敏感词', name='sensitive_admin_create_word')
async def create_word(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateSensitiveWordParam,
) -> ResponseSchemaModel[GetSensitiveWordDetail]:
    """创建敏感词"""
    data = await sensitive_word_service.create(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get('/words', summary='敏感词分页列表', name='sensitive_admin_get_words', dependencies=[DependsPagination])
async def get_word_list(
    db: CurrentSession,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
    action: Annotated[str | None, Query(description='处理方式')] = None,
) -> ResponseModel:
    """获取敏感词分页列表"""
    data = await sensitive_word_service.page_words(db=db, keyword=keyword, status=status, action=action)
    return response_base.success(data=data)


@router.put('/words/{pk}', summary='更新敏感词', name='sensitive_admin_update_word')
async def update_word(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='敏感词 ID')],
    obj: UpdateSensitiveWordParam,
) -> ResponseModel:
    """更新敏感词"""
    count = await sensitive_word_service.update(db=db, pk=pk, obj=obj)
    return response_base.success(data={'updated': count})


@router.delete('/words/{pk}', summary='删除敏感词', name='sensitive_admin_delete_word')
async def delete_word(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='敏感词 ID')],
) -> ResponseModel:
    """删除敏感词"""
    count = await sensitive_word_service.delete(db=db, pk=pk)
    return response_base.success(data={'deleted': count})


# ============ 命中日志 ============
@router.get('/hits', summary='敏感词命中日志', name='sensitive_admin_get_hits', dependencies=[DependsPagination])
async def get_hit_log_list(
    db: CurrentSession,
    keyword: Annotated[str | None, Query(description='搜索关键词')] = None,
    action: Annotated[str | None, Query(description='处理方式')] = None,
    user_id: Annotated[int | None, Query(gt=0, description='用户 ID')] = None,
    target_type: Annotated[str | None, Query(description='内容类型')] = None,
) -> ResponseModel:
    """获取敏感词命中日志分页列表"""
    data = await sensitive_word_service.page_hits(
        db=db,
        keyword=keyword,
        action=action,
        user_id=user_id,
        target_type=target_type,
    )
    return response_base.success(data=data)
