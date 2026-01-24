#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.gangwei import GkGangwei
from backend.app.gongkao.schema.gangwei import CreateGangweiParam, GangweiParam, UpdateGangweiParam


class CRUDGangwei(CRUDPlus[GkGangwei]):
    """岗位数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkGangwei | None:
        """
        获取岗位详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_unique_key(
        self,
        db: AsyncSession,
        year: int,
        org_region: str,
        position_code: str,
    ) -> GkGangwei | None:
        """
        通过联合唯一键获取岗位

        :param db: 数据库会话
        :param year: 年度
        :param org_region: 单位所属地区
        :param position_code: 职位代码
        :return:
        """
        return await self.select_model_by_column(
            db,
            year=year,
            org_region=org_region,
            position_code=position_code,
        )

    def _build_query(self, params: GangweiParam) -> Select:
        """
        构建查询条件

        :param params: 查询参数
        :return:
        """
        stmt = select(self.model).order_by(self.model.year.desc(), self.model.id.desc())

        if params.year is not None:
            stmt = stmt.where(self.model.year == params.year)
        if params.org_name is not None:
            stmt = stmt.where(self.model.org_name.contains(params.org_name))
        if params.org_region is not None:
            stmt = stmt.where(self.model.org_region.contains(params.org_region))
        if params.position_name is not None:
            stmt = stmt.where(self.model.position_name.contains(params.position_name))
        if params.position_code is not None:
            stmt = stmt.where(self.model.position_code == params.position_code)

        return stmt

    async def get_list(
        self,
        db: AsyncSession,
        params: GangweiParam,
        offset: int = 0,
        limit: int = 20,
    ) -> Sequence[GkGangwei]:
        """
        获取岗位列表

        :param db: 数据库会话
        :param params: 查询参数
        :param offset: 偏移量
        :param limit: 限制数量
        :return:
        """
        stmt = self._build_query(params).offset(offset).limit(limit)
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_count(self, db: AsyncSession, params: GangweiParam) -> int:
        """
        获取岗位总数

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        from sqlalchemy import func

        stmt = self._build_query(params)
        count_stmt = select(func.count()).select_from(stmt.subquery())
        result = await db.execute(count_stmt)
        return result.scalar() or 0

    async def create(self, db: AsyncSession, obj: CreateGangweiParam, created_by: int) -> GkGangwei:
        """
        创建岗位

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        gangwei = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(gangwei)
        return gangwei

    async def bulk_create(
        self,
        db: AsyncSession,
        objs: list[CreateGangweiParam],
        created_by: int,
    ) -> list[GkGangwei]:
        """
        批量创建岗位

        :param db: 数据库会话
        :param objs: 创建参数列表
        :param created_by: 创建者 ID
        :return:
        """
        gangwei_list = []
        for obj in objs:
            gangwei = GkGangwei(**obj.model_dump(), created_by=created_by)
            db.add(gangwei)
            gangwei_list.append(gangwei)
        await db.flush()
        for gangwei in gangwei_list:
            await db.refresh(gangwei)
        return gangwei_list

    async def update(self, db: AsyncSession, pk: int, obj: UpdateGangweiParam, updated_by: int) -> int:
        """
        更新岗位

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除岗位

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


gangwei_dao: CRUDGangwei = CRUDGangwei(GkGangwei)
