#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_practice_record import practice_record_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.model import PracticeRecord, PracticeSession, Question, QuestionBank, QuestionChapter
from backend.app.question_bank.schema.practice import (
    AnswerCardItem,
    CreatePracticeSessionParam,
    CreatePracticeRecordParam,
    GetPracticeRecordDetail,
    QuestionSolution,
    SessionReport,
    SessionSolution,
)
from backend.app.question_bank.schema.question import GetQuestionListItem, GetQuestionWithAnswer
from backend.common.exception import errors


class SessionService:
    """练习会话服务类"""

    @staticmethod
    async def create_session(
        *, db: AsyncSession, user_id: int, obj: CreatePracticeSessionParam
    ) -> tuple[PracticeSession, list[GetQuestionListItem]]:
        """
        创建练习会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return: 会话对象和题目列表
        """
        session_dict = obj.model_dump()
        session_dict['start_time'] = datetime.now()
        session_dict['user_id'] = user_id
        session_dict['created_by'] = user_id

        question_ids = session_dict.get('question_ids')
        limit_count = session_dict.pop('limit', None)
        shuffle_flag = session_dict.pop('shuffle', False)

        # 如果没有传 question_ids，根据 chapter_id 或 bank_id 自动获取
        if not question_ids:
            chapter_id = session_dict.get('chapter_id')
            bank_id = session_dict.get('bank_id')

            if chapter_id:
                # 根据章节获取题目 ID 列表
                stmt = (
                    select(Question.id)
                    .where(Question.chapter_id == chapter_id, Question.is_active.is_(True))
                    .order_by(Question.id)
                )
                result = await db.execute(stmt)
                question_ids = [row[0] for row in result.fetchall()]

                # 获取章节名称作为 practice_name
                chapter_result = await db.execute(
                    select(QuestionChapter.name, QuestionChapter.bank_id).where(QuestionChapter.id == chapter_id)
                )
                chapter_row = chapter_result.first()
                if chapter_row:
                    session_dict['practice_name'] = chapter_row.name
                    if not bank_id:
                        session_dict['bank_id'] = chapter_row.bank_id

            elif bank_id:
                # 根据题库获取题目 ID 列表
                stmt = (
                    select(Question.id)
                    .where(Question.bank_id == bank_id, Question.is_active.is_(True))
                    .order_by(Question.chapter_id, Question.id)
                )
                result = await db.execute(stmt)
                question_ids = [row[0] for row in result.fetchall()]

        # 处理随机排序
        if shuffle_flag and question_ids:
            question_ids = list(question_ids)
            random.shuffle(question_ids)

        # 处理数量限制
        if limit_count and limit_count > 0 and question_ids:
            question_ids = question_ids[:limit_count]

        # 更新 question_ids 和 total_count
        session_dict['question_ids'] = question_ids
        session_dict['total_count'] = len(question_ids) if question_ids else 0

        # 查询题库名称并保存到 practice_name（如果还没有设置）
        if not session_dict.get('practice_name') and session_dict.get('bank_id'):
            result = await db.execute(select(QuestionBank.name).where(QuestionBank.id == session_dict['bank_id']))
            bank_name = result.scalar_one_or_none()
            session_dict['practice_name'] = bank_name

        new_session = await practice_session_dao.create(db=db, obj_dict=session_dict)

        # 查询题目详情（不含答案）
        questions_data = []
        if question_ids:
            stmt = select(Question).where(Question.id.in_(question_ids), Question.is_active.is_(True))
            result = await db.execute(stmt)
            question_map = {q.id: q for q in result.scalars().all()}

            # 按 question_ids 顺序返回
            for qid in question_ids:
                q = question_map.get(qid)
                if q:
                    questions_data.append(GetQuestionListItem.model_validate(q))

        return new_session, questions_data

    @staticmethod
    async def get_latest_session(
        *, db: AsyncSession, user_id: int, bank_id: int | None = None, chapter_id: int | None = None
    ) -> PracticeSession | None:
        """
        获取用户最新的进行中会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :return: 会话对象
        """
        session = await practice_session_dao.get_latest_session(
            db=db, user_id=user_id, bank_id=bank_id, chapter_id=chapter_id
        )
        return session

    @staticmethod
    async def get_session_detail(
        *, db: AsyncSession, session_id: int, user_id: int
    ) -> tuple[PracticeSession, list[GetQuestionWithAnswer], dict[int, dict]]:
        """
        获取练习会话详情（包含题目列表和答题记录）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: (会话对象, 题目列表, 用户答案字典)
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        # 查询题目详情（含答案和解析）
        questions_data = []
        if session.question_ids:
            stmt = select(Question).where(Question.id.in_(session.question_ids), Question.is_active.is_(True))
            result = await db.execute(stmt)
            question_map = {q.id: q for q in result.scalars().all()}

            for qid in session.question_ids:
                q = question_map.get(qid)
                if q:
                    # 手动构建 GetQuestionWithAnswer
                    question_dict = {
                        'id': q.id,
                        'bank_id': q.bank_id,
                        'chapter_id': q.chapter_id,
                        'type': q.type,
                        'stem': q.stem,
                        'options_data': q.options_data,
                        'difficulty': q.difficulty,
                        'score': q.score,
                        'knowledge_point': q.knowledge_point,
                        'is_active': q.is_active,
                        'review_status': q.review_status,
                        'created_time': q.created_time,
                        'bank_name': q.bank.name if q.bank else None,
                        'chapter_name': q.chapter.name if q.chapter else None,
                        'answer_data': q.analysis.answer_data if q.analysis else None,
                        'analysis_content': q.analysis.content if q.analysis else None,
                    }
                    questions_data.append(GetQuestionWithAnswer.model_validate(question_dict))

        # 查询用户答题记录
        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)
        user_answers: dict[int, dict] = {}
        for record in records:
            user_answers[record.question_id] = {
                'question_id': record.question_id,
                'user_answer': record.user_answer,
                'answer_time': record.answer_time or 0,
            }

        # 兜底方案：如果 total_time 为 0，从答题记录计算总时间
        if session.total_time == 0 and records:
            calculated_time = sum(r.answer_time or 0 for r in records)
            session.total_time = calculated_time

        return session, questions_data, user_answers

    @staticmethod
    async def update_session_statistics(
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        completed_count: int | None,
        correct_count: int | None,
        wrong_count: int | None,
        total_time: int | None,
    ) -> int:
        """
        更新练习会话统计数据

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :param completed_count: 已完成数量
        :param correct_count: 正确数量
        :param wrong_count: 错误数量
        :param total_time: 总用时
        :return: 更新数量
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')

        count = await practice_session_dao.update_statistics(
            db=db,
            session_id=session_id,
            completed_count=completed_count if completed_count is not None else session.completed_count,
            correct_count=correct_count if correct_count is not None else session.correct_count,
            wrong_count=wrong_count if wrong_count is not None else session.wrong_count,
            total_time=total_time if total_time is not None else session.total_time,
        )
        return count

    @staticmethod
    async def abandon_session(*, db: AsyncSession, session_id: int, user_id: int) -> int:
        """
        放弃练习会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: 更新数量
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')

        count = await practice_session_dao.abandon_session(db=db, session_id=session_id)
        return count

    @staticmethod
    async def delete_session(*, db: AsyncSession, session_id: int, user_id: int) -> int:
        """
        删除练习会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: 删除数量
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')

        count = await practice_session_dao.delete(db=db, session_id=session_id)
        return count

    @staticmethod
    async def create_records(
        *, db: AsyncSession, user_id: int, session_id: int, records: list[CreatePracticeRecordParam]
    ) -> int:
        """
        创建答题记录（支持批量）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :param records: 答题记录列表
        :return: 创建数量
        """
        # 获取会话信息
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')

        # 查询已存在的答题记录
        existing_records = await practice_record_dao.get_by_session(db=db, session_id=session_id)
        existing_question_ids = {r.question_id for r in existing_records}

        # 只创建不存在的记录
        records_dict = []
        for record in records:
            if record.question_id in existing_question_ids:
                continue
            record_dict = record.model_dump()
            record_dict['user_id'] = user_id
            record_dict['session_id'] = session_id
            record_dict['bank_id'] = session.bank_id
            record_dict['chapter_id'] = session.chapter_id
            record_dict['created_by'] = user_id
            records_dict.append(record_dict)

        if records_dict:
            await practice_record_dao.batch_create(db=db, records=records_dict)

        return len(records_dict)

    @staticmethod
    async def get_record(*, db: AsyncSession, record_id: int, user_id: int) -> PracticeRecord:
        """
        获取答题记录详情

        :param db: 数据库会话
        :param record_id: 记录 ID
        :param user_id: 用户 ID
        :return: 答题记录
        """
        record = await practice_record_dao.get(db=db, record_id=record_id)
        if not record:
            raise errors.NotFoundError(msg='记录不存在')
        if record.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此记录')

        return record

    @staticmethod
    async def get_session_records(*, db: AsyncSession, session_id: int, user_id: int) -> list[PracticeRecord]:
        """
        获取会话的所有答题记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: 答题记录列表
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)
        return records

    @staticmethod
    async def get_session_report(*, db: AsyncSession, session_id: int, user_id: int) -> SessionReport:
        """
        获取会话答题报告

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: 答题报告
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        # 查询所有答题记录
        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)

        # 构造答题卡数据和错题列表
        answer_items = []
        wrong_question_ids = []

        if session.question_ids:
            record_map = {r.question_id: r for r in records}

            for index, question_id in enumerate(session.question_ids):
                record = record_map.get(question_id)

                if record is None:
                    status = 'unanswered'
                    answer_time = 0
                elif record.is_correct:
                    status = 'correct'
                    answer_time = record.answer_time or 0
                else:
                    status = 'wrong'
                    answer_time = record.answer_time or 0
                    wrong_question_ids.append(question_id)

                answer_items.append(
                    AnswerCardItem(
                        index=index + 1,
                        question_id=question_id,
                        status=status,
                        answer_time=answer_time,
                    )
                )
        else:
            for index, record in enumerate(records):
                status = 'correct' if record.is_correct else 'wrong'
                if not record.is_correct:
                    wrong_question_ids.append(record.question_id)

                answer_items.append(
                    AnswerCardItem(
                        index=index + 1,
                        question_id=record.question_id,
                        status=status,
                        answer_time=record.answer_time or 0,
                    )
                )

        unanswered_count = session.total_count - session.completed_count

        report_data = SessionReport(
            session_id=session.id,
            bank_id=session.bank_id,
            practice_name=session.practice_name,
            session_type=session.session_type,
            total_count=session.total_count,
            completed_count=session.completed_count,
            correct_count=session.correct_count,
            wrong_count=session.wrong_count,
            unanswered_count=unanswered_count,
            accuracy_rate=session.accuracy_rate,
            total_time=session.total_time,
            status=session.status,
            answer_items=answer_items,
            wrong_question_ids=wrong_question_ids,
        )

        return report_data

    @staticmethod
    async def get_session_solution(*, db: AsyncSession, session_id: int, user_id: int) -> SessionSolution:
        """
        获取会话答案解析

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: 答案解析
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        # 查询题目详情（含答案和解析）
        questions_data = []
        if session.question_ids:
            stmt = select(Question).where(Question.id.in_(session.question_ids), Question.is_active.is_(True))
            result = await db.execute(stmt)
            question_map = {q.id: q for q in result.scalars().all()}

            # 查询用户答题记录
            records = await practice_record_dao.get_by_session(db=db, session_id=session_id)
            record_map = {r.question_id: r for r in records}

            # 按 question_ids 顺序构建解析数据
            for qid in session.question_ids:
                q = question_map.get(qid)
                if not q:
                    continue

                record = record_map.get(qid)

                # 处理选项数据：从 dict 转换为 list
                options_list = None
                if q.options_data and isinstance(q.options_data, dict):
                    options_list = list(q.options_data.values())

                # 处理答案数据
                correct_answer = None
                if q.analysis and q.analysis.answer_data:
                    answer_value = q.analysis.answer_data.get('correct')
                    correct_answer = answer_value if answer_value else None

                # 处理解析内容
                analysis_content = None
                if q.analysis:
                    analysis_content = q.analysis.content

                questions_data.append(
                    QuestionSolution(
                        question_id=q.id,
                        content=q.stem,
                        type=q.type,
                        options=options_list,
                        correct_answer=correct_answer,
                        analysis=analysis_content,
                        user_answer=record.user_answer if record else None,
                        is_correct=record.is_correct if record else None,
                        answer_time=record.answer_time if record and record.answer_time else 0,
                    )
                )

        solution_data = SessionSolution(
            session_id=session.id,
            questions=questions_data,
        )

        return solution_data


session_service = SessionService()
