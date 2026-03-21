#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import Depends, Request

from backend.app.membership.crud.crud_membership import user_membership_dao
from backend.common.exception import errors
from backend.database.db import CurrentSession


async def get_membership_level(request: Request, db: CurrentSession) -> int:
    """
    获取当前用户的最高会员等级

    返回 0 表示无会员，返回 > 0 表示对应等级。
    可直接用作 Depends 注入到任何需要会员等级的端点。

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    user_id = getattr(request.user, 'id', None) or getattr(request.user, 'user_id', None)
    if not user_id:
        return 0
    memberships = await user_membership_dao.get_active_by_user(db, int(user_id))
    return max((m.level for m in memberships), default=0)


class MembershipRequired:
    """
    会员等级校验依赖

    用法::

        # 要求至少是基础会员 (level >= 1)
        @router.get('/vip-content', dependencies=[Depends(MembershipRequired())])

        # 要求高级会员 (level >= 2)
        @router.get('/premium', dependencies=[Depends(MembershipRequired(level=2))])

        # 作为参数注入（校验通过后可获取当前等级）
        @router.get('/content')
        async def get_content(member_level: int = Depends(MembershipRequired(level=1))):
            ...
    """

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


async def check_membership_level(db, *, user_id: int, required_level: int) -> int:
    """
    通用的会员等级校验工具函数（供 service 层调用）

    不满足等级时抛出 ForbiddenError，满足时返回用户当前等级。

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param required_level: 需要的最低等级
    :return:
    """
    if required_level <= 0:
        return 0
    memberships = await user_membership_dao.get_active_by_user(db, user_id)
    user_level = max((m.level for m in memberships), default=0)
    if user_level < required_level:
        raise errors.ForbiddenError(msg='需要开通会员才能访问')
    return user_level


# 依赖注入快捷方式
DependsMembershipLevel = Annotated[int, Depends(get_membership_level)]
