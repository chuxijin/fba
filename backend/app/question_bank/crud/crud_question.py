#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
题目相关 CRUD 操作

设计原则：
- 题目 CRUD 不涉及答案
- 解析 CRUD 独立管理
- 统计数据独立更新
"""
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import Question, QuestionAnalysis, QuestionStatistics
from backend.app.question_bank.model.question import QuestionMaterial
from backend.app.question_bank.schema.question import (
    CreateQuestionAnalysisParam,
    CreateQuestionParam,
    UpdateQuestionAnalysisParam,
    UpdateQuestionParam,
    UpdateQuestionStatisticsParam,
)


# ============ 题目 CRUD ============


class CRUDQuestion(CRUDPlus[Question]):
    """题目数据库操作类"""

    async def get(self, db: AsyncSession, question_id: int) -> Question | None:
        """
        获取题目详情（不含答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        return await self.select_model(db, question_id)

    async def get_with_relations(self, db: AsyncSession, question_id: int) -> Question | None:
        """
        获取题目详情（含关联信息和解析）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stmt = (
            select(Question)
            .where(Question.id == question_id)
            .options(
                joinedload(Question.bank),
                joinedload(Question.chapter),
                selectinload(Question.analyses),
            )
        )
        result = await db.execute(stmt)
        question = result.unique().scalars().first()
        # 兼容性处理：将 analyses 的第一个元素赋值给 analysis 属性，以满足 Schema 定义
        if question and question.analyses:
            # 动态赋值，不影响数据库
            setattr(question, 'analysis', question.analyses[0])
        return question

    async def get_by_ids(self, db: AsyncSession, ids: list[int], include_analysis: bool = False) -> Sequence[Question]:
        """
        批量获取题目列表（按 ID 列表顺序返回）

        :param db: 数据库会话
        :param ids: 题目 ID 列表
        :param include_analysis: 是否加载解析数据（答案）
        :return:
        """
        if not ids:
            return []

        # 构建基础查询选项
        options_list = [
            joinedload(Question.bank),
            joinedload(Question.chapter),
        ]

        # 🔥 根据参数决定是否加载解析
        if include_analysis:
            options_list.append(selectinload(Question.analyses))

        stmt = select(Question).where(Question.id.in_(ids)).options(*options_list)

        result = await db.execute(stmt)
        questions_map = {q.id: q for q in result.unique().scalars().all()}

        # 按 ids 顺序返回
        return [questions_map[id] for id in ids if id in questions_map]

    async def get_select(
        self,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
        is_active: bool | None = None,
        review_status: int | None = None,
        keyword: str | None = None,
    ):
        """
        获取题目查询语句

        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :param is_active: 是否启用
        :param review_status: 审核状态
        :param keyword: 关键字搜索
        :return:
        """
        # 直接构建查询语句，使用 joinedload 预加载关系
        stmt = select(Question).options(
            joinedload(Question.bank),
            joinedload(Question.chapter)
        )

        if bank_id is not None:
            stmt = stmt.where(Question.bank_id == bank_id)
        if chapter_id is not None:
            stmt = stmt.where(Question.chapter_id == chapter_id)
        if type is not None:
            stmt = stmt.where(Question.type == type)
        if difficulty is not None:
            stmt = stmt.where(Question.difficulty == difficulty)
        if is_active is not None:
            stmt = stmt.where(Question.is_active == is_active)
        if review_status is not None:
            stmt = stmt.where(Question.review_status == review_status)
        if keyword is not None:
            stmt = stmt.where(Question.stem.like(f'%{keyword}%'))

        stmt = stmt.order_by(Question.created_time.desc())
        return stmt

    async def get_all(
        self,
        db: AsyncSession,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
        is_active: bool | None = None,
        review_status: int | None = None,
        keyword: str | None = None,
        include_analysis: bool = False,
        include_materials: bool = False,
    ) -> Sequence[Question]:
        """
        获取所有题目

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :param is_active: 是否启用
        :param review_status: 审核状态
        :param keyword: 关键字搜索
        :param include_analysis: 是否包含解析
        :param include_materials: 是否包含材料
        :return:
        """
        # 构建查询选项
        options_list = [
            joinedload(Question.bank),
            joinedload(Question.chapter)
        ]

        if include_analysis:
            options_list.append(selectinload(Question.analyses))
        
        if include_materials:
            options_list.append(selectinload(Question.materials))

        stmt = select(Question).options(*options_list)

        if bank_id is not None:
            stmt = stmt.where(Question.bank_id == bank_id)
        if chapter_id is not None:
            stmt = stmt.where(Question.chapter_id == chapter_id)
        if type is not None:
            stmt = stmt.where(Question.type == type)
        if difficulty is not None:
            stmt = stmt.where(Question.difficulty == difficulty)
        if is_active is not None:
            stmt = stmt.where(Question.is_active == is_active)
        if review_status is not None:
            stmt = stmt.where(Question.review_status == review_status)
        if keyword is not None:
            stmt = stmt.where(Question.stem.like(f'%{keyword}%'))

        stmt = stmt.order_by(Question.created_time.desc())

        result = await db.execute(stmt)
        questions = result.unique().scalars().all()

        # 兼容性处理：如果有加载解析，将 analyses[0] 赋值给 analysis
        if include_analysis:
            for q in questions:
                if q.analyses:
                    setattr(q, 'analysis', q.analyses[0])
        
        return questions

    async def create(self, db: AsyncSession, obj: CreateQuestionParam, user_id: int) -> Question:
        """
        创建题目

        :param db: 数据库会话
        :param obj: 创建题目参数
        :param user_id: 用户 ID
        :return:
        """
        obj_dict = obj.model_dump()
        material_ids = obj_dict.pop('material_ids', None)
        obj_dict.pop('analysis', None)
        obj_dict['created_by'] = user_id

        question = Question(**obj_dict)
        db.add(question)

        # 处理材料关联
        if material_ids:
            stmt = select(QuestionMaterial).where(QuestionMaterial.id.in_(material_ids))
            result = await db.execute(stmt)
            materials = result.scalars().all()
            question.materials = list(materials)

        await db.flush()

        return question

    async def update(
        self, db: AsyncSession, question_id: int, obj: UpdateQuestionParam, user_id: int
    ) -> int:
        """
        更新题目

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param obj: 更新题目参数
        :param user_id: 用户 ID
        :return:
        """
        obj_dict = obj.model_dump()
        material_ids = obj_dict.pop('material_ids', None)
        obj_dict.pop('analysis', None)
        obj_dict['updated_by'] = user_id

        count = await self.update_model(db, question_id, obj_dict)

        # 如果提供了 material_ids（包括空列表），则更新关联
        if material_ids is not None:
            question = await self.get(db, question_id)
            if question:
                # 需先加载或确保 materials 可访问，selectinload 应该自动处理，这里直接赋值
                stmt = select(QuestionMaterial).where(QuestionMaterial.id.in_(material_ids))
                result = await db.execute(stmt)
                materials = result.scalars().all()
                question.materials = list(materials)
                await db.flush()

        return count

    async def delete(self, db: AsyncSession, question_ids: list[int]) -> int:
        """
        批量删除题目

        :param db: 数据库会话
        :param question_ids: 题目 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=question_ids)


