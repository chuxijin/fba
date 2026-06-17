#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""导师端权限与归属校验服务"""

import sqlalchemy as sa

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import User
from backend.app.study_plan.crud import (
    study_mentor_student_dao,
    study_plan_dao,
    study_plan_item_dao,
)
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.model.mentor import StudyMentorStudent
from backend.app.study_plan.model.plan import StudyPlan
from backend.app.study_plan.schema.mentor import GetMentorStudentOption
from backend.common.exception import errors


async def ensure_mentor_can_access_student(
    db: AsyncSession,
    mentor_id: int,
    student_id: int,
    allow_all: bool = False,
) -> None:
    """
    校验导师是否可访问指定学员

    :param db: 数据库会话
    :param mentor_id: 导师用户 ID
    :param student_id: 学员用户 ID
    :param allow_all: 是否跳过关系校验
    :return:
    """
    if allow_all:
        return

    relation = await study_mentor_student_dao.get_pair(db, mentor_id, student_id)
    if relation is None or relation.status != 'active':
        raise errors.ForbiddenError(msg='该学员未分配给当前导师')


async def list_accessible_students_for_mentor(
    db: AsyncSession,
    mentor_id: int,
    allow_all: bool = False,
) -> list[GetMentorStudentOption]:
    """
    获取导师可访问学员选项

    :param db: 数据库会话
    :param mentor_id: 导师用户 ID
    :param allow_all: 是否返回所有生效关系
    :return:
    """
    join_condition = sa.and_(
        User.id == StudyMentorStudent.student_id,
        User.deleted == 0,
    )
    filters = [
        StudyMentorStudent.status == 'active',
        StudyMentorStudent.deleted == 0,
    ]
    if not allow_all:
        filters.append(StudyMentorStudent.mentor_id == mentor_id)

    stmt = (
        select(StudyMentorStudent, User)
        .outerjoin(User, join_condition)
        .where(*filters)
        .order_by(StudyMentorStudent.assigned_at.desc(), StudyMentorStudent.id.desc())
    )
    result = await db.execute(stmt)
    student_options: list[GetMentorStudentOption] = []
    seen_student_ids: set[int] = set()
    for relation, user in result.all():
        if relation.student_id in seen_student_ids:
            continue
        seen_student_ids.add(relation.student_id)
        student_options.append(
            GetMentorStudentOption(
                id=relation.id,
                student_id=relation.student_id,
                student_username=user.username if user is not None else None,
                student_nickname=user.nickname if user is not None else None,
                status=relation.status,
                assigned_at=relation.assigned_at,
            )
        )

    return student_options


async def get_plan_for_mentor(
    db: AsyncSession,
    plan_id: int,
    mentor_id: int,
    allow_all: bool = False,
) -> StudyPlan:
    """
    获取计划并校验导师是否可访问

    :param db: 数据库会话
    :param plan_id: 计划 ID
    :param mentor_id: 导师用户 ID
    :param allow_all: 是否跳过关系校验
    :return:
    """
    plan = await study_plan_dao.get(db, plan_id)
    if plan is None:
        raise errors.NotFoundError(msg='计划不存在')

    await ensure_mentor_can_access_student(db, mentor_id, plan.user_id, allow_all)
    return plan


async def get_item_for_mentor(
    db: AsyncSession,
    item_id: int,
    mentor_id: int,
    allow_all: bool = False,
) -> StudyPlanItem:
    """
    获取计划项并校验导师是否可访问

    :param db: 数据库会话
    :param item_id: 计划项 ID
    :param mentor_id: 导师用户 ID
    :param allow_all: 是否跳过关系校验
    :return:
    """
    item = await study_plan_item_dao.get(db, item_id)
    if item is None:
        raise errors.NotFoundError(msg='计划项不存在')

    await ensure_mentor_can_access_student(db, mentor_id, item.user_id, allow_all)
    return item
