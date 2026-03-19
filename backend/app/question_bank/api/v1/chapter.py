#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.question_bank.schema.chapter import (
    CreateChapterParam,
    DeleteChapterParam,
    GetChapterDetail,
    GetChapterTree,
    UpdateChapterParam,
)
from backend.app.question_bank.security import DependsCurrentUser
from backend.app.question_bank.service.chapter_service import chapter_service
from backend.app.question_bank.service.membership_service import membership_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取章节详情', name='qbank_get_chapter')
async def get_chapter(
    db: CurrentSession,
    pk: Annotated[int, Path(description='章节 ID')],
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[GetChapterDetail]:
    """👤 客户接口 - 需要登录且开通会员后查看章节详情"""
    await membership_service.verify_chapter_access(db=db, user_id=current_user.user_id, chapter_id=pk)
    data = await chapter_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '/tree/customer',
    summary='获取章节树（客户端）',
    name='qbank_get_chapter_tree_customer',
)
async def get_chapter_tree_customer(
    db: CurrentSession,
    bank_id: Annotated[int, Query(description='题库 ID')],
) -> ResponseSchemaModel[list[GetChapterTree]]:
    """
    👤 客户端接口 - 查看题库章节树（公开）

    :param db: 数据库会话
    :param bank_id: 题库 ID
    :return: 章节树列表
    """
    tree = await chapter_service.get_tree(db=db, bank_id=bank_id)
    return response_base.success(data=tree)


@router.get(
    '',
    summary='获取章节树',
    name='qbank_get_chapter_tree',
    dependencies=[DependsRBAC],
)
async def get_chapter_tree(
    db: CurrentSession,
    bank_id: Annotated[int, Query(description='题库 ID')],
) -> ResponseSchemaModel[list[GetChapterTree]]:
    """🔐 管理员接口 - 管理员可以查看章节树"""
    tree = await chapter_service.get_tree(db=db, bank_id=bank_id)
    return response_base.success(data=tree)


@router.post(
    '',
    summary='创建章节',
    name='qbank_create_chapter',
    dependencies=[DependsRBAC],
)
async def create_chapter(db: CurrentSessionTransaction, obj: CreateChapterParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以创建章节"""
    await chapter_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新章节',
    name='qbank_update_chapter',
    dependencies=[DependsRBAC],
)
async def update_chapter(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='章节 ID')], obj: UpdateChapterParam
) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以更新章节"""
    count = await chapter_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除章节',
    name='qbank_delete_chapter',
    dependencies=[DependsRBAC],
)
async def delete_chapter(db: CurrentSessionTransaction, obj: DeleteChapterParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以删除章节"""
    count = await chapter_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()

