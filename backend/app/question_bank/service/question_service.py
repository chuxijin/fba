#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
题目服务层

设计原则：
- 题目查询不返回答案
- 解析查询返回答案和解析内容
- 答题提交时验证答案并更新统计
- 答错自动加入错题本
"""
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_question import (
    question_analysis_dao,
    question_dao,
    question_statistics_dao,
)
from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.model import (
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionChapter,
    QuestionStatistics,
)
from backend.app.question_bank.schema.question import (
    BatchImportParam,
    BatchImportResult,
    BatchSubmitAnswerParam,
    BatchSubmitAnswerResult,
    CreateQuestionAnalysisParam,
    CreateQuestionParam,
    DeleteQuestionParam,
    ImportResultItem,
    QuestionImportRow,
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
        ids: list[int] | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
        is_active: bool | None = None,
        review_status: int | None = None,
        keyword: str | None = None,
        page: int | None = None,
        size: int | None = None,
        include_analysis: bool = False,
    ) -> Sequence[Question] | dict[str, Any]:
        """
        获取题目列表

        :param db: 数据库会话
        :param ids: 题目 ID 列表（批量查询）
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :param is_active: 是否启用
        :param review_status: 审核状态
        :param keyword: 关键字搜索
        :param page: 页码
        :param size: 每页数量
        :param include_analysis: 是否包含解析（答案）
        :return:
        """
        # 按 ids 批量查询（优先级最高）
        if ids:
            questions = await question_dao.get_by_ids(db, ids, include_analysis=include_analysis)
            return questions

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
            include_analysis=include_analysis,
            include_materials=True,  # 默认加载材料，确保前端能获取到
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

        # Call DAO to create question (handles material_ids internally)
        question = await question_dao.create(db, obj, user_id)

        # 处理多版本解析（新格式，优先）
        if obj.analyses:
            for idx, analysis_item in enumerate(obj.analyses):
                analysis_param = CreateQuestionAnalysisParam(
                    question_id=question.id,
                    answer_data=analysis_item.get('answer_data', {}),
                    content=analysis_item.get('content', ''),
                    type=analysis_item.get('type', 'official'),
                    is_default=analysis_item.get('is_default', idx == 0),  # 第一个默认
                )
                await question_analysis_dao.create(db, analysis_param, user_id)
        # 兼容旧格式（单条解析）
        elif obj.analysis:
            analysis_param = CreateQuestionAnalysisParam(
                question_id=question.id,
                answer_data=obj.analysis.get('answer_data', {}),
                content=obj.analysis.get('content', ''),
                type=obj.analysis.get('type', 'official'),
                is_default=True,
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

        # Call DAO to update question (handles material_ids internally)
        count = await question_dao.update(db, pk, obj, user_id)

        # 处理多版本解析（新格式，优先）
        if obj.analyses is not None:
            # 删除该题目的所有现有解析
            await db.execute(
                select(QuestionAnalysis).where(QuestionAnalysis.question_id == pk)
            )
            await question_analysis_dao.delete_model_by_column(db, allow_multiple=True, question_id=pk)
            
            # 创建新的解析记录
            for idx, analysis_item in enumerate(obj.analyses):
                create_param = CreateQuestionAnalysisParam(
                    question_id=pk,
                    answer_data=analysis_item.get('answer_data', {}),
                    content=analysis_item.get('content', ''),
                    type=analysis_item.get('type', 'official'),
                    is_default=analysis_item.get('is_default', idx == 0),
                )
                await question_analysis_dao.create(db, create_param, user_id)
        # 兼容旧格式（单条解析）
        elif obj.analysis:
            existing_analysis = await question_analysis_dao.get_by_question_id(db, pk)
            if existing_analysis:
                # 更新现有解析
                update_analysis_dict = {
                    'answer_data': obj.analysis.get('answer_data', {}),
                    'content': obj.analysis.get('content', ''),
                    'type': obj.analysis.get('type', 'official'),
                    'updated_by': user_id,
                }
                await question_analysis_dao.update_model_by_column(db, update_analysis_dict, question_id=pk)
            else:
                # 创建新解析
                create_param = CreateQuestionAnalysisParam(
                    question_id=pk,
                    answer_data=obj.analysis.get('answer_data', {}),
                    content=obj.analysis.get('content', ''),
                    type=obj.analysis.get('type', 'official'),
                    is_default=True,
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
    async def get_solution(*, db: AsyncSession, question_id: int, user_answer: str | None = None) -> dict[str, Any]:
        """
        获取题目答案和解析（练题模式专用）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :param user_answer: 用户答案（可选，传入时会返回判题结果）
        :return: 包含 correct_answer、analysis、is_correct 和统计数据的字典
        """
        # 验证题目存在
        question = await question_dao.get(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')

        # 获取解析
        analysis = await question_analysis_dao.get_by_question_id(db, question_id)
        if not analysis:
            raise errors.NotFoundError(msg='题目解析不存在')

        # 🔥 获取统计数据（全站正确率和易错项）
        stats = await question_statistics_dao.get_or_create(db, question_id)

        # 提取正确答案
        correct_answer = analysis.answer_data.get('correct', '')

        # 判题（如果传入了用户答案）
        is_correct = None
        if user_answer is not None:
            # 前端可能传入 JSON 字符串格式的数组（多选题），需要解析
            import json
            try:
                parsed_answer = json.loads(user_answer)
                is_correct = QuestionService._check_answer(question.type, parsed_answer, analysis.answer_data)
            except (json.JSONDecodeError, TypeError):
                # 不是 JSON 格式，直接使用字符串判题
                is_correct = QuestionService._check_answer(question.type, user_answer, analysis.answer_data)

        return {
            'correct_answer': correct_answer,
            'analysis': analysis.content,
            'is_correct': is_correct,
            'correct_rate': stats.correct_rate,  # 🔥 全站正确率
            'wrong_option_stats': stats.wrong_option_stats,  # 🔥 易错项统计
        }

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
    async def batch_submit_answer(*, db: AsyncSession, obj: BatchSubmitAnswerParam, user_id: int) -> BatchSubmitAnswerResult:
        """
        批量提交答案并判分（适合考试/试卷场景）

        :param db: 数据库会话
        :param obj: 批量提交答案参数
        :param user_id: 用户 ID
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

            # 🔥 错题本逻辑：答错自动加入错题本
            if not is_correct:
                # 答错：查找是否已存在错题记录
                existing_wrong = await wrong_question_dao.get_by_user_and_question(
                    db, user_id, answer_item.question_id
                )
                if existing_wrong:
                    # 已存在：增加错误次数，重置连续正确次数
                    await wrong_question_dao.increment_wrong(db, existing_wrong.id, datetime.now())
                else:
                    # 不存在：创建新的错题记录
                    await wrong_question_dao.create(db, user_id, answer_item.question_id, datetime.now())
            else:
                # 答对：如果错题本中存在，增加连续正确次数（连续3次后自动标记为已掌握）
                existing_wrong = await wrong_question_dao.get_by_user_and_question(
                    db, user_id, answer_item.question_id
                )
                if existing_wrong:
                    await wrong_question_dao.increment_correct(db, existing_wrong.id, datetime.now())

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

    # ============ 批量导入相关 ============

    @staticmethod
    async def batch_import(*, db: AsyncSession, obj: BatchImportParam, user_id: int) -> BatchImportResult:
        """
        批量导入题目（从 CSV）

        采用"全有或全无"模式：所有题目验证通过才写入，有任何错误则全部不写入

        :param db: 数据库会话
        :param obj: 批量导入参数
        :param user_id: 用户 ID
        :return:
        """
        # 验证题库存在
        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='题库不存在')

        # 题型映射（中文 → 英文）
        type_mapping = {
            '单选': 'single',
            '单选题': 'single',
            '多选': 'multiple',
            '多选题': 'multiple',
            '判断': 'judgement',
            '判断题': 'judgement',
            '填空': 'fill',
            '填空题': 'fill',
            '简答': 'shortAnswer',
            '简答题': 'shortAnswer',
        }

        # 难度映射（中文 → 英文）
        difficulty_mapping = {
            '简单': 'easy',
            '中等': 'medium',
            '困难': 'hard',
        }

        # 章节缓存（避免重复查询）
        chapter_cache: dict[str, int] = {}

        # ============ 第一阶段：验证所有数据 ============
        validated_rows: list[dict] = []
        validation_errors: list[ImportResultItem] = []

        for row_index, row in enumerate(obj.questions, start=2):
            try:
                # 1️⃣ 验证题型
                question_type = type_mapping.get(row.题型)
                if not question_type:
                    raise ValueError(f'不支持的题型：{row.题型}')

                # 2️⃣ 解析难度
                difficulty = difficulty_mapping.get(row.难度 or '中等', 'medium')

                # 3️⃣ 获取或创建章节（此处只查询，不创建）
                chapter_id = await QuestionService._get_or_create_chapter(
                    db=db,
                    bank_id=obj.bank_id,
                    level1_name=row.一级目录,
                    level2_name=row.二级目录,
                    chapter_cache=chapter_cache,
                )

                # 4️⃣ 构建选项数据
                options_data = None
                if question_type in ['single', 'multiple', 'judgement']:
                    options_data = {}
                    for option_key in ['A', 'B', 'C', 'D']:
                        option_value = getattr(row, f'选项{option_key}', None)
                        if option_value:
                            options_data[option_key] = {
                                'code': option_key,
                                'content': option_value,
                            }

                # 5️⃣ 验证答案格式
                answer_data = QuestionService._parse_answer(row.答案, question_type)

                # 6️⃣ 验证分数
                score = Decimal(str(row.分数 if row.分数 is not None else 1))

                # 保存验证通过的数据
                validated_rows.append({
                    'row_index': row_index,
                    'question_type': question_type,
                    'difficulty': difficulty,
                    'chapter_id': chapter_id,
                    'options_data': options_data,
                    'answer_data': answer_data,
                    'score': score,
                    'stem': row.题目,
                    'analysis_content': row.解析 if row.解析 else '暂无解析',
                })

            except Exception as e:
                validation_errors.append(
                    ImportResultItem(
                        row_number=row_index,
                        success=False,
                        question_id=None,
                        error_message=str(e),
                    )
                )

        # ============ 如果有验证错误，直接返回，不写入任何数据 ============
        if validation_errors:
            return BatchImportResult(
                total=len(obj.questions),
                success_count=0,
                fail_count=len(validation_errors),
                details=validation_errors,
            )

        # ============ 第二阶段：全部验证通过，批量写入数据库 ============
        results: list[ImportResultItem] = []
        chapter_count: dict[int, int] = {}

        for row_data in validated_rows:
            # 创建题目记录
            question = Question(
                bank_id=obj.bank_id,
                chapter_id=row_data['chapter_id'],
                type=row_data['question_type'],
                stem=row_data['stem'],
                options_data=row_data['options_data'],
                difficulty=row_data['difficulty'],
                score=row_data['score'],
                created_by=user_id,
            )
            db.add(question)
            await db.flush()

            # 创建解析记录
            analysis = QuestionAnalysis(
                question_id=question.id,
                answer_data=row_data['answer_data'],
                content=row_data['analysis_content'],
                created_by=user_id,
            )
            db.add(analysis)

            # 记录成功
            results.append(
                ImportResultItem(
                    row_number=row_data['row_index'],
                    success=True,
                    question_id=question.id,
                    error_message=None,
                )
            )

            # 统计章节题目数量
            if row_data['chapter_id']:
                chapter_count[row_data['chapter_id']] = chapter_count.get(row_data['chapter_id'], 0) + 1

        success_count = len(validated_rows)

        # ============ 第三阶段：更新 q_count ============
        if success_count > 0:
            # 更新各章节的 q_count
            for chapter_id, count in chapter_count.items():
                await db.execute(
                    update(QuestionChapter)
                    .where(QuestionChapter.id == chapter_id)
                    .values(q_count=QuestionChapter.q_count + count)
                )

            # 🔥 递归更新题库及其所有父级题库的 q_count
            await QuestionService._update_bank_q_count_recursive(
                db=db,
                bank_id=obj.bank_id,
                delta=success_count,
            )

            await db.flush()

        return BatchImportResult(
            total=len(obj.questions),
            success_count=success_count,
            fail_count=0,
            details=results,
        )

    @staticmethod
    async def _get_or_create_chapter(
        *,
        db: AsyncSession,
        bank_id: int,
        level1_name: str | None,
        level2_name: str | None,
        chapter_cache: dict[str, int],
    ) -> int | None:
        """
        获取或创建章节

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param level1_name: 一级章节名称
        :param level2_name: 二级章节名称
        :param chapter_cache: 章节缓存
        :return: 章节 ID（None 表示无章节）
        """
        # 如果没有章节，返回 None
        if not level1_name:
            return None

        # 1️⃣ 获取或创建一级章节
        cache_key_1 = f'{bank_id}:{level1_name}'
        if cache_key_1 not in chapter_cache:
            level1_chapter = await chapter_dao.get_by_name(
                db=db,
                bank_id=bank_id,
                name=level1_name,
                parent_id=None,
            )
            if not level1_chapter:
                # 创建一级章节
                from backend.app.question_bank.schema.chapter import CreateChapterParam

                level1_param = CreateChapterParam(
                    bank_id=bank_id,
                    name=level1_name,
                    level=1,
                    parent_id=None,
                    sort_order=0,
                )
                await chapter_dao.create(db, level1_param)
                await db.flush()
                # 重新查询获取 ID
                level1_chapter = await chapter_dao.get_by_name(
                    db=db,
                    bank_id=bank_id,
                    name=level1_name,
                    parent_id=None,
                )
            chapter_cache[cache_key_1] = level1_chapter.id

        level1_id = chapter_cache[cache_key_1]

        # 2️⃣ 如果没有二级章节，返回一级章节 ID
        if not level2_name:
            return level1_id

        # 3️⃣ 获取或创建二级章节
        cache_key_2 = f'{bank_id}:{level1_name}:{level2_name}'
        if cache_key_2 not in chapter_cache:
            level2_chapter = await chapter_dao.get_by_name(
                db=db,
                bank_id=bank_id,
                name=level2_name,
                parent_id=level1_id,
            )
            if not level2_chapter:
                # 创建二级章节
                from backend.app.question_bank.schema.chapter import CreateChapterParam

                level2_param = CreateChapterParam(
                    bank_id=bank_id,
                    name=level2_name,
                    level=2,
                    parent_id=level1_id,
                    sort_order=0,
                )
                await chapter_dao.create(db, level2_param)
                await db.flush()
                # 重新查询获取 ID
                level2_chapter = await chapter_dao.get_by_name(
                    db=db,
                    bank_id=bank_id,
                    name=level2_name,
                    parent_id=level1_id,
                )
            chapter_cache[cache_key_2] = level2_chapter.id

        return chapter_cache[cache_key_2]

    @staticmethod
    async def _update_bank_q_count_recursive(*, db: AsyncSession, bank_id: int, delta: int) -> None:
        """
        递归更新题库及其所有父级题库的 q_count

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param delta: 变化量（正数增加，负数减少）
        """
        current_id = bank_id

        while current_id:
            # 更新当前题库的 q_count
            await db.execute(
                update(QuestionBank)
                .where(QuestionBank.id == current_id)
                .values(q_count=QuestionBank.q_count + delta)
            )

            # 获取父级题库 ID
            result = await db.execute(
                select(QuestionBank.parent_id).where(QuestionBank.id == current_id)
            )
            parent_id = result.scalar()
            current_id = parent_id

    @staticmethod
    def _parse_answer(answer_str: str, question_type: str) -> dict:
        """
        解析答案字符串

        :param answer_str: 答案字符串
        :param question_type: 题型
        :return:
        """
        if question_type in ['single', 'judgement']:
            # 单选/判断：直接返回字符串
            return {'correct': answer_str.strip().upper()}

        if question_type == 'multiple':
            # 多选：支持两种格式
            # 1. 逗号分隔：A,B,C
            # 2. 连续字母：ABC
            if ',' in answer_str:
                # 格式 1：逗号分隔
                answers = [ans.strip().upper() for ans in answer_str.split(',')]
            else:
                # 格式 2：连续字母，拆分为单个字母
                answers = [c.upper() for c in answer_str.strip() if c.isalpha()]
            return {'correct': answers}

        if question_type in ['fill', 'shortAnswer']:
            # 填空/简答：分割为列表
            answers = [ans.strip() for ans in answer_str.split(',')]
            return {'correct': answers}

        return {'correct': answer_str}


question_service: QuestionService = QuestionService()
