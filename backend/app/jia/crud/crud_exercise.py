#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.exercise import Exercise
from backend.app.jia.schema.exercise import CreateExerciseParam, UpdateExerciseParam


class CRUDExercise(CRUDPlus[Exercise]):

    async def get_list(self, *, name: str | None = None) -> Select:
        """获取动作列表查询表达式"""
        filters = {}
        if name:
            filters['name_zh__like'] = f'%{name}%'
        return await self.select_order('id', 'desc', **filters)

    async def create(
        self,
        db: AsyncSession,
        obj: CreateExerciseParam,
        created_by: int,
        vector: list[float] | None = None,
    ) -> Exercise:
        """
        创建动作

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :param vector: 向量数据
        :return:
        """
        return await self.create_model(db, obj, created_by=created_by, vector=vector)

    async def update(
        self,
        db: AsyncSession,
        pk: int,
        obj: UpdateExerciseParam,
        updated_by: int,
        vector: list[float] | None = None,
    ) -> int:
        """
        更新动作

        :param db: 数据库会话
        :param pk: 动作 ID
        :param obj: 更新参数
        :param updated_by: 更新者 ID
        :param vector: 向量数据
        :return:
        """
        if vector is not None:
            return await self.update_model(db, pk, obj, updated_by=updated_by, vector=vector)
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def search_by_vector(
        self,
        db: AsyncSession,
        vector: list[float],
        name: str | None = None,
        limit: int = 20,
    ) -> list[Exercise]:
        """
        根据向量搜索相似动作

        :param db: 数据库会话
        :param vector: 查询向量
        :param name: 名称过滤（可选）
        :param limit: 返回数量
        :return:
        """
        stmt = select(Exercise).order_by(Exercise.vector.l2_distance(vector))
        if name:
            stmt = stmt.where(Exercise.name_zh.like(f'%{name}%'))
        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())


exercise_dao: CRUDExercise = CRUDExercise(Exercise)
