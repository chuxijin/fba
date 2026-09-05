#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkHanyuGroup, GkHanyuGroupItem
from backend.app.gongkao.schema.hanyu_group import (
    CreateHanyuGroupParam,
    HanyuGroupParam,
    UpdateHanyuGroupParam,
)


class CRUDHanyuGroup(CRUDPlus[GkHanyuGroup]):
    """汉语词语辨析组数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkHanyuGroup | None:
        """
        获取辨析组详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_title(self, db: AsyncSession, title: str, category: str | None = None) -> GkHanyuGroup | None:
        """
        根据标题获取辨析组

        :param db: 数据库会话
        :param title: 辨析组标题
        :param category: 分类
        :return:
        """
        filters = {'title': title}
        if category is not None:
            filters['category'] = category
        return await self.select_model_by_column(db, **filters)

    async def get_select(self, params: HanyuGroupParam) -> Select:
        """
        构建辨析组列表查询表达式

        :param params: 查询参数
        :return:
        """
        se = select(self.model)

        if params.category is not None:
            se = se.where(self.model.category == params.category)
        if params.group_no is not None:
            se = se.where(self.model.group_no == params.group_no)
        if params.title:
            se = se.where(self.model.title.ilike(f'%{params.title}%'))

        se = se.order_by(self.model.sort_order, self.model.group_no, self.model.id)
        return se

    async def get_categories(self, db: AsyncSession) -> list[str]:
        """
        获取所有分类

        :param db: 数据库会话
        :return:
        """
        stmt = select(self.model.category).distinct().order_by(self.model.category)
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]

    async def create(self, db: AsyncSession, obj: CreateHanyuGroupParam, created_by: int) -> GkHanyuGroup:
        """
        创建辨析组（含成员明细）

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        data = obj.model_dump(exclude={'items'})
        group = GkHanyuGroup(**data, created_by=created_by)
        db.add(group)
        await db.flush()
        group.items = [GkHanyuGroupItem(group_id=group.id, **item.model_dump()) for item in obj.items]
        await db.flush()
        return group

    async def update(self, db: AsyncSession, group: GkHanyuGroup, obj: UpdateHanyuGroupParam, updated_by: int) -> None:
        """
        更新辨析组（items 传入则整体替换成员明细）

        :param db: 数据库会话
        :param group: 辨析组 ORM 对象
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        data = obj.model_dump(exclude={'items'}, exclude_unset=True)
        for field, value in data.items():
            setattr(group, field, value)
        group.updated_by = updated_by
        if obj.items is not None:
            group.items = [GkHanyuGroupItem(group_id=group.id, **item.model_dump()) for item in obj.items]
        await db.flush()

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除辨析组（支持批量，级联删除成员明细）

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


hanyu_group_dao: CRUDHanyuGroup = CRUDHanyuGroup(GkHanyuGroup)
