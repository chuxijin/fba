#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import copy

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.study_plan.crud import (
    study_plan_template_dao,
    study_plan_template_item_dao,
)
from backend.app.study_plan.model.item import StudyPlanItem
from backend.app.study_plan.model.plan import StudyPlan
from backend.app.study_plan.model.template import StudyPlanTemplateItem
from backend.app.study_plan.schema.template import InstantiateStudyPlanTemplateParam
from backend.app.study_plan.service.ability_url_resolver import enrich_ability_item_extra
from backend.common.exception import errors


def _build_item_from_template(
    template_item: StudyPlanTemplateItem,
    plan_id: int,
    user_id: int,
    plan_date: date,
    created_by: int,
) -> StudyPlanItem:
    """
    从模板项构造一个学员计划项

    :param template_item: 模板项
    :param plan_id: 目标计划 ID
    :param user_id: 学员用户 ID
    :param plan_date: 项所属日期
    :param created_by: 创建者用户 ID
    :return:
    """
    return StudyPlanItem(
        plan_id=plan_id,
        user_id=user_id,
        plan_date=plan_date,
        order_index=template_item.order_index,
        module_type=template_item.module_type,
        title=template_item.title,
        ref_type=template_item.ref_type,
        ref_id=template_item.ref_id,
        expected_minutes=template_item.expected_minutes,
        status='pending',
        extra=copy.deepcopy(template_item.extra) if template_item.extra is not None else None,
        created_by=created_by,
    )


async def instantiate_template(
    db: AsyncSession,
    param: InstantiateStudyPlanTemplateParam,
    creator_id: int,
) -> StudyPlan:
    """
    将模板实例化为学员的具体学习计划（含所有日期的 items）

    :param db: 数据库会话
    :param param: 实例化参数
    :param creator_id: 创建者用户 ID（导师/管理员）
    :return:
    """
    template = await study_plan_template_dao.get(db, param.template_id)
    if template is None:
        raise errors.NotFoundError(msg='模板不存在')
    if not template.is_active:
        raise errors.RequestError(msg='模板已下架，无法实例化')

    template_items = await study_plan_template_item_dao.list_by_template(db, template.id)
    if not template_items:
        raise errors.RequestError(msg='模板未配置任何模块项')

    end_date = param.start_date + timedelta(days=template.duration_days - 1)

    plan = StudyPlan(
        user_id=param.user_id,
        title=param.title,
        start_date=param.start_date,
        end_date=end_date,
        domain=template.domain,
        status='active',
        template_id=template.id,
        created_by=creator_id,
    )
    db.add(plan)
    await db.flush()

    items = []
    for ti in template_items:
        enriched_extra = await enrich_ability_item_extra(
            db,
            copy.deepcopy(ti.extra) if ti.extra is not None else None,
        )
        items.append(
            StudyPlanItem(
                plan_id=plan.id,
                user_id=param.user_id,
                plan_date=param.start_date + timedelta(days=ti.day_index - 1),
                order_index=ti.order_index,
                module_type=ti.module_type,
                title=ti.title,
                ref_type=ti.ref_type,
                ref_id=ti.ref_id,
                expected_minutes=ti.expected_minutes,
                status='pending',
                extra=enriched_extra,
                created_by=creator_id,
            )
        )
    db.add_all(items)
    await db.flush()

    return plan
