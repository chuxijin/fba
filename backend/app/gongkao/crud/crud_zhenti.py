#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model.zhenti import GkMaterial, GkQuestion, GkQuestionAnswer, GkQuestionOption
from backend.app.gongkao.schema.zhenti import (
    CreateMaterialParam,
    CreateQuestionAnswerParam,
    CreateQuestionOptionParam,
    CreateQuestionParam,
    UpdateMaterialParam,
    UpdateQuestionAnswerParam,
    UpdateQuestionOptionParam,
    UpdateQuestionParam,
)


# ==================== 题目 CRUD ====================
class CRUDQuestion(CRUDPlus[GkQuestion]):
    """题目数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkQuestion | None:
        """获取题目详情"""
        return await self.select_model(db, pk)

    async def get_select(
        self,
        title: str | None = None,
        question_type: str | None = None,
        category_id: int | None = None,
        material_id: int | None = None,
        year: int | None = None,
        source: str | None = None,
        status: bool | None = None,
    ) -> Select:
        """获取题目列表查询表达式"""
        filters = {}
        if title is not None:
            filters['title__like'] = f'%{title}%'
        if question_type is not None:
            filters['type'] = question_type
        if category_id is not None:
            filters['category_id'] = category_id
        if year is not None:
            filters['year'] = year
        if source is not None:
            filters['source__like'] = f'%{source}%'
        if status is not None:
            filters['status'] = status

        stmt = await self.select_order('sort_order', 'asc', **filters)

        # JSON 数组包含查询
        if material_id is not None:
            stmt = stmt.where(func.json_contains(self.model.material_ids, str(material_id)))

        return stmt

    async def create(self, db: AsyncSession, obj: CreateQuestionParam, created_by: int) -> GkQuestion:
        """创建题目"""
        question = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(question)
        return question

    async def update(self, db: AsyncSession, pk: int, obj: UpdateQuestionParam, updated_by: int) -> int:
        """更新题目"""
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """删除题目（支持批量）"""
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def get_hot_sources(self, db: AsyncSession, limit: int = 10) -> Sequence[str]:
        """获取热门来源（按浏览量排序）"""
        stmt = (
            select(self.model.source)
            .where(self.model.source.is_not(None))
            .group_by(self.model.source)
            .order_by(desc(func.sum(self.model.view_count)))
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()


# ==================== 题目选项 CRUD ====================
class CRUDQuestionOption(CRUDPlus[GkQuestionOption]):
    """题目选项数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkQuestionOption | None:
        """获取选项详情"""
        return await self.select_model(db, pk)

    async def get_by_question(self, db: AsyncSession, question_id: int) -> Sequence[GkQuestionOption]:
        """获取题目的所有选项"""
        return await self.select_models_order(db, 'sort_order', 'asc', question_id=question_id)

    async def create(self, db: AsyncSession, obj: CreateQuestionOptionParam) -> GkQuestionOption:
        """创建选项"""
        option = await self.create_model(db, obj)
        await db.flush()
        await db.refresh(option)
        return option

    async def update(self, db: AsyncSession, pk: int, obj: UpdateQuestionOptionParam) -> int:
        """更新选项"""
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """删除选项（支持批量）"""
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def delete_by_question(self, db: AsyncSession, question_id: int) -> int:
        """删除题目的所有选项"""
        return await self.delete_model_by_column(db, allow_multiple=True, question_id=question_id)


# ==================== 题目答案 CRUD ====================
class CRUDQuestionAnswer(CRUDPlus[GkQuestionAnswer]):
    """题目答案数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkQuestionAnswer | None:
        """获取答案详情"""
        return await self.select_model(db, pk)

    async def get_by_question(self, db: AsyncSession, question_id: int) -> Sequence[GkQuestionAnswer]:
        """获取题目的所有答案"""
        return await self.select_models(db, question_id=question_id)

    async def get_official_answer(self, db: AsyncSession, question_id: int) -> GkQuestionAnswer | None:
        """获取题目的官方答案"""
        return await self.select_model_by_column(db, question_id=question_id, is_official=True)

    async def create(self, db: AsyncSession, obj: CreateQuestionAnswerParam) -> GkQuestionAnswer:
        """创建答案"""
        answer = await self.create_model(db, obj)
        await db.flush()
        await db.refresh(answer)
        return answer

    async def update(self, db: AsyncSession, pk: int, obj: UpdateQuestionAnswerParam) -> int:
        """更新答案"""
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """删除答案（支持批量）"""
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def delete_by_question(self, db: AsyncSession, question_id: int) -> int:
        """删除题目的所有答案"""
        return await self.delete_model_by_column(db, allow_multiple=True, question_id=question_id)


# ==================== 材料 CRUD ====================
class CRUDMaterial(CRUDPlus[GkMaterial]):
    """材料数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkMaterial | None:
        """获取材料详情"""
        return await self.select_model(db, pk)

    async def get_select(
        self,
        title: str | None = None,
        category_id: int | None = None,
        year: int | None = None,
        source: str | None = None,
        status: bool | None = None,
    ) -> Select:
        """获取材料列表查询表达式"""
        filters = {}
        if title is not None:
            filters['title__like'] = f'%{title}%'
        if category_id is not None:
            filters['category_id'] = category_id
        if year is not None:
            filters['year'] = year
        if source is not None:
            filters['source__like'] = f'%{source}%'
        if status is not None:
            filters['status'] = status
        return await self.select_order('sort_order', 'asc', **filters)

    async def create(self, db: AsyncSession, obj: CreateMaterialParam, created_by: int) -> GkMaterial:
        """创建材料"""
        material = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(material)
        return material

    async def update(self, db: AsyncSession, pk: int, obj: UpdateMaterialParam, updated_by: int) -> int:
        """更新材料"""
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """删除材料（支持批量）"""
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


question_dao: CRUDQuestion = CRUDQuestion(GkQuestion)
question_option_dao: CRUDQuestionOption = CRUDQuestionOption(GkQuestionOption)
question_answer_dao: CRUDQuestionAnswer = CRUDQuestionAnswer(GkQuestionAnswer)
material_dao: CRUDMaterial = CRUDMaterial(GkMaterial)
