#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Sequence

from sqlalchemy import Select, and_, desc, select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.coulddrive.model.rule_template import RuleTemplate
from backend.app.coulddrive.schema.rule_template import (
    CreateRuleTemplateParam, 
    UpdateRuleTemplateParam,
    GetRuleTemplateListParam,
    TemplateType
)


class CRUDRuleTemplate(CRUDPlus[RuleTemplate]):
    """规则模板数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> RuleTemplate | None:
        """
        获取规则模板详情

        :param db: 数据库会话
        :param pk: 规则模板 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_name(self, db: AsyncSession, template_name: str) -> RuleTemplate | None:
        """
        通过模板名称获取规则模板

        :param db: 数据库会话
        :param template_name: 模板名称
        :return:
        """
        return await self.select_model_by_column(db, template_name=template_name)

    async def get_list(self, params: GetRuleTemplateListParam) -> Select:
        """
        获取规则模板列表查询语句

        :param params: 查询参数
        :return:
        """
        stmt = select(self.model).order_by(desc(self.model.created_time))

        filters = []
        
        if params.template_type is not None:
            filters.append(self.model.template_type == params.template_type)
        
        if params.category is not None:
            filters.append(self.model.category == params.category)
        
        if params.is_active is not None:
            filters.append(self.model.is_active == params.is_active)
        
        if params.is_system is not None:
            filters.append(self.model.is_system == params.is_system)
        
        if params.keyword is not None and params.keyword.strip():
            keyword = f"%{params.keyword.strip()}%"
            filters.append(
                or_(
                    self.model.template_name.like(keyword),
                    self.model.description.like(keyword)
                )
            )

        if filters:
            stmt = stmt.where(and_(*filters))

        return stmt

    async def get_list_with_pagination(self, db: AsyncSession, params: GetRuleTemplateListParam) -> Sequence[RuleTemplate]:
        """
        获取规则模板分页列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        stmt = await self.get_list(params)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_all(self, db: AsyncSession) -> Sequence[RuleTemplate]:
        """
        获取所有规则模板

        :param db: 数据库会话
        :return:
        """
        return await self.select_models(db)

    async def get_all_active(self, db: AsyncSession) -> Sequence[RuleTemplate]:
        """
        获取所有启用的规则模板

        :param db: 数据库会话
        :return:
        """
        return await self.select_models(db, is_active=True)

    async def get_by_type(self, db: AsyncSession, template_type: TemplateType) -> Sequence[RuleTemplate]:
        """
        通过类型获取规则模板

        :param db: 数据库会话
        :param template_type: 模板类型
        :return:
        """
        return await self.select_models(db, template_type=template_type, is_active=True)

    async def get_by_category(self, db: AsyncSession, category: str) -> Sequence[RuleTemplate]:
        """
        通过分类获取规则模板

        :param db: 数据库会话
        :param category: 分类
        :return:
        """
        return await self.select_models(db, category=category, is_active=True)

    async def create(self, db: AsyncSession, obj: CreateRuleTemplateParam, created_by: int) -> None:
        """
        创建规则模板

        :param db: 数据库会话
        :param obj: 创建规则模板参数
        :param created_by: 创建者ID
        :return:
        """
        # 添加创建者信息
        create_data = obj.model_dump()
        create_data['created_by'] = created_by
        create_data['updated_by'] = created_by
        
        await self.create_model(db, create_data)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateRuleTemplateParam, updated_by: int) -> int:
        """
        更新规则模板

        :param db: 数据库会话
        :param pk: 规则模板 ID
        :param obj: 更新规则模板参数
        :param updated_by: 更新者ID
        :return:
        """
        # 添加更新者信息
        update_data = obj.model_dump(exclude_unset=True)
        update_data['updated_by'] = updated_by
        
        return await self.update_model(db, pk, update_data)

    async def delete(self, db: AsyncSession, pk: list[int]) -> int:
        """
        删除规则模板

        :param db: 数据库会话
        :param pk: 规则模板 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pk)

    async def update_usage(self, db: AsyncSession, pk: int) -> int:
        """
        更新模板使用统计

        :param db: 数据库会话
        :param pk: 规则模板 ID
        :return:
        """
        return await self.update_model(db, pk, {
            "usage_count": self.model.usage_count + 1,
            "last_used_at": datetime.now()
        })

    async def toggle_active(self, db: AsyncSession, pk: int, is_active: bool) -> int:
        """
        切换模板启用状态

        :param db: 数据库会话
        :param pk: 规则模板 ID
        :param is_active: 是否启用
        :return:
        """
        return await self.update_model(db, pk, {"is_active": is_active})

    async def get_stats(self, db: AsyncSession) -> dict[str, any]:
        """
        获取规则模板统计信息

        :param db: 数据库会话
        :return:
        """
        # 总数量
        total_count = await db.scalar(select(func.count(self.model.id)))
        
        # 启用数量
        active_count = await db.scalar(
            select(func.count(self.model.id)).where(self.model.is_active == True)
        )
        
        # 系统模板数量
        system_count = await db.scalar(
            select(func.count(self.model.id)).where(self.model.is_system == True)
        )
        
        # 用户模板数量
        user_count = total_count - system_count
        
        # 分类统计
        category_stats_result = await db.execute(
            select(self.model.category, func.count(self.model.id))
            .where(self.model.category.isnot(None))
            .group_by(self.model.category)
        )
        category_stats = {row[0]: row[1] for row in category_stats_result.fetchall()}
        
        # 类型统计
        type_stats_result = await db.execute(
            select(self.model.template_type, func.count(self.model.id))
            .group_by(self.model.template_type)
        )
        type_stats = {row[0]: row[1] for row in type_stats_result.fetchall()}
        
        return {
            "total_count": total_count or 0,
            "active_count": active_count or 0,
            "system_count": system_count or 0,
            "user_count": user_count or 0,
            "category_stats": category_stats,
            "type_stats": type_stats
        }

    async def check_name_exists(self, db: AsyncSession, template_name: str, exclude_id: int | None = None) -> bool:
        """
        检查模板名称是否已存在

        :param db: 数据库会话
        :param template_name: 模板名称
        :param exclude_id: 排除的ID（用于更新时检查）
        :return:
        """
        stmt = select(func.count(self.model.id)).where(self.model.template_name == template_name)
        
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)
        
        count = await db.scalar(stmt)
        return count > 0


rule_template_dao: CRUDRuleTemplate = CRUDRuleTemplate(RuleTemplate) 