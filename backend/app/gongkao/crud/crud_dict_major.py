#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.dict_major import GkDictMajor
from backend.app.gongkao.schema.dict_major import CreateDictMajorParam, UpdateDictMajorParam


class CRUDDictMajor(CRUDPlus[GkDictMajor]):
    """专业目录数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkDictMajor | None:
        """
        获取专业详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_code(self, db: AsyncSession, code: str) -> GkDictMajor | None:
        """
        通过专业代码获取

        :param db: 数据库会话
        :param code: 专业代码
        :return:
        """
        return await self.select_model_by_column(db, code=code)

    async def get_by_name(self, db: AsyncSession, name: str, edu_level: str = '本科') -> GkDictMajor | None:
        """
        通过专业名称获取

        :param db: 数据库会话
        :param name: 专业名称
        :param edu_level: 学历层次
        :return:
        """
        return await self.select_model_by_column(db, name=name, edu_level=edu_level)

    async def get_children(self, db: AsyncSession, parent_code: str | None) -> Sequence[GkDictMajor]:
        """
        获取子专业列表

        :param db: 数据库会话
        :param parent_code: 父级代码
        :return:
        """
        if parent_code is None:
            # 获取学科门类（顶级）
            return await self.select_models_order(db, 'sort_order', 'asc', level=1, is_active=True)
        return await self.select_models_order(db, 'sort_order', 'asc', parent_code=parent_code, is_active=True)

    async def get_by_level(self, db: AsyncSession, level: int, edu_level: str | None = None) -> Sequence[GkDictMajor]:
        """
        按级别获取专业列表

        :param db: 数据库会话
        :param level: 级别
        :param edu_level: 学历层次
        :return:
        """
        filters = {'level': level, 'is_active': True}
        if edu_level:
            filters['edu_level'] = edu_level
        return await self.select_models_order(db, 'sort_order', 'asc', **filters)

    async def search_by_name_or_alias(
        self,
        db: AsyncSession,
        keyword: str,
        edu_level: str | None = None,
    ) -> Sequence[GkDictMajor]:
        """
        通过名称或别名搜索专业

        :param db: 数据库会话
        :param keyword: 搜索关键词
        :param edu_level: 学历层次
        :return:
        """
        stmt = select(self.model).where(
            self.model.is_active == True,  # noqa: E712
            or_(
                self.model.name.contains(keyword),
                self.model.aliases.any(keyword),
            ),
        )
        if edu_level:
            stmt = stmt.where(self.model.edu_level == edu_level)
        stmt = stmt.order_by(self.model.level, self.model.sort_order)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_select(
        self,
        name: str | None = None,
        level: int | None = None,
        parent_code: str | None = None,
        edu_level: str | None = None,
        is_active: bool | None = None,
    ) -> Select:
        """
        获取专业列表查询表达式

        :param name: 专业名称
        :param level: 级别
        :param parent_code: 父级代码
        :param edu_level: 学历层次
        :param is_active: 是否启用
        :return:
        """
        filters = {}
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if level is not None:
            filters['level'] = level
        if parent_code is not None:
            filters['parent_code'] = parent_code
        if edu_level is not None:
            filters['edu_level'] = edu_level
        if is_active is not None:
            filters['is_active'] = is_active
        return await self.select_order('level', 'asc', 'sort_order', 'asc', **filters)

    async def create(self, db: AsyncSession, obj: CreateDictMajorParam) -> GkDictMajor:
        """
        创建专业

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        major = await self.create_model(db, obj)
        await db.flush()
        await db.refresh(major)
        return major

    async def bulk_create(self, db: AsyncSession, objs: list[CreateDictMajorParam]) -> int:
        """
        批量创建专业

        :param db: 数据库会话
        :param objs: 创建参数列表
        :return:
        """
        for obj in objs:
            major = GkDictMajor(**obj.model_dump())
            db.add(major)
        await db.flush()
        return len(objs)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDictMajorParam) -> int:
        """
        更新专业

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除专业（支持批量）

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def get_all(self, db: AsyncSession, edu_level: str | None = None) -> Sequence[GkDictMajor]:
        """
        获取所有专业

        :param db: 数据库会话
        :param edu_level: 学历层次
        :return:
        """
        stmt = select(self.model).where(self.model.is_active == True)  # noqa: E712
        if edu_level:
            stmt = stmt.where(self.model.edu_level == edu_level)
        stmt = stmt.order_by(self.model.level, self.model.sort_order)
        result = await db.execute(stmt)
        return result.scalars().all()


dict_major_dao: CRUDDictMajor = CRUDDictMajor(GkDictMajor)
