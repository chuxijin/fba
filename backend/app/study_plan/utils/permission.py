#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.common.grayscale import check_grayscale, require_grayscale

STUDY_PLAN_INTERNAL_ROLE = 'study_plan_internal'

DependsStudyPlanWhitelist = require_grayscale('study_plan')


async def apply_virtual_roles(data: dict, user_id: int) -> dict:
    """
    给 /me 类响应数据追加学习规划虚拟角色（in-place 修改并返回 data）

    :param data: /me 接口的响应字典
    :param user_id: 用户 ID
    :return:
    """
    if not await check_grayscale(user_id, 'study_plan'):
        return data

    existing = data.get('roles') or []
    if existing and isinstance(existing[0], dict):
        existing.append({'id': 0, 'name': STUDY_PLAN_INTERNAL_ROLE})
    else:
        existing.append(STUDY_PLAN_INTERNAL_ROLE)
    data['roles'] = existing
    return data