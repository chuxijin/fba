#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.question_bank.crud.crud_membership import membership_dao
from backend.app.question_bank.schema.membership import (
    CreateMembershipParam,
    DeleteMembershipParam,
    GetMembershipDetail,
    UpdateMembershipParam,
)
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取会员权益详情', name='qbank_get_membership', dependencies=[DependsRBAC])
async def get_membership(
    db: CurrentSession, pk: Annotated[int, Path(description='会员权益 ID')]
) -> ResponseSchemaModel[GetMembershipDetail]:
    """🔐 管理员接口 - 查看会员权益详情"""
    membership = await membership_dao.get(db, pk)
    if not membership:
        return response_base.fail(msg='会员权益不存在')
    return response_base.success(data=membership)


@router.get('', summary='获取会员权益列表', name='qbank_get_membership_list', dependencies=[DependsRBAC])
async def get_membership_list(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    category: Annotated[int | None, Query(description='会员分类')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetMembershipDetail]]:
    """🔐 管理员接口 - 查看会员权益列表"""
    memberships = await membership_dao.get_list(db=db, user_id=user_id, category=category, status=status)
    return response_base.success(data=memberships)


@router.post(
    '',
    summary='创建会员权益',
    name='qbank_create_membership',
    dependencies=[
        Depends(RequestPermission('question_bank:membership:create')),
        DependsRBAC,
    ],
)
async def create_membership(db: CurrentSessionTransaction, obj: CreateMembershipParam) -> ResponseModel:
    """🔐 管理员接口 - 为用户开通会员权益"""
    await membership_dao.create(db, obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新会员权益',
    name='qbank_update_membership',
    dependencies=[
        Depends(RequestPermission('question_bank:membership:update')),
        DependsRBAC,
    ],
)
async def update_membership(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='会员权益 ID')], obj: UpdateMembershipParam
) -> ResponseModel:
    """🔐 管理员接口 - 更新会员权益（如延期、禁用等）"""
    count = await membership_dao.update(db, pk, obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除会员权益',
    name='qbank_delete_membership',
    dependencies=[
        Depends(RequestPermission('question_bank:membership:delete')),
        DependsRBAC,
    ],
)
async def delete_membership(db: CurrentSessionTransaction, obj: DeleteMembershipParam) -> ResponseModel:
    """🔐 管理员接口 - 删除会员权益"""
    count = await membership_dao.delete(db, obj.ids)
    if count > 0:
        return response_base.success()
    return response_base.fail()
