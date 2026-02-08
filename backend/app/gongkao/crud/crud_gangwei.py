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

    def _build_query(self, params: GangweiParam) -> Select:
        """
        构建查询条件

        :param params: 查询参数
        :return:
        """
        stmt = select(self.model).order_by(self.model.year.desc(), self.model.id.desc())

        if params.year is not None:
            stmt = stmt.where(self.model.year == params.year)
        if params.exam_type is not None:
            stmt = stmt.where(self.model.exam_type == params.exam_type)
        if params.region is not None:
            stmt = stmt.where(self.model.region.contains(params.region))
        if params.dept_name is not None:
            stmt = stmt.where(self.model.dept_name.contains(params.dept_name))
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

    async def get_existing_keys(
        self,
        db: AsyncSession,
        year: int,
        keys: list[tuple[str | None, str | None, str | None]],
    ) -> set[tuple[str | None, str | None, str | None]]:
        """
        批量检查已存在的记录（按年度+职位代码+职位名称+部门名称）

        :param db: 数据库会话
        :param year: 年度
        :param keys: (position_code, position_name, dept_name) 元组列表
        :return:
        """
        if not keys:
            return set()

        from sqlalchemy import and_, or_

        # 构建查询条件
        stmt = (
            select(
                self.model.position_code,
                self.model.position_name,
                self.model.dept_name,
            )
            .where(self.model.year == year)
            .where(
                or_(
                    *[
                        and_(
                            self.model.position_code == code,
                            self.model.position_name == name,
                            self.model.dept_name == dept,
                        )
                        for code, name, dept in keys
                    ]
                )
            )
        )
        result = await db.execute(stmt)
        return {(row[0], row[1], row[2]) for row in result.all()}

    async def find_by_match_key(
        self,
        db: AsyncSession,
        year: int,
        position_code: str | None,
        position_name: str | None,
        dept_name: str | None,
    ) -> tuple[GkGangwei | None, int]:
        """
        根据匹配条件查找岗位

        :param db: 数据库会话
        :param year: 年度
        :param position_code: 职位代码
        :param position_name: 职位名称
        :param dept_name: 部门名称
        :return: (岗位对象, 匹配数量)
        """
        from sqlalchemy import and_, func

        # 构建匹配条件
        conditions = [
            self.model.year == year,
            self.model.position_name == position_name,
            self.model.dept_name == dept_name,
        ]
        # 职位代码如果有值才加入匹配条件
        if position_code:
            conditions.append(self.model.position_code == position_code)

        # 先查询匹配数量
        count_stmt = select(func.count()).select_from(self.model).where(and_(*conditions))
        count_result = await db.execute(count_stmt)
        match_count = count_result.scalar() or 0

        if match_count == 0:
            return None, 0

        # 查询第一条匹配记录
        stmt = select(self.model).where(and_(*conditions)).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none(), match_count

    async def update_scores(
        self,
        db: AsyncSession,
        pk: int,
        score_data: dict,
        updated_by: int,
    ) -> int:
        """
        更新岗位分数字段

        :param db: 数据库会话
        :param pk: 岗位 ID
        :param score_data: 分数数据字典
        :param updated_by: 修改者 ID
        :return:
        """
        from sqlalchemy import update

        stmt = (
            update(self.model)
            .where(self.model.id == pk)
            .values(**score_data, updated_by=updated_by)
        )
        result = await db.execute(stmt)
        return result.rowcount


gangwei_dao: CRUDGangwei = CRUDGangwei(GkGangwei)
