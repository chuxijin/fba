#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import Request

from backend.common.exception import errors
from backend.core.conf import settings

STUDY_PLAN_INTERNAL_ROLE = 'study_plan_internal'


def is_user_in_whitelist(user_id: int) -> bool:
    """
    判断用户是否在学习规划灰度白名单内

    :param user_id: 用户 ID
    :return:
    """
    whitelist = settings.STUDY_PLAN_WHITELIST
    if not whitelist:
        return True
    return user_id in whitelist


def get_virtual_roles_for_user(user_id: int) -> list[str]:
    """
    获取学员需要追加的虚拟角色名列表（用于前端 tabbar 灰度可见控制）

    :param user_id: 用户 ID
    :return:
    """
    whitelist = settings.STUDY_PLAN_WHITELIST
    if whitelist and user_id in whitelist:
        return [STUDY_PLAN_INTERNAL_ROLE]
    return []


class StudyPlanWhitelistGate:
    """学习规划灰度白名单依赖注入校验器"""

    async def __call__(self, request: Request) -> None:
        user = getattr(request, 'user', None)
        user_id = getattr(user, 'id', None)
        if user_id is None:
            raise errors.AuthorizationError(msg='请先登录')
        if not is_user_in_whitelist(user_id):
            raise errors.ForbiddenError(msg='学习规划功能尚未对您开放')


DependsStudyPlanWhitelist = StudyPlanWhitelistGate()
