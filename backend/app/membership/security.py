#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_membership import user_membership_dao
from backend.app.membership.service.entitlement_service import membership_entitlement_service
from backend.common.exception import errors
from backend.database.db import CurrentSession


async def get_membership_level(request: Request, db: CurrentSession) -> int:
    """
    获取当前用户最高会员权重

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    user_id = getattr(request.user, 'id', None) or getattr(request.user, 'user_id', None)
    if not user_id:
        return 0
    return await user_membership_dao.get_max_active_weight(db, int(user_id))


class MembershipRequired:
    """会员等级校验依赖"""

    def __init__(self, level: int = 1):
        self.level = level

    async def __call__(self, request: Request, db: CurrentSession) -> int:
        """
        校验当前用户会员等级是否满足要求

        :param request: 请求对象
        :param db: 数据库会话
        :return:
        """
        user_level = await get_membership_level(request, db)
        if user_level < self.level:
            raise errors.ForbiddenError(msg='需要开通会员才能访问')
        return user_level


async def check_membership_level(db: AsyncSession, *, user_id: int, required_level: int) -> int:
    """
    通用会员等级校验函数

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param required_level: 最低等级权重
    :return:
    """
    if required_level <= 0:
        return 0
    user_level = await user_membership_dao.get_max_active_weight(db, user_id)
    if user_level < required_level:
        raise errors.ForbiddenError(msg='需要开通会员才能访问')
    return user_level


async def check_membership_entitlement(
    db: AsyncSession,
    *,
    user_id: int,
    entitlement_code: str,
    required_value: int = 1,
) -> int:
    """
    通用会员权益校验函数

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param entitlement_code: 权益编码
    :param required_value: 最低权益值
    :return:
    """
    return await membership_entitlement_service.check_user_entitlement(
        db,
        user_id=user_id,
        entitlement_code=entitlement_code,
        required_value=required_value,
    )


DependsMembershipLevel = Annotated[int, Depends(get_membership_level)]
