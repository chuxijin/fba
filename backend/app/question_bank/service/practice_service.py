#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
刷题服务类

设计原则：
- 专门为客户端刷题场景提供简化的服务接口
- 不重复实现业务逻辑，而是调用 question_service
- 提供符合刷题流程的便捷方法
"""
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_question import question_dao, question_statistics_dao
from backend.app.question_bank.crud.crud_practice_record import practice_record_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.model import (
    PracticeRecord,
    PracticeSession,
    Question,
    QuestionAnalysis,
    QuestionBank,
    QuestionChapter,
)
from backend.app.question_bank.schema.practice import (
    BankProgressItem,
    ChapterProgressItem,
    UserStatistics,
    UserStatisticsSummary,
)
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors


class PracticeService:
    """刷题服务类"""

    @staticmethod
    async def get_practice_questions(
        *,
        db: AsyncSession,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
    ) -> Sequence[Question]:
        """
        获取可练习的题目列表（不含答案）

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :return:
        """
        questions = await question_dao.get_all(
            db=db,
            bank_id=bank_id,
            chapter_id=chapter_id,
            type=type,
            difficulty=difficulty,
            is_active=True,  # 只返回启用的题目
            review_status=10,  # 只返回已审核通过的题目
        )
        return questions

    @staticmethod
    async def get_question_for_practice(*, db: AsyncSession, question_id: int) -> Question:
        """
        获取题目详情用于练习（不含答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get_with_relations(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')
        if not question.is_active:
            raise errors.NotFoundError(msg='题目已禁用')
        if question.review_status != 10:
            raise errors.NotFoundError(msg='题目未通过审核')
        return question

    @staticmethod
    async def get_practice_analysis(*, db: AsyncSession, question_id: int) -> QuestionAnalysis:
        """
        查看题目解析（刷题后查看答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        # 调用 question_service 的获取解析方法，并增加查看次数
        analysis = await question_service.get_analysis(db=db, question_id=question_id, increment_view=True)
        return analysis

    @staticmethod
    async def get_user_statistics(
        *,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
    ) -> UserStatistics:
        """
        获取用户学习统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 分类 ID（可选，筛选指定分类下的题库）
        :return:
        """
        # 1. 查询题库列表（可按分类筛选）
        bank_stmt = select(QuestionBank.id, QuestionBank.q_count, QuestionBank.cat_id)
        if cat_id:
            bank_stmt = bank_stmt.where(QuestionBank.cat_id == cat_id)
        bank_result = await db.execute(bank_stmt)
        bank_rows = bank_result.all()

        # 构建 bank_id -> (q_count, cat_id) 映射
        bank_info_map: dict[int, tuple[int, int]] = {
            row.id: (row.q_count, row.cat_id) for row in bank_rows
        }
        target_bank_ids = list(bank_info_map.keys())

        if not target_bank_ids:
            return UserStatistics(
                banks=[],
                summary=UserStatisticsSummary(
                    total_practiced=0,
                    total_correct=0,
                    total_time=0,
                    bank_count=0,
                ),
            )

        # 2. 统计每个题库的练习数据
        bank_stats_stmt = (
            select(
                PracticeRecord.bank_id,
                func.count(func.distinct(PracticeRecord.question_id)).label('practiced_count'),
                func.count(
                    func.distinct(
                        sa.case(
                            (PracticeRecord.is_correct.isnot(None), PracticeRecord.question_id),
                            else_=None
                        )
                    )
                ).label('completed_count'),
                func.sum(func.cast(PracticeRecord.is_correct, sa.Integer)).label('correct_count'),
                func.sum(PracticeRecord.answer_time).label('total_time'),
            )
            .where(
                PracticeRecord.user_id == user_id,
                PracticeRecord.bank_id.in_(target_bank_ids),
            )
            .group_by(PracticeRecord.bank_id)
        )
        bank_stats_result = await db.execute(bank_stats_stmt)
        bank_stats_rows = bank_stats_result.all()

        # 构建 bank_id -> stats 映射
        bank_stats_map: dict[int, dict] = {}
        for row in bank_stats_rows:
            bank_stats_map[row.bank_id] = {
                'practiced_count': row.practiced_count or 0,
                'completed_count': row.completed_count or 0,
                'correct_count': row.correct_count or 0,
                'total_time': row.total_time or 0,
            }

        # 3. 查询章节列表和统计数据
        chapter_stmt = (
            select(
                QuestionChapter.id,
                QuestionChapter.bank_id,
                QuestionChapter.name,
                QuestionChapter.q_count,
                QuestionChapter.sort_order,
            )
            .where(QuestionChapter.bank_id.in_(target_bank_ids))
            .order_by(QuestionChapter.bank_id, QuestionChapter.sort_order)
        )
        chapter_result = await db.execute(chapter_stmt)
        chapter_rows = chapter_result.all()

        # 统计每个章节的练习数据
        chapter_stats_stmt = (
            select(
                PracticeRecord.chapter_id,
                func.count(func.distinct(PracticeRecord.question_id)).label('practiced_count'),
                func.count(
                    func.distinct(
                        sa.case(
                            (PracticeRecord.is_correct.isnot(None), PracticeRecord.question_id),
                            else_=None
                        )
                    )
                ).label('completed_count'),
                func.sum(func.cast(PracticeRecord.is_correct, sa.Integer)).label('correct_count'),
            )
            .where(
                PracticeRecord.user_id == user_id,
                PracticeRecord.bank_id.in_(target_bank_ids),
                PracticeRecord.chapter_id.isnot(None),
            )
            .group_by(PracticeRecord.chapter_id)
        )
        chapter_stats_result = await db.execute(chapter_stats_stmt)
        chapter_stats_rows = chapter_stats_result.all()

        # 构建 chapter_id -> stats 映射
        chapter_stats_map: dict[int, dict] = {}
        for row in chapter_stats_rows:
            chapter_stats_map[row.chapter_id] = {
                'practiced_count': row.practiced_count or 0,
                'completed_count': row.completed_count or 0,
                'correct_count': row.correct_count or 0,
            }

        # 构建 bank_id -> chapters 映射
        bank_chapters_map: dict[int, list[ChapterProgressItem]] = {}
        for row in chapter_rows:
            if row.bank_id not in bank_chapters_map:
                bank_chapters_map[row.bank_id] = []

            chapter_stats = chapter_stats_map.get(row.id, {})
            practiced = chapter_stats.get('practiced_count', 0)
            completed = chapter_stats.get('completed_count', 0)
            correct = chapter_stats.get('correct_count', 0)

            # 🔥 正确率基于已判题的题目
            accuracy = Decimal('0')
            if completed > 0:
                accuracy = Decimal(str(round((correct / completed) * 100, 2)))

            bank_chapters_map[row.bank_id].append(ChapterProgressItem(
                chapter_id=row.id,
                chapter_name=row.name,
                total_count=row.q_count,
                practiced_count=practiced,
                completed_count=completed,
                correct_count=correct,
                accuracy_rate=accuracy,
            ))

        # 4. 查询每个题库的未完成会话
        in_progress_stmt = (
            select(
                PracticeSession.bank_id,
                PracticeSession.id.label('session_id'),
                PracticeSession.completed_count,
            )
            .where(
                PracticeSession.user_id == user_id,
                PracticeSession.status == 'in_progress',
                PracticeSession.bank_id.in_(target_bank_ids),
            )
            .order_by(PracticeSession.updated_time.desc())
        )
        in_progress_result = await db.execute(in_progress_stmt)
        in_progress_rows = in_progress_result.all()

        # 构建 bank_id -> (session_id, completed_count) 映射
        in_progress_map: dict[int, tuple[int, int]] = {}
        for row in in_progress_rows:
            if row.bank_id and row.bank_id not in in_progress_map:
                in_progress_map[row.bank_id] = (row.session_id, row.completed_count or 0)

        # 5. 构建各题库进度数据
        banks: list[BankProgressItem] = []
        total_practiced = 0
        total_correct = 0
        total_time = 0

        for bank_id, (q_count, _) in bank_info_map.items():
            stats = bank_stats_map.get(bank_id, {})
            practiced_count = stats.get('practiced_count', 0)
            completed_count = stats.get('completed_count', 0)
            correct_count = stats.get('correct_count', 0)
            bank_time = stats.get('total_time', 0)

            # 跳过没有练习记录的题库
            if practiced_count == 0:
                continue

            # 🔥 正确率基于已判题的题目
            accuracy_rate = Decimal('0')
            if completed_count > 0:
                accuracy_rate = Decimal(str(round((correct_count / completed_count) * 100, 2)))

            # 获取未完成会话信息
            in_progress_info = in_progress_map.get(bank_id)
            in_progress_session_id = in_progress_info[0] if in_progress_info else None
            in_progress_count = in_progress_info[1] if in_progress_info else 0

            # 获取章节进度
            chapters = bank_chapters_map.get(bank_id, [])

            banks.append(BankProgressItem(
                bank_id=bank_id,
                practiced_count=practiced_count,
                completed_count=completed_count,
                total_count=q_count,
                correct_count=correct_count,
                accuracy_rate=accuracy_rate,
                total_time=bank_time,
                in_progress_session_id=in_progress_session_id,
                in_progress_count=in_progress_count,
                chapters=chapters,
            ))

            # 累计总数
            total_practiced += practiced_count
            total_correct += correct_count
            total_time += bank_time

        # 6. 构建汇总数据
        summary = UserStatisticsSummary(
            total_practiced=total_practiced,
            total_correct=total_correct,
            total_time=total_time,
            bank_count=len(banks),
        )

        return UserStatistics(banks=banks, summary=summary)

    @staticmethod
    async def submit_session_and_judge(
        *,
        db: AsyncSession,
        session_id: int,
        total_time: int,
        submit_time: datetime,
    ) -> dict[str, int | Decimal]:
        """
        提交练习会话并统一判题

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param total_time: 总用时（秒）
        :param submit_time: 提交时间
        :return: 统计数据
        """
        # 1. 查询所有答题记录
        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)

        # 2. 查询题目和答案（批量）
        question_ids = [r.question_id for r in records]
        if question_ids:
            stmt = (
                select(Question)
                .where(Question.id.in_(question_ids), Question.is_active.is_(True))
            )
            result = await db.execute(stmt)
            question_map = {q.id: q for q in result.scalars().all()}

            # 3. 遍历记录，判题并更新
            for record in records:
                question = question_map.get(record.question_id)
                if not question or not question.analysis:
                    continue

                # 调用 question_service 的判题方法
                is_correct = question_service._check_answer(
                    question.type,
                    record.user_answer,
                    question.analysis.answer_data
                )

                # 更新记录的 is_correct
                await practice_record_dao.update_is_correct(db, record.id, is_correct)

                # 🔥 更新题目统计数据（全站正确率和易错项）
                from backend.app.question_bank.schema.question import UpdateQuestionStatisticsParam
                stats_param = UpdateQuestionStatisticsParam(
                    attempt_count=1,
                    correct_count=1 if is_correct else 0,
                    answer_time=record.answer_time,
                    wrong_option=record.user_answer if not is_correct and question.type in ['single', 'judgement'] else None,
                )
                await question_statistics_dao.update_stats(db, record.question_id, stats_param)

        # 4. 重新查询更新后的记录，计算统计数据
        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)
        completed_count = len(records)
        correct_count = sum(1 for r in records if r.is_correct)
        wrong_count = completed_count - correct_count

        # 计算正确率
        accuracy_rate = Decimal('0')
        if completed_count > 0:
            accuracy_rate = Decimal(str(round((correct_count / completed_count) * 100, 2)))

        # 5. 更新会话统计数据
        await practice_session_dao.update_statistics(
            db=db,
            session_id=session_id,
            completed_count=completed_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
            total_time=total_time,
        )

        # 6. 标记为已完成
        await practice_session_dao.submit_session(db=db, session_id=session_id, submit_time=submit_time, score=None)

        return {
            'completed_count': completed_count,
            'correct_count': correct_count,
            'wrong_count': wrong_count,
            'accuracy_rate': accuracy_rate,
        }


practice_service: PracticeService = PracticeService()
