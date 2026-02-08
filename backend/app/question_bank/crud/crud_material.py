#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""材料数据库操作类"""
from collections.abc import Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model.question import QuestionMaterial, question_material_relation
from backend.app.question_bank.schema.material import CreateMaterialParam, UpdateMaterialParam, MaterialParam


class CRUDMaterial(CRUDPlus[QuestionMaterial]):
    """材料数据库操作类"""

    async def get(self, db: AsyncSession, material_id: int) -> QuestionMaterial | None:
        """
        获取材料详情

        :param db: 数据库会话
        :param material_id: 材料 ID
        :return:
        """
        return await self.select_model_by_column(db, id=material_id)

    async def get_with_bank(self, db: AsyncSession, material_id: int) -> QuestionMaterial | None:
        """
        获取材料详情（包含题库信息）

        :param db: 数据库会话
        :param material_id: 材料 ID
        :return:
        """
        stmt = select(self.model).options(selectinload(self.model.bank)).where(self.model.id == material_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_bank(
        self,
        db: AsyncSession,
        bank_id: int,
        is_active: bool | None = None,
    ) -> Sequence[QuestionMaterial]:
        """
        获取题库所有材料

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param is_active: 是否启用
        :return:
        """
        filters = {'bank_id': bank_id}
        if is_active is not None:
            filters['is_active'] = is_active
        return await self.select_models_order(db, 'sort_order', 'asc', **filters)

    async def get_list(
        self,
        db: AsyncSession,
        params: MaterialParam,
    ) -> Sequence[QuestionMaterial]:
        """
        获取材料列表

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        filters = {}
        if params.bank_id:
            filters['bank_id'] = params.bank_id
        if params.category_id:
            filters['category_id'] = params.category_id
        if params.is_active is not None:
            filters['is_active'] = params.is_active
        if params.year:
            filters['year'] = params.year

        stmt = select(self.model)
        for key, value in filters.items():
            stmt = stmt.where(getattr(self.model, key) == value)

        if params.keyword:
            keyword = f'%{params.keyword}%'
            stmt = stmt.where(
                (self.model.title.ilike(keyword)) | (self.model.source.ilike(keyword))
            )

        stmt = stmt.order_by(self.model.sort_order.asc(), self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_by_title(
        self,
        db: AsyncSession,
        bank_id: int,
        title: str,
    ) -> QuestionMaterial | None:
        """
        根据标题获取材料

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param title: 材料标题
        :return:
        """
        return await self.select_model_by_column(db, bank_id=bank_id, title=title)

    async def create(self, db: AsyncSession, obj: CreateMaterialParam, *, created_by: int) -> QuestionMaterial:
        """
        创建材料

        :param db: 数据库会话
        :param obj: 创建材料参数
        :param created_by: 创建者用户 ID
        :return:
        """
        obj_data = obj.model_dump()
        obj_data['created_by'] = created_by
        ins = self.model(**obj_data)
        db.add(ins)
        return ins

    async def update(self, db: AsyncSession, material_id: int, obj: UpdateMaterialParam, *, updated_by: int) -> int:
        """
        更新材料

        :param db: 数据库会话
        :param material_id: 材料 ID
        :param obj: 更新材料参数
        :param updated_by: 更新者用户 ID
        :return:
        """
        obj_data = obj.model_dump()
        obj_data['updated_by'] = updated_by
        return await self.update_model_by_column(db, obj_data, id=material_id)

    async def delete(self, db: AsyncSession, material_ids: list[int]) -> int:
        """
        批量删除材料

        :param db: 数据库会话
        :param material_ids: 材料 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=material_ids)

    async def get_question_count(self, db: AsyncSession, material_id: int) -> int:
        """
        获取材料关联的题目数量

        :param db: 数据库会话
        :param material_id: 材料 ID
        :return:
        """
        stmt = select(func.count()).select_from(question_material_relation).where(
            question_material_relation.c.material_id == material_id
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def link_questions(
        self,
        db: AsyncSession,
        material_id: int,
        question_ids: list[int],
    ) -> None:
        """
        关联题目到材料

        :param db: 数据库会话
        :param material_id: 材料 ID
        :param question_ids: 题目 ID 列表
        :return:
        """
        for idx, question_id in enumerate(question_ids):
            stmt = question_material_relation.insert().values(
                material_id=material_id,
                question_id=question_id,
                sort_order=idx,
            )
            await db.execute(stmt)

    async def unlink_questions(
        self,
        db: AsyncSession,
        material_id: int,
        question_ids: list[int] | None = None,
    ) -> int:
        """
        解除题目与材料的关联

        :param db: 数据库会话
        :param material_id: 材料 ID
        :param question_ids: 题目 ID 列表（为空则解除所有关联）
        :return:
        """
        stmt = question_material_relation.delete().where(
            question_material_relation.c.material_id == material_id
        )
        if question_ids:
            stmt = stmt.where(question_material_relation.c.question_id.in_(question_ids))
        result = await db.execute(stmt)
        return result.rowcount


material_dao: CRUDMaterial = CRUDMaterial(QuestionMaterial)
