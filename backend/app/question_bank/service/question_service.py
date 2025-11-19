#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
题目服务层

设计原则：
- 题目查询不返回答案
- 解析查询返回答案和解析内容
- 答题提交时验证答案并更新统计
"""
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_question import (
    question_analysis_dao,
    question_dao,
    question_statistics_dao,
)
from backend.app.question_bank.model import Question, QuestionAnalysis, QuestionStatistics
from backend.app.question_bank.schema.question import (
    BatchSubmitAnswerParam,
    BatchSubmitAnswerResult,
    CreateQuestionAnalysisParam,
    CreateQuestionParam,
    DeleteQuestionParam,
    QuestionResultItem,
    UpdateQuestionAnalysisParam,
    UpdateQuestionParam,
    UpdateQuestionStatisticsParam,
)
from backend.common.exception import errors
from backend.common.pagination import _CustomPage, _CustomPageParams


class QuestionService:
    """题目服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Question:
        """
        获取题目详情（不含答案）

        :param db: 数据库会话
        :param pk: 题目 ID
        :return:
        """
        question = await question_dao.get_with_relations(db, pk)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')
        return question

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
        is_active: bool | None = None,
        review_status: int | None = None,
        keyword: str | None = None,
        page: int | None = None,
        size: int | None = None,
    ) -> Sequence[Question] | dict[str, Any]:
        """
        获取题目列表（不含答案）

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :param is_active: 是否启用
        :param review_status: 审核状态
        :param keyword: 关键字搜索
        :param page: 页码
        :param size: 每页数量
        :return:
        """
        # 如果提供了分页参数，使用优化的分页查询
        if page is not None and size is not None:
            # 获取查询语句
            question_select = await question_dao.get_select(
                bank_id=bank_id,
                chapter_id=chapter_id,
                type=type,
                difficulty=difficulty,
                is_active=is_active,
                review_status=review_status,
                keyword=keyword,
            )

            # 获取总数
            count_stmt = select(func.count()).select_from(question_select.subquery())
            total = await db.scalar(count_stmt) or 0

            # 获取当前页数据
            offset = (page - 1) * size
            stmt = question_select.limit(size).offset(offset)
            result = await db.execute(stmt)
            questions = result.unique().scalars().all()

            # 在异步上下文中手动序列化为字典，避免 MissingGreenlet 错误
            # 这样可以确保所有关系属性的访问都在 async session context 内完成
            questions_dict = []
            for q in questions:
                question_dict = {
                    'id': q.id,
                    'bank_id': q.bank_id,
                    'type': q.type,
                    'stem': q.stem,
                    'chapter_id': q.chapter_id,
                    'options_data': q.options_data,
                    'difficulty': q.difficulty,
                    'score': q.score,
                    'knowledge_point': q.knowledge_point,
                    'source': q.source,
                    'year': q.year,
                    'usage': q.usage,
                    'is_active': q.is_active,
                    'review_status': q.review_status,
                    'created_time': q.created_time,
                    'updated_time': q.updated_time,
                    'created_by': q.created_by,
                    'updated_by': q.updated_by,
                    # 关系对象
                    'bank': {'id': q.bank.id, 'name': q.bank.name} if q.bank else None,
                    'chapter': {'id': q.chapter.id, 'name': q.chapter.name} if q.chapter else None,
                    # 扁平化字段，方便前端表格显示
                    'bank_name': q.bank.name if q.bank else None,
                    'chapter_name': q.chapter.name if q.chapter else None,
                }
                questions_dict.append(question_dict)

            # 使用项目的分页工具函数构造分页响应
            params = _CustomPageParams(page=page, size=size)
            page_data = _CustomPage.create(items=questions_dict, params=params, total=total)
            return page_data.model_dump()

        # 否则返回全部数据（客户端使用）
        questions = await question_dao.get_all(
            db,
            bank_id=bank_id,
            chapter_id=chapter_id,
            type=type,
            difficulty=difficulty,
            is_active=is_active,
            review_status=review_status,
            keyword=keyword,
        )
        return questions

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateQuestionParam, user_id: int) -> Question:
        """
        创建题目

        :param db: 数据库会话
        :param obj: 创建题目参数
        :param user_id: 用户 ID
        :return:
        """
        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        if obj.chapter_id:
            chapter = await chapter_dao.get(db, obj.chapter_id)
            if not chapter:
                raise errors.NotFoundError(msg='章节不存在')

        # 提取解析数据
        analysis_data = obj.analysis

        # 创建题目（排除 analysis 字段）
        question_dict = obj.model_dump(exclude={'analysis'})
        question_dict['created_by'] = user_id
        question = Question(**question_dict)
        db.add(question)
        await db.flush()

        # 如果提供了解析数据，同时创建解析
        if analysis_data:
            analysis_param = CreateQuestionAnalysisParam(
                question_id=question.id,
                answer_data=analysis_data.get('answer_data', {}),
                content=analysis_data.get('content', ''),
            )
            await question_analysis_dao.create(db, analysis_param, user_id)

        return question

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateQuestionParam, user_id: int) -> int:
        """
        更新题目

        :param db: 数据库会话
        :param pk: 题目 ID
        :param obj: 更新题目参数
        :param user_id: 用户 ID
        :return:
        """
        question = await question_dao.get(db, pk)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        if obj.chapter_id:
            chapter = await chapter_dao.get(db, obj.chapter_id)
            if not chapter:
                raise errors.NotFoundError(msg='章节不存在')

        # 提取解析数据
        analysis_data = obj.analysis

        # 更新题目（排除 analysis 字段）
        update_dict = obj.model_dump(exclude={'analysis'})
        update_dict['updated_by'] = user_id
        count = await question_dao.update_model(db, pk, update_dict)

        # 如果提供了解析数据，同时更新或创建解析
        if analysis_data:
            existing_analysis = await question_analysis_dao.get_by_question_id(db, pk)
            if existing_analysis:
                # 更新现有解析
                update_analysis_dict = {
                    'answer_data': analysis_data.get('answer_data', {}),
                    'content': analysis_data.get('content', ''),
                    'updated_by': user_id,
                }
                await question_analysis_dao.update_model_by_column(db, update_analysis_dict, question_id=pk)
            else:
                # 创建新解析
                create_param = CreateQuestionAnalysisParam(
                    question_id=pk,
                    answer_data=analysis_data.get('answer_data', {}),
                    content=analysis_data.get('content', ''),
                )
                await question_analysis_dao.create(db, create_param, user_id)

        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteQuestionParam) -> int:
        """
        删除题目（级联删除解析和统计）

        :param db: 数据库会话
        :param obj: 删除题目参数
        :return:
        """
        count = await question_dao.delete(db, obj.ids)
        return count

    # ============ 题目解析相关 ============

    @staticmethod
    async def get_analysis(*, db: AsyncSession, question_id: int, increment_view: bool = True) -> QuestionAnalysis:
        """
        获取题目解析（含答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param increment_view: 是否增加查看次数
        :return:
        """
        # 验证题目存在
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        # 获取解析
        analysis = await question_analysis_dao.get_by_question_id(db, question_id)
        if not analysis:
            raise errors.NotFoundError(msg='题目解析不存在')

        # 增加查看次数
        if increment_view:
            await question_analysis_dao.increment_view_count(db, question_id)

        return analysis

    @staticmethod
    async def create_analysis(*, db: AsyncSession, obj: CreateQuestionAnalysisParam, user_id: int) -> QuestionAnalysis:
        """
        创建题目解析

        :param db: 数据库会话
        :param obj: 创建解析参数
        :param user_id: 用户 ID
        :return:
        """
        # 验证题目存在
        question = await question_dao.get(db, obj.question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        # 检查是否已存在解析
        existing = await question_analysis_dao.get_by_question_id(db, obj.question_id)
        if existing:
            raise errors.ForbiddenError(msg='该题目已存在解析')

        analysis = await question_analysis_dao.create(db, obj, user_id)
        return analysis

    @staticmethod
    async def update_analysis(
        *, db: AsyncSession, question_id: int, obj: UpdateQuestionAnalysisParam, user_id: int
    ) -> int:
        """
        更新题目解析

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param obj: 更新解析参数
        :param user_id: 用户 ID
        :return:
        """
        analysis = await question_analysis_dao.get_by_question_id(db, question_id)
        if not analysis:
            raise errors.NotFoundError(msg='题目解析不存在')

        count = await question_analysis_dao.update(db, question_id, obj, user_id)
        return count

    @staticmethod
    async def mark_analysis_helpful(*, db: AsyncSession, question_id: int, is_helpful: bool) -> None:
        """
        标记解析是否有帮助

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param is_helpful: 是否有帮助
        """
        analysis = await question_analysis_dao.get_by_question_id(db, question_id)
        if not analysis:
            raise errors.NotFoundError(msg='题目解析不存在')

        await question_analysis_dao.increment_helpful_count(db, question_id, is_helpful)

    # ============ 答题相关 ============

    @staticmethod
    async def batch_submit_answer(*, db: AsyncSession, obj: BatchSubmitAnswerParam) -> BatchSubmitAnswerResult:
        """
        批量提交答案并判分（适合考试/试卷场景）

        :param db: 数据库会话
        :param obj: 批量提交答案参数
        :return:
        """
        results: list[QuestionResultItem] = []
        total_score = Decimal('0')
        full_score = Decimal('0')
        correct_count = 0
        wrong_count = 0

        # 逐题判分
        for answer_item in obj.answers:
            # 获取题目
            question = await question_dao.get(db, answer_item.question_id)
            if not question:
                raise errors.NotFoundError(msg=f'题目 ID {answer_item.question_id} 不存在')

            # 获取解析（包含正确答案）
            analysis = await question_analysis_dao.get_by_question_id(db, answer_item.question_id)
            if not analysis:
                raise errors.NotFoundError(msg=f'题目 ID {answer_item.question_id} 的解析不存在')

            # 判断答案是否正确
            is_correct = QuestionService._check_answer(question.type, answer_item.user_answer, analysis.answer_data)

            # 计算得分
            score = question.score if is_correct else Decimal('0')
            total_score += score
            full_score += question.score

            # 统计正确/错误数量
            if is_correct:
                correct_count += 1
            else:
                wrong_count += 1

            # 更新统计数据
            stats_param = UpdateQuestionStatisticsParam(
                attempt_count=1,
                correct_count=1 if is_correct else 0,
                answer_time=answer_item.answer_time,
                wrong_option=answer_item.user_answer if not is_correct and question.type in ['single', 'judgement'] else None,
            )
            await question_statistics_dao.update_stats(db, answer_item.question_id, stats_param)

            # 如果需要包含解析，增加查看次数
            if obj.include_analysis:
                await question_analysis_dao.increment_view_count(db, answer_item.question_id)

            # 构造结果项
            results.append(
                QuestionResultItem(
                    question_id=answer_item.question_id,
                    is_correct=is_correct,
                    user_answer=answer_item.user_answer,
                    correct_answer=analysis.answer_data,
                    score=score,
                    full_score=question.score,
                    analysis_content=analysis.content if obj.include_analysis else None,
                )
            )

        # 计算总体统计
        total_questions = len(obj.answers)
        accuracy_rate = Decimal((correct_count / total_questions) * 100).quantize(Decimal('0.01')) if total_questions > 0 else Decimal('0')
        score_rate = Decimal((total_score / full_score) * 100).quantize(Decimal('0.01')) if full_score > 0 else Decimal('0')

        return BatchSubmitAnswerResult(
            total_questions=total_questions,
            correct_count=correct_count,
            wrong_count=wrong_count,
            total_score=total_score,
            full_score=full_score,
            accuracy_rate=accuracy_rate,
            score_rate=score_rate,
            results=results,
        )

    @staticmethod
    def _check_answer(question_type: str, user_answer: str | list[str], correct_data: dict) -> bool:
        """
        判断答案是否正确

        :param question_type: 题型
        :param user_answer: 用户答案
        :param correct_data: 正确答案数据
        :return:
        """
        correct_answer = correct_data.get('correct')

        if question_type in ['single', 'judgement']:
            # 单选/判断：比较字符串
            return str(user_answer).strip().upper() == str(correct_answer).strip().upper()

        if question_type == 'multiple':
            # 多选：比较集合（不考虑顺序）
            if not isinstance(user_answer, list):
                return False
            user_set = {str(ans).strip().upper() for ans in user_answer}
            correct_set = {str(ans).strip().upper() for ans in correct_answer}
            return user_set == correct_set

        if question_type == 'fill':
            # 填空：逐个比较（去除首尾空格）
            if not isinstance(user_answer, list):
                return False
            if len(user_answer) != len(correct_answer):
                return False
            return all(
                str(u).strip() == str(c).strip()
                for u, c in zip(user_answer, correct_answer)
            )

        if question_type == 'shortAnswer':
            # 简答：关键词匹配（至少包含 60% 的关键词）
            keywords = correct_data.get('keywords', [])
            if not keywords:
                return True
            user_text = str(user_answer).lower()
            matched = sum(1 for keyword in keywords if keyword.lower() in user_text)
            return matched >= len(keywords) * 0.6

        return False

    # ============ 题目统计相关 ============

    @staticmethod
    async def get_statistics(*, db: AsyncSession, question_id: int) -> QuestionStatistics:
        """
        获取题目统计

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        stats = await question_statistics_dao.get_or_create(db, question_id)
        return stats

    @staticmethod
    async def update_statistics(*, db: AsyncSession, question_id: int, obj: UpdateQuestionStatisticsParam) -> None:
        """
        更新题目统计

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param obj: 更新统计参数
        """
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        await question_statistics_dao.update_stats(db, question_id, obj)


question_service: QuestionService = QuestionService()
