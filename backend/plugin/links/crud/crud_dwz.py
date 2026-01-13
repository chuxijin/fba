#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.links.model import Dwz
from backend.plugin.links.schema import CreateDwzParam, UpdateDwzParam


class CRUDDwz(CRUDPlus[Dwz]):
    """短网址 CRUD"""

    async def get(self, db: AsyncSession, pk: int) -> Dwz | None:
        """
        获取短网址详情

        :param db: 数据库会话
        :param pk: 短网址ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_code(self, db: AsyncSession, code: str) -> Dwz | None:
        """
        通过短码获取短网址

        :param db: 数据库会话
        :param code: 短网址Key
        :return:
        """
        return await self.select_model_by_column(db, code=code)

    def get_select(
        self,
        *,
        title: str | None = None,
        status: int | None = None,
        created_by: int | None = None,
    ) -> Select:
        """
        获取短网址列表查询

        :param title: 标题模糊搜索
        :param status: 状态筛选
        :param created_by: 创建者筛选
        :return:
        """
        filters = {}
        if status is not None:
            filters['status'] = status
        if created_by is not None:
            filters['created_by'] = created_by

        stmt = select(self.model).filter_by(**filters)
        if title:
            stmt = stmt.where(self.model.title.ilike(f'%{title}%'))
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt

    async def create(self, db: AsyncSession, obj: CreateDwzParam, code: str, created_by: int) -> Dwz:
        """
        创建短网址

        :param db: 数据库会话
        :param obj: 创建参数
        :param code: 生成的短码
        :param created_by: 创建者ID
        :return:
        """
        dwz = Dwz(
            code=code,
            original_url=obj.original_url,
            title=obj.title,
            remark=obj.remark,
            entry_domain=obj.entry_domain,
            redirect_domain=obj.redirect_domain,
            landing_domain=obj.landing_domain,
            created_by=created_by,
        )
        db.add(dwz)
        await db.flush()
        await db.refresh(dwz)
        return dwz

    async def update(self, db: AsyncSession, pk: int, obj: UpdateDwzParam) -> int:
        """
        更新短网址

        :param db: 数据库会话
        :param pk: 短网址ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """
        删除短网址

        :param db: 数据库会话
        :param pk: 短网址ID
        :return:
        """
        return await self.delete_model(db, pk)

    async def increment_clicks(self, db: AsyncSession, pk: int) -> None:
        """
        增加访问量

        :param db: 数据库会话
        :param pk: 短网址ID
        :return:
        """
        stmt = update(self.model).where(self.model.id == pk).values(clicks=self.model.clicks + 1)
        await db.execute(stmt)

    async def check_code_exists(self, db: AsyncSession, code: str) -> bool:
        """
        检查短码是否存在

        :param db: 数据库会话
        :param code: 短网址Key
        :return:
        """
        result = await self.select_model_by_column(db, code=code)
        return result is not None


dwz_dao: CRUDDwz = CRUDDwz(Dwz)