# ============ 题目解析 CRUD ============


class CRUDQuestionAnalysis(CRUDPlus[QuestionAnalysis]):
    """题目解析数据库操作类"""

    async def get_by_question_id(self, db: AsyncSession, question_id: int) -> QuestionAnalysis | None:
        """
        根据题目 ID 获取解析

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stmt = select(QuestionAnalysis).where(QuestionAnalysis.question_id == question_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, obj: CreateQuestionAnalysisParam, user_id: int) -> QuestionAnalysis:
        """
        创建题目解析

        :param db: 数据库会话
        :param obj: 创建解析参数
        :param user_id: 用户 ID
        :return:
        """
        obj_dict = obj.model_dump()
        obj_dict['created_by'] = user_id

        analysis = QuestionAnalysis(**obj_dict)
        db.add(analysis)
        await db.flush()

        return analysis

    async def update(
        self, db: AsyncSession, question_id: int, obj: UpdateQuestionAnalysisParam, user_id: int
    ) -> int:
        """
        更新题目解析

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param obj: 更新解析参数
        :param user_id: 用户 ID
        :return:
        """
        obj_dict = obj.model_dump()
        obj_dict['updated_by'] = user_id

        return await self.update_model_by_column(db, obj_dict, question_id=question_id)

    async def increment_view_count(self, db: AsyncSession, question_id: int) -> None:
        """
        增加查看次数

        :param db: 数据库会话
        :param question_id: 题目 ID
        """
        analysis = await self.get_by_question_id(db, question_id)
        if analysis:
            analysis.view_count += 1
            await db.flush()

    async def increment_helpful_count(self, db: AsyncSession, question_id: int, is_helpful: bool) -> None:
        """
        增加有帮助/无帮助次数

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param is_helpful: 是否有帮助
        """
        analysis = await self.get_by_question_id(db, question_id)
        if analysis:
            if is_helpful:
                analysis.helpful_count += 1
            else:
                analysis.unhelpful_count += 1
            await db.flush()


# ============ 题目统计 CRUD ============


class CRUDQuestionStatistics(CRUDPlus[QuestionStatistics]):
    """题目统计数据库操作类"""

    async def get_by_question_id(self, db: AsyncSession, question_id: int) -> QuestionStatistics | None:
        """
        根据题目 ID 获取统计

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stmt = select(QuestionStatistics).where(QuestionStatistics.question_id == question_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_or_create(self, db: AsyncSession, question_id: int) -> QuestionStatistics:
        """
        获取或创建统计记录

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        stats = await self.get_by_question_id(db, question_id)
        if not stats:
            stats = QuestionStatistics(question_id=question_id)
            db.add(stats)
            await db.flush()
        return stats

    async def update_stats(
        self, db: AsyncSession, question_id: int, obj: UpdateQuestionStatisticsParam
    ) -> None:
        """
        更新题目统计

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param obj: 更新统计参数
        """
        stats = await self.get_or_create(db, question_id)

        # 更新答题统计
        if obj.attempt_count is not None:
            stats.attempt_count += obj.attempt_count
        if obj.correct_count is not None:
            stats.correct_count += obj.correct_count

        # 重新计算正确率
        if stats.attempt_count > 0:
            stats.correct_rate = Decimal((stats.correct_count / stats.attempt_count) * 100).quantize(
                Decimal('0.01')
            )

        # 更新平均答题时间
        if obj.answer_time is not None:
            if stats.avg_answer_time is None:
                stats.avg_answer_time = obj.answer_time
            else:
                # 加权平均
                total_time = stats.avg_answer_time * (stats.attempt_count - 1) + obj.answer_time
                stats.avg_answer_time = Decimal(total_time / stats.attempt_count).quantize(Decimal('0.01'))

        # 更新错误选项统计
        if obj.wrong_option is not None:
            if stats.wrong_option_stats is None:
                stats.wrong_option_stats = {}
            wrong_option_stats = stats.wrong_option_stats.copy()
            wrong_option_stats[obj.wrong_option] = wrong_option_stats.get(obj.wrong_option, 0) + 1
            stats.wrong_option_stats = wrong_option_stats

        # 更新收藏/笔记次数
        if obj.collect_delta is not None:
            stats.collect_count += obj.collect_delta
        if obj.note_delta is not None:
            stats.note_count += obj.note_delta

        await db.flush()


# ============ 导出实例 ============

question_dao: CRUDQuestion = CRUDQuestion(Question)
question_analysis_dao: CRUDQuestionAnalysis = CRUDQuestionAnalysis(QuestionAnalysis)
question_statistics_dao: CRUDQuestionStatistics = CRUDQuestionStatistics(QuestionStatistics)
