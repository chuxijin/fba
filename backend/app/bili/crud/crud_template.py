#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.bili.model import BiliTemplate
from backend.app.bili.schema.template import CreateBiliTemplateParam, UpdateBiliTemplateParam


class CRUDBiliTemplate(CRUDPlus[BiliTemplate]):
    """B 站模板话术数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> BiliTemplate | None:
        """
        获取模板详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_list(
        self,
        db: AsyncSession,
        name: str | None = None,
        template_type: str | None = None,
        status: int | None = None,
        category_id: int | None = None,
    ) -> Sequence[BiliTemplate]:
        """
        获取模板列表

        :param db: 数据库会话
        :param name: 模板名称
        :param template_type: 模板类型
        :param status: 状态
        :param category_id: 分类 ID
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if template_type is not None:
            filters['template_type'] = template_type
        if status is not None:
            filters['status'] = status
        if category_id is not None:
            filters['category_id'] = category_id
        return await self.select_models(db, **filters)

    async def create(self, db: AsyncSession, obj: CreateBiliTemplateParam) -> None:
        """
        创建模板

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateBiliTemplateParam) -> int:
        """
        更新模板

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除模板

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.delete_model(db, pk)


bili_template_dao: CRUDBiliTemplate = CRUDBiliTemplate(BiliTemplate)
