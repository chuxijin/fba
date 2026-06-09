#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import Request

from backend.common.exception import errors
from backend.core.conf import settings


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
