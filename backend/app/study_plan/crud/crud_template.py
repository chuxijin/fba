#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.study_plan.model.template import StudyPlanTemplate, StudyPlanTemplateItem


class CRUDStudyPlanTemplate(CRUDPlus[StudyPlanTemplate]):
    """学习计划模板数据库操作类"""

    async def get(self, db: AsyncSession, template_id: int) -> StudyPlanTemplate | None:
        """
        获取模板详情

        :param db: 数据库会话
        :param template_id: 模板 ID
        :return:
        """
        return await self.select_model(db, template_id, deleted=0)

    async def list_active(
        self, db: AsyncSession, domain: str = 'civil_service',
    ) -> Sequence[StudyPlanTemplate]:
        """
        获取启用的模板列表

        :param db: 数据库会话
        :param domain: 业务领域
        :return:
        """
        stmt = (
            select(StudyPlanTemplate)
            .where(
                StudyPlanTemplate.is_active.is_(True),
                StudyPlanTemplate.domain == domain,
                StudyPlanTemplate.deleted == 0,
            )
            .order_by(StudyPlanTemplate.id.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()


class CRUDStudyPlanTemplateItem(CRUDPlus[StudyPlanTemplateItem]):
    """学习计划模板项数据库操作类"""

    async def get(self, db: AsyncSession, item_id: int) -> StudyPlanTemplateItem | None:
        """
        获取模板项详情

        :param db: 数据库会话
        :param item_id: 模板项 ID
        :return:
        """
        return await self.select_model(db, item_id, deleted=0)

    async def list_by_template(
        self, db: AsyncSession, template_id: int,
    ) -> Sequence[StudyPlanTemplateItem]:
        """
        获取模板下所有模板项（按 day_index + order_index 升序）

        :param db: 数据库会话
        :param template_id: 模板 ID
        :return:
        """
        stmt = (
            select(StudyPlanTemplateItem)
            .where(
                StudyPlanTemplateItem.template_id == template_id,
                StudyPlanTemplateItem.deleted == 0,
            )
            .order_by(
                StudyPlanTemplateItem.day_index.asc(),
                StudyPlanTemplateItem.order_index.asc(),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()


study_plan_template_dao = CRUDStudyPlanTemplate(StudyPlanTemplate)
study_plan_template_item_dao = CRUDStudyPlanTemplateItem(StudyPlanTemplateItem)
