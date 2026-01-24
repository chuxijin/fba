#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_zhenti import material_dao, question_answer_dao, question_dao, question_option_dao
from backend.app.gongkao.model.zhenti import GkMaterial, GkQuestion, GkQuestionAnswer, GkQuestionOption
from backend.app.gongkao.schema.zhenti import (
    CreateMaterialParam,
    CreateQuestionAnswerParam,
    CreateQuestionOptionParam,
    CreateQuestionParam,
    DeleteMaterialParam,
    DeleteQuestionAnswerParam,
    DeleteQuestionOptionParam,
    DeleteQuestionParam,
    GetMaterialDetail,
    GetQuestionDetail,
    MaterialParam,
    QuestionParam,
    UpdateMaterialParam,
    UpdateQuestionAnswerParam,
    UpdateQuestionOptionParam,
    UpdateQuestionParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


# ==================== 题目 Service ====================
class QuestionService:
    """题目服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkQuestion:
        """获取题目详情"""
        question = await question_dao.get(db, pk)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')
        return question

    @staticmethod
    async def get_list(*, db: AsyncSession, params: QuestionParam) -> dict:
        """获取题目列表"""
        select = await question_dao.get_select(
            title=params.title,
            question_type=params.type,
            category_id=params.category_id,
            material_id=params.material_id,
            year=params.year,
            source=params.source,
            status=params.status,
        )
        return await paging_data(db, select, GetQuestionDetail)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQuestionParam, created_by: int) -> GkQuestion:
        """创建题目"""
        return await question_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateQuestionParam, updated_by: int) -> int:
        """更新题目"""
        question = await question_dao.get(db, pk)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')
        return await question_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteQuestionParam) -> int:
        """删除题目"""
        return await question_dao.delete(db, obj.ids)

    @staticmethod
    async def get_hot_sources(*, db: AsyncSession, limit: int = 10) -> Sequence[str]:
        """获取热门来源"""
        return await question_dao.get_hot_sources(db, limit)


# ==================== 题目选项 Service ====================
class QuestionOptionService:
    """题目选项服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkQuestionOption:
        """获取选项详情"""
        option = await question_option_dao.get(db, pk)
        if not option:
            raise errors.NotFoundError(msg='选项不存在')
        return option

    @staticmethod
    async def get_by_question(*, db: AsyncSession, question_id: int) -> Sequence[GkQuestionOption]:
        """获取题目的所有选项"""
        return await question_option_dao.get_by_question(db, question_id)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQuestionOptionParam) -> GkQuestionOption:
        """创建选项"""
        return await question_option_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateQuestionOptionParam) -> int:
        """更新选项"""
        option = await question_option_dao.get(db, pk)
        if not option:
            raise errors.NotFoundError(msg='选项不存在')
        return await question_option_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteQuestionOptionParam) -> int:
        """删除选项"""
        return await question_option_dao.delete(db, obj.ids)


# ==================== 题目答案 Service ====================
class QuestionAnswerService:
    """题目答案服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkQuestionAnswer:
        """获取答案详情"""
        answer = await question_answer_dao.get(db, pk)
        if not answer:
            raise errors.NotFoundError(msg='答案不存在')
        return answer

    @staticmethod
    async def get_by_question(*, db: AsyncSession, question_id: int) -> Sequence[GkQuestionAnswer]:
        """获取题目的所有答案"""
        return await question_answer_dao.get_by_question(db, question_id)

    @staticmethod
    async def get_official_answer(*, db: AsyncSession, question_id: int) -> GkQuestionAnswer | None:
        """获取题目的官方答案"""
        return await question_answer_dao.get_official_answer(db, question_id)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQuestionAnswerParam) -> GkQuestionAnswer:
        """创建答案"""
        return await question_answer_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateQuestionAnswerParam) -> int:
        """更新答案"""
        answer = await question_answer_dao.get(db, pk)
        if not answer:
            raise errors.NotFoundError(msg='答案不存在')
        return await question_answer_dao.update(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteQuestionAnswerParam) -> int:
        """删除答案"""
        return await question_answer_dao.delete(db, obj.ids)


# ==================== 材料 Service ====================
class MaterialService:
    """材料服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkMaterial:
        """获取材料详情"""
        material = await material_dao.get(db, pk)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')
        return material

    @staticmethod
    async def get_list(*, db: AsyncSession, params: MaterialParam) -> dict:
        """获取材料列表"""
        select = await material_dao.get_select(
            title=params.title,
            category_id=params.category_id,
            year=params.year,
            source=params.source,
            status=params.status,
        )
        return await paging_data(db, select, GetMaterialDetail)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateMaterialParam, created_by: int) -> GkMaterial:
        """创建材料"""
        return await material_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateMaterialParam, updated_by: int) -> int:
        """更新材料"""
        material = await material_dao.get(db, pk)
        if not material:
            raise errors.NotFoundError(msg='材料不存在')
        return await material_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteMaterialParam) -> int:
        """删除材料"""
        return await material_dao.delete(db, obj.ids)


question_service: QuestionService = QuestionService()
question_option_service: QuestionOptionService = QuestionOptionService()
question_answer_service: QuestionAnswerService = QuestionAnswerService()
material_service: MaterialService = MaterialService()
