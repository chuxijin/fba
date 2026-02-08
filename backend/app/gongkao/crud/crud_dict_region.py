#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.dict_region import GkDictRegion
from backend.app.gongkao.schema.dict_region import CreateDictRegionParam, UpdateDictRegionParam


class CRUDDictRegion(CRUDPlus[GkDictRegion]):
    """地区字典数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkDictRegion | None:
        """
        获取地区详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_code(self, db: AsyncSession, code: str) -> GkDictRegion | None:
        """
        通过地区代码获取

        :param db: 数据库会话
        :param code: 地区代码
        :return:
        """
        return await self.select_model_by_column(db, code=code)

    async def get_children(self, db: AsyncSession, parent_code: str | None) -> Sequence[GkDictRegion]:
        """
        获取子地区列表

        :param db: 数据库会话
        :param parent_code: 父级代码
        :return:
        """
        if parent_code is None:
            # 获取省级（顶级）
            return await self.select_models_order(db, 'sort_order', 'asc', level=1)
        return await self.select_models_order(db, 'sort_order', 'asc', parent_code=parent_code)

    async def get_by_level(self, db: AsyncSession, level: int) -> Sequence[GkDictRegion]:
        """
        按级别获取地区列表

        :param db: 数据库会话
        :param level: 级别
        :return:
        """
        return await self.select_models_order(db, 'sort_order', 'asc', level=level)

    async def get_select(
        self,
        name: str | None = None,
        level: int | None = None,
        parent_code: str | None = None,
    ) -> Select:
        """
        获取地区列表查询表达式

        :param name: 地区名称
        :param level: 级别
        :param parent_code: 父级代码
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if level is not None:
            filters['level'] = level
        if parent_code is not None:
            filters['parent_code'] = parent_code
        return await self.select_order('sort_order', 'asc', **filters)

    async def create(self, db: AsyncSession, obj: CreateDictRegionParam) -> GkDictRegion:
        """
        创建地区

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        region = await self.create_model(db, obj)
        await db.flush()
        await db.refresh(region)
        return region

    async def bulk_create(self, db: AsyncSession, objs: list[CreateDictRegionParam]) -> int:
        """
        批量创建地区

        :param db: 数据库会话
        :param objs: 创建参数列表
        :return:
        """
        for obj in objs:
            region = GkDictRegion(**obj.model_dump())
            db.add(region)
        await db.flush()
        return len(objs)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDictRegionParam) -> int:
        """
        更新地区

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除地区（支持批量）

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def get_all(self, db: AsyncSession) -> Sequence[GkDictRegion]:
        """
        获取所有地区

        :param db: 数据库会话
        :return:
        """
        from sqlalchemy import select

        stmt = select(self.model).order_by(self.model.level, self.model.sort_order)
        result = await db.execute(stmt)
        return result.scalars().all()


dict_region_dao: CRUDDictRegion = CRUDDictRegion(GkDictRegion)
