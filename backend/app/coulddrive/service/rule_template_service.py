#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_rule_template import rule_template_dao
from backend.app.coulddrive.model.rule_template import RuleTemplate
from backend.app.coulddrive.schema.rule_template import (
    CreateRuleTemplateParam,
    UpdateRuleTemplateParam,
    GetRuleTemplateListParam,
    TemplateType,
    RuleTemplateStatsDetail
)
from backend.common.exception.errors import NotFoundError, ForbiddenError


class RuleTemplateService:
    """规则模板服务类"""

    @staticmethod
    async def get_rule_template(db: AsyncSession, template_id: int) -> RuleTemplate:
        """
        获取规则模板详情

        :param db: 数据库会话
        :param template_id: 模板ID
        :return:
        """
        rule_template = await rule_template_dao.get(db, template_id)
        if not rule_template:
            raise NotFoundError(msg="规则模板不存在")
        return rule_template

    @staticmethod
    async def get_rule_template_list(db: AsyncSession, params: GetRuleTemplateListParam) -> Sequence[RuleTemplate]:
        """
        获取规则模板列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        return await rule_template_dao.get_list_with_pagination(db, params)

    @staticmethod
    async def create_rule_template(db: AsyncSession, obj: CreateRuleTemplateParam, created_by: int) -> None:
        """
        创建规则模板

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID
        :return:
        """
        # 检查模板名称是否已存在
        if await rule_template_dao.check_name_exists(db, obj.template_name):
            raise ForbiddenError(msg="模板名称已存在")
        
        await rule_template_dao.create(db, obj, created_by)

    @staticmethod
    async def update_rule_template(
        db: AsyncSession, 
        template_id: int, 
        obj: UpdateRuleTemplateParam, 
        updated_by: int
    ) -> None:
        """
        更新规则模板

        :param db: 数据库会话
        :param template_id: 模板ID
        :param obj: 更新参数
        :param updated_by: 更新者ID
        :return:
        """
        # 检查模板是否存在
        rule_template = await RuleTemplateService.get_rule_template(db, template_id)
        
        # 如果更新模板名称，检查是否重复
        if obj.template_name and obj.template_name != rule_template.template_name:
            if await rule_template_dao.check_name_exists(db, obj.template_name, template_id):
                raise ForbiddenError(msg="模板名称已存在")
        
        # 检查是否为系统模板
        if rule_template.is_system:
            raise ForbiddenError(msg="系统模板不允许修改")
        
        count = await rule_template_dao.update(db, template_id, obj, updated_by)
        if count == 0:
            raise NotFoundError(msg="更新失败，规则模板不存在")

    @staticmethod
    async def delete_rule_templates(db: AsyncSession, template_ids: list[int]) -> None:
        """
        批量删除规则模板

        :param db: 数据库会话
        :param template_ids: 模板ID列表
        :return:
        """
        # 检查是否包含系统模板
        for template_id in template_ids:
            rule_template = await rule_template_dao.get(db, template_id)
            if rule_template and rule_template.is_system:
                raise ForbiddenError(msg=f"模板 '{rule_template.template_name}' 是系统模板，不允许删除")
        
        count = await rule_template_dao.delete(db, template_ids)
        if count == 0:
            raise NotFoundError(msg="删除失败，规则模板不存在")

    @staticmethod
    async def use_rule_template(db: AsyncSession, template_id: int) -> RuleTemplate:
        """
        使用规则模板（更新使用统计）

        :param db: 数据库会话
        :param template_id: 模板ID
        :return:
        """
        rule_template = await RuleTemplateService.get_rule_template(db, template_id)
        
        if not rule_template.is_active:
            raise ForbiddenError(msg="模板已禁用，无法使用")
        
        # 更新使用统计
        await rule_template_dao.update_usage(db, template_id)
        
        return rule_template

    @staticmethod
    async def toggle_rule_template_active(db: AsyncSession, template_id: int, is_active: bool) -> None:
        """
        切换规则模板启用状态

        :param db: 数据库会话
        :param template_id: 模板ID
        :param is_active: 是否启用
        :return:
        """
        rule_template = await RuleTemplateService.get_rule_template(db, template_id)
        
        # 检查是否为系统模板
        if rule_template.is_system:
            raise ForbiddenError(msg="系统模板不允许修改状态")
        
        count = await rule_template_dao.toggle_active(db, template_id, is_active)
        if count == 0:
            raise NotFoundError(msg="操作失败，规则模板不存在")

    @staticmethod
    async def get_rule_template_stats(db: AsyncSession) -> RuleTemplateStatsDetail:
        """
        获取规则模板统计信息

        :param db: 数据库会话
        :return:
        """
        stats = await rule_template_dao.get_stats(db)
        return RuleTemplateStatsDetail(**stats)

    @staticmethod
    async def get_templates_by_type(db: AsyncSession, template_type: TemplateType) -> Sequence[RuleTemplate]:
        """
        根据类型获取规则模板

        :param db: 数据库会话
        :param template_type: 模板类型
        :return:
        """
        return await rule_template_dao.get_by_type(db, template_type)

    @staticmethod
    async def get_templates_by_category(db: AsyncSession, category: str) -> Sequence[RuleTemplate]:
        """
        根据分类获取规则模板

        :param db: 数据库会话
        :param category: 分类
        :return:
        """
        return await rule_template_dao.get_by_category(db, category)


rule_template_service = RuleTemplateService() 