#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import random
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from backend.app.question_bank.crud.crud_practice_record import practice_record_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.crud.crud_session_question import session_question_dao
from backend.app.question_bank.crud.crud_question import (
    question_option_stats_dao,
    question_statistics_dao,
)
from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.model import (
    PracticeRecord,
    PracticeSession,
    Question,
    QuestionOption,
    QuestionPlacement,
    SessionQuestion,
)
from backend.app.question_bank.schema.practice import (
    AnswerCardItem,
    BatchUpsertPracticeRecordsParam,
    CreatePracticeSessionParam,
    SessionReport,
    SubmitPracticeSessionParam,
    SubmitPracticeSessionResult,
)
from backend.app.question_bank.schema.question import UpdateQuestionStatisticsParam
from backend.app.question_bank.service.question_service import question_service
from backend.common.exception import errors

log = logging.getLogger(__name__)


class SessionService:
    """练习会话服务类（唯一刷题写入入口）"""

    # ------------------------------------------------------------------
    #  Session 生命周期
    # ------------------------------------------------------------------

    @staticmethod
    async def create_session(
        *, db: AsyncSession, user_id: int, obj: CreatePracticeSessionParam
    ) -> PracticeSession:
        """
        创建练习会话

        流程：解析参数 → 查询挂载 → 建会话 → 批量写 SessionQuestion → 返回

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建会话参数
        :return:
        """
        now = datetime.now()
        limit_count = obj.limit
        shuffle_flag = obj.shuffle

        # ---- 1. 确定挂载列表 ----
        if obj.placement_ids:
            # 前端直接指定挂载 ID
            stmt = (
                select(QuestionPlacement)
                .where(
                    QuestionPlacement.id.in_(obj.placement_ids),
                    QuestionPlacement.is_active.is_(True),
                )
                .join(Question, Question.id == QuestionPlacement.question_id)
                .where(Question.content_status == 10)
                .options(
                    joinedload(QuestionPlacement.bank),
                    joinedload(QuestionPlacement.chapter),
                )
                .order_by(QuestionPlacement.sort_order, QuestionPlacement.question_id)
            )
            result = await db.execute(stmt)
            placements: list[QuestionPlacement] = list(result.unique().scalars().all())
        elif obj.chapter_id:
            # 按章节筛选
            stmt = (
                select(QuestionPlacement)
                .where(
                    QuestionPlacement.chapter_id == obj.chapter_id,
                    QuestionPlacement.is_active.is_(True),
                )
                .join(Question, Question.id == QuestionPlacement.question_id)
                .where(Question.content_status == 10)
                .options(
                    joinedload(QuestionPlacement.bank),
                    joinedload(QuestionPlacement.chapter),
                )
                .order_by(QuestionPlacement.sort_order, QuestionPlacement.question_id)
            )
            result = await db.execute(stmt)
            placements = list(result.unique().scalars().all())
        elif obj.bank_id:
            # 按题库筛选
            stmt = (
                select(QuestionPlacement)
                .where(
                    QuestionPlacement.bank_id == obj.bank_id,
                    QuestionPlacement.is_active.is_(True),
                )
                .join(Question, Question.id == QuestionPlacement.question_id)
                .where(Question.content_status == 10)
                .options(
                    joinedload(QuestionPlacement.bank),
                    joinedload(QuestionPlacement.chapter),
                )
                .order_by(
                    QuestionPlacement.chapter_id,
                    QuestionPlacement.sort_order,
                    QuestionPlacement.question_id,
                )
            )
            result = await db.execute(stmt)
            placements = list(result.unique().scalars().all())
        else:
            placements = []

        if not placements:
            raise errors.NotFoundError(msg='没有可用的题目')

        # ---- 1b. 查询 question.type（QuestionPlacement.question 为 noload） ----
        q_ids = list({p.question_id for p in placements})
        q_type_stmt = select(Question.id, Question.type).where(Question.id.in_(q_ids))
        q_type_rows = (await db.execute(q_type_stmt)).all()
        question_type_map: dict[int, str] = {row[0]: row[1] for row in q_type_rows}

        # ---- 2. 打乱 / 截断 ----
        if shuffle_flag:
            random.shuffle(placements)
        if limit_count and limit_count > 0:
            placements = placements[:limit_count]

        # ---- 3. 推导会话名称 ----
        practice_name = obj.practice_name
        bank_id = obj.bank_id
        chapter_id = obj.chapter_id

        if not practice_name:
            first_placement = placements[0]
            if first_placement.chapter and first_placement.chapter.name:
                practice_name = first_placement.chapter.name
            elif first_placement.bank and first_placement.bank.name:
                practice_name = first_placement.bank.name

        if not bank_id and placements[0].bank_id:
            bank_id = placements[0].bank_id
        if not chapter_id and placements[0].chapter_id:
            chapter_id = placements[0].chapter_id

        # ---- 4. 计算总满分 ----
        total_score = sum(p.score or Decimal('0') for p in placements)

        # ---- 5. 创建会话 ----
        session_dict = {
            'user_id': user_id,
            'session_type': obj.session_type,
            'bank_id': bank_id,
            'chapter_id': chapter_id,
            'practice_name': practice_name,
            'total_count': len(placements),
            'total_score': total_score if total_score > 0 else None,
            'start_time': now,
            'exam_config': obj.exam_config,
            'created_by': user_id,
        }
        new_session = await practice_session_dao.create(db=db, obj_dict=session_dict)

        # ---- 6. 批量写 SessionQuestion 快照 ----
        sq_items = []
        for idx, p in enumerate(placements, start=1):
            sq_items.append({
                'seq_no': idx,
                'question_id': p.question_id,
                'placement_id': p.id,
                'question_type': question_type_map.get(p.question_id, 'single'),
                'full_score': p.score or Decimal('0'),
            })
        await session_question_dao.batch_create(db=db, session_id=new_session.id, items=sq_items)

        log.info(
            'Session created: id=%d user=%d type=%s bank=%s total=%d',
            new_session.id, user_id, obj.session_type, bank_id, len(placements),
        )
        return new_session

    @staticmethod
    async def get_session_detail(*, db: AsyncSession, session_id: int, user_id: int) -> PracticeSession:
        """
        获取练习会话详情（含会话题目快照和答题记录）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        session = await practice_session_dao.get_detail(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        return session

    @staticmethod
    async def get_latest_session(
        *, db: AsyncSession, user_id: int, session_type: str | None = None,
        bank_id: int | None = None, chapter_id: int | None = None
    ) -> PracticeSession | None:
        """
        获取用户最新的进行中会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_type: 会话类型
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :return:
        """
        return await practice_session_dao.get_latest_session(
            db=db, user_id=user_id, session_type=session_type,
            bank_id=bank_id, chapter_id=chapter_id,
        )

    @staticmethod
    async def abandon_session(*, db: AsyncSession, session_id: int, user_id: int) -> int:
        """
        放弃练习会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')

        log.info('Session abandoned: id=%d user=%d', session_id, user_id)
        return await practice_session_dao.abandon_session(db=db, session_id=session_id)

    @staticmethod
    async def delete_session(*, db: AsyncSession, session_id: int, user_id: int) -> int:
        """
        删除练习会话

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')

        return await practice_session_dao.delete(db=db, session_id=session_id)

    # ------------------------------------------------------------------
    #  答题记录 Upsert
    # ------------------------------------------------------------------

    @staticmethod
    async def upsert_records(
        *, db: AsyncSession, user_id: int, obj: BatchUpsertPracticeRecordsParam
    ) -> dict[str, Any]:
        """
        批量创建/更新答题记录（基于 session_id + question_id 幂等）

        当 judge_now=True 且非考试模式时，同步返回每题的判题结果

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 批量提交参数
        :return: 包含 upserted_count 和可选 judge_results 的字典
        """
        session = await practice_session_dao.get(db=db, session_id=obj.session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')
        if session.status != 'in_progress':
            raise errors.ForbiddenError(msg='会话已结束，不可作答')

        # 考试模式不允许即时判题
        allow_judge_now = obj.judge_now and session.session_type != 'exam'

        # 查询会话题目快照，用于验证 question_id 合法性和取 full_score
        session_questions = await session_question_dao.list_by_session(db=db, session_id=obj.session_id)
        sq_map: dict[int, SessionQuestion] = {sq.question_id: sq for sq in session_questions}

        records_dict: list[dict] = []
        for item in obj.records:
            sq = sq_map.get(item.question_id)
            if not sq:
                continue

            records_dict.append({
                'session_id': obj.session_id,
                'user_id': user_id,
                'question_id': item.question_id,
                'placement_id': sq.placement_id,
                'seq_no': sq.seq_no,
                'user_answer': item.user_answer,
                'answer_time': item.answer_time,
                'full_score': sq.full_score,
            })

        if records_dict:
            await practice_record_dao.batch_upsert(db=db, records=records_dict)

        result: dict[str, Any] = {'upserted_count': len(records_dict)}

        # 即时判题：查询对应题目的默认解析，逐题比对
        if allow_judge_now and records_dict:
            question_ids = [r['question_id'] for r in records_dict]
            stmt = (
                select(Question)
                .where(Question.id.in_(question_ids))
                .options(selectinload(Question.analyses))
            )
            q_result = await db.execute(stmt)
            question_map: dict[int, Question] = {q.id: q for q in q_result.scalars().all()}

            judge_results: list[dict[str, Any]] = []
            for rd in records_dict:
                question = question_map.get(rd['question_id'])
                if not question:
                    judge_results.append({
                        'question_id': rd['question_id'], 'is_correct': None, 'correct_answer': None,
                    })
                    continue

                analysis = None
                if question.analyses:
                    analysis = next((a for a in question.analyses if a.is_default), question.analyses[0])

                is_correct = False
                correct_answer = None
                if analysis and analysis.answer_data:
                    correct_answer = analysis.answer_data.get('correct')
                    is_correct = question_service.check_answer(
                        question.type, rd['user_answer'], analysis.answer_data,
                    )

                judge_results.append({
                    'question_id': rd['question_id'],
                    'is_correct': is_correct,
                    'correct_answer': correct_answer,
                })

            result['judge_results'] = judge_results

        return result

    @staticmethod
    async def get_record(*, db: AsyncSession, record_id: int, user_id: int) -> PracticeRecord:
        """
        获取答题记录详情

        :param db: 数据库会话
        :param record_id: 记录 ID
        :param user_id: 用户 ID
        :return:
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
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        return await practice_record_dao.get_by_session(db=db, session_id=session_id)

    # ------------------------------------------------------------------
    #  提交会话（判题 + 统计 + 错题本 一次事务）
    # ------------------------------------------------------------------

    @staticmethod
    async def submit_session(
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        obj: SubmitPracticeSessionParam,
    ) -> SubmitPracticeSessionResult:
        """
        提交练习会话并统一判题

        流程：锁会话行 → 判题 → 更新记录 → 更新全站统计 → 写错题本 → 标记完成

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :param obj: 提交参数
        :return:
        """
        # 1. 加锁查询会话，防并发重复提交
        lock_stmt = (
            select(PracticeSession)
            .where(PracticeSession.id == session_id)
            .with_for_update()
        )
        result = await db.execute(lock_stmt)
        session = result.scalars().first()

        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此会话')
        if session.status == 'completed':
            # 幂等：已提交直接返回上次结果
            return SubmitPracticeSessionResult(
                completed_count=session.completed_count,
                correct_count=session.correct_count,
                wrong_count=session.wrong_count,
                accuracy_rate=session.accuracy_rate,
                score=session.score,
                total_score=session.total_score,
            )
        if session.status != 'in_progress':
            raise errors.ForbiddenError(msg='会话状态异常，无法提交')

        # 考试模式：校验时间限制
        if session.session_type == 'exam' and session.exam_config:
            time_limit = session.exam_config.get('time_limit')
            if time_limit and obj.total_time > time_limit:
                raise errors.ForbiddenError(msg=f'考试已超时（限时 {time_limit} 秒）')

        # 2. 查询答题记录 + 题目 + 解析
        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)
        if not records:
            raise errors.NotFoundError(msg='没有答题记录可提交')

        question_ids = [r.question_id for r in records]
        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(selectinload(Question.analyses))
        )
        q_result = await db.execute(stmt)
        question_map: dict[int, Question] = {q.id: q for q in q_result.scalars().all()}

        # 查询 SessionQuestion 快照（取 placement_id / full_score）
        session_questions = await session_question_dao.list_by_session(db=db, session_id=session_id)
        sq_map: dict[int, SessionQuestion] = {sq.question_id: sq for sq in session_questions}

        submit_time = datetime.now()
        judge_version = obj.judge_version
        total_score = Decimal('0')
        earned_score = Decimal('0')

        # 3. 遍历判题
        for record in records:
            question = question_map.get(record.question_id)
            if not question:
                continue

            # 取默认解析
            analysis = None
            if question.analyses:
                analysis = next((a for a in question.analyses if a.is_default), question.analyses[0])

            is_correct = False
            if analysis and analysis.answer_data:
                is_correct = question_service.check_answer(
                    question.type,
                    record.user_answer,
                    analysis.answer_data,
                )

            # 计算得分
            sq = sq_map.get(record.question_id)
            full = sq.full_score if sq else record.full_score
            score = full if is_correct else Decimal('0')
            total_score += full
            earned_score += score

            # 3a. 更新记录判题结果
            await practice_record_dao.update_judge_result(
                db=db,
                record_id=record.id,
                is_correct=is_correct,
                score=score,
                full_score=full,
                judged_at=submit_time,
                judge_version=judge_version,
            )

            # 3b. 更新全站题目统计
            stats_param = UpdateQuestionStatisticsParam(
                attempt_count=1,
                correct_count=1 if is_correct else 0,
                answer_time=record.answer_time,
                wrong_option=(
                    record.user_answer
                    if not is_correct and question.type in ['single', 'judgement']
                    else None
                ),
            )
            await question_statistics_dao.update_stats(db, record.question_id, stats_param)

            # 3c. 更新选项统计
            placement_id = sq.placement_id if sq else record.placement_id
            selected_codes = question_service.parse_selected_option_codes(
                question_type=question.type,
                user_answer=record.user_answer,
            )
            if selected_codes:
                await question_option_stats_dao.increment_by_codes(
                    db,
                    placement_id=placement_id,
                    question_id=record.question_id,
                    option_codes=selected_codes,
                    is_correct=is_correct,
                )

            # 3d. 更新错题本
            if not is_correct:
                existing_wrong = await wrong_question_dao.get_by_user_and_question(
                    db, user_id=user_id, question_id=record.question_id,
                    placement_id=placement_id,
                )
                if existing_wrong:
                    await wrong_question_dao.increment_wrong(db, existing_wrong.id, submit_time)
                else:
                    await wrong_question_dao.create(
                        db, user_id=user_id, question_id=record.question_id,
                        wrong_time=submit_time, placement_id=placement_id,
                    )
            else:
                # 答对：如果在错题本中则增加连续做对次数
                existing_wrong = await wrong_question_dao.get_by_user_and_question(
                    db, user_id=user_id, question_id=record.question_id,
                    placement_id=placement_id,
                )
                if existing_wrong:
                    await wrong_question_dao.increment_correct(db, existing_wrong.id, submit_time)

        # 4. 计算汇总（update_judge_result 走 SQL update 不刷 ORM 属性，用本地变量统计）
        correct_ids: set[int] = set()
        for record in records:
            question = question_map.get(record.question_id)
            if not question:
                continue
            analysis = None
            if question.analyses:
                analysis = next((a for a in question.analyses if a.is_default), question.analyses[0])
            if analysis and analysis.answer_data:
                if question_service.check_answer(question.type, record.user_answer, analysis.answer_data):
                    correct_ids.add(record.question_id)

        completed_count = len(records)
        correct_count = len(correct_ids)
        wrong_count = completed_count - correct_count

        # 5. 标记会话完成
        await practice_session_dao.mark_completed(
            db=db,
            session_id=session_id,
            submit_time=submit_time,
            completed_count=completed_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
            total_time=obj.total_time,
            score=earned_score if earned_score > 0 else None,
            total_score=total_score if total_score > 0 else None,
        )

        log.info(
            'Session submitted: id=%d user=%d completed=%d correct=%d wrong=%d score=%s',
            session_id, user_id, completed_count, correct_count, wrong_count, earned_score,
        )
        return SubmitPracticeSessionResult(
            completed_count=completed_count,
            correct_count=correct_count,
            wrong_count=wrong_count,
            accuracy_rate=(
                Decimal(str(round(correct_count / completed_count * 100, 2)))
                if completed_count > 0 else Decimal('0')
            ),
            score=earned_score if earned_score > 0 else None,
            total_score=total_score if total_score > 0 else None,
        )

    # ------------------------------------------------------------------
    #  报告 / 解析
    # ------------------------------------------------------------------

    @staticmethod
    async def get_session_report(*, db: AsyncSession, session_id: int, user_id: int) -> SessionReport:
        """
        获取会话答题报告

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        session = await practice_session_dao.get_detail(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        # 构造答题卡 + 错题列表
        record_map: dict[int, PracticeRecord] = {r.question_id: r for r in session.records}
        answer_items: list[AnswerCardItem] = []
        wrong_question_ids: list[int] = []

        for sq in session.session_questions:
            record = record_map.get(sq.question_id)

            if record is None:
                status = 'unanswered'
                answer_time = 0
            elif record.is_correct:
                status = 'correct'
                answer_time = record.answer_time or 0
            else:
                status = 'wrong'
                answer_time = record.answer_time or 0
                wrong_question_ids.append(sq.question_id)

            answer_items.append(
                AnswerCardItem(
                    seq_no=sq.seq_no,
                    question_id=sq.question_id,
                    placement_id=sq.placement_id,
                    status=status,
                    answer_time=answer_time,
                )
            )

        unanswered_count = session.total_count - session.completed_count

        return SessionReport(
            session_id=session.id,
            session_type=session.session_type,
            status=session.status,
            bank_id=session.bank_id,
            chapter_id=session.chapter_id,
            total_count=session.total_count,
            completed_count=session.completed_count,
            correct_count=session.correct_count,
            wrong_count=session.wrong_count,
            unanswered_count=unanswered_count,
            accuracy_rate=session.accuracy_rate,
            total_time=session.total_time,
            answer_items=answer_items,
            wrong_question_ids=wrong_question_ids,
        )

    @staticmethod
    async def get_session_solution(
        *, db: AsyncSession, session_id: int, user_id: int
    ) -> list[dict]:
        """
        获取会话全部题目的答案与解析

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return: 逐题解析列表
        """
        session = await practice_session_dao.get_detail(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        # 批量查题目 + 解析 + 选项
        question_ids = [sq.question_id for sq in session.session_questions]
        if not question_ids:
            return []

        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(
                selectinload(Question.analyses),
                selectinload(Question.options).joinedload(QuestionOption.content_ref),
            )
        )
        result = await db.execute(stmt)
        question_map: dict[int, Question] = {q.id: q for q in result.scalars().all()}

        record_map: dict[int, PracticeRecord] = {r.question_id: r for r in session.records}

        solutions: list[dict] = []
        for sq in session.session_questions:
            q = question_map.get(sq.question_id)
            if not q:
                continue

            record = record_map.get(sq.question_id)
            analysis = None
            if q.analyses:
                analysis = next((a for a in q.analyses if a.is_default), q.analyses[0])

            correct_answer = None
            if analysis and analysis.answer_data:
                correct_answer = analysis.answer_data.get('correct')

            options_data = question_service.build_options_data(question=q)
            options_list = list(options_data.values()) if options_data and isinstance(options_data, dict) else None

            solutions.append({
                'seq_no': sq.seq_no,
                'question_id': q.id,
                'placement_id': sq.placement_id,
                'content': q.stem,
                'type': q.type,
                'options': options_list,
                'correct_answer': correct_answer,
                'analysis': analysis.content if analysis else None,
                'user_answer': record.user_answer if record else None,
                'is_correct': record.is_correct if record else None,
                'score': record.score if record else None,
                'full_score': sq.full_score,
                'answer_time': record.answer_time if record else 0,
            })

        return solutions

    # ------------------------------------------------------------------
    #  列表查询（包装 DAO，避免 API 层直接访问 DAO）
    # ------------------------------------------------------------------

    @staticmethod
    async def get_session_list_select(
        *,
        user_id: int,
        session_type: str | None = None,
        status: str | None = None,
    ) -> select:
        """
        获取会话列表查询表达式

        :param user_id: 用户 ID
        :param session_type: 会话类型
        :param status: 状态
        :return:
        """
        return await practice_session_dao.get_select(
            user_id=user_id, session_type=session_type, status=status,
        )

    @staticmethod
    async def get_record_list_select(
        *,
        user_id: int,
        session_id: int | None = None,
        question_id: int | None = None,
    ) -> select:
        """
        获取答题记录列表查询表达式

        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :param question_id: 题目 ID
        :return:
        """
        return await practice_record_dao.get_select(
            user_id=user_id, session_id=session_id, question_id=question_id,
        )


session_service: SessionService = SessionService()
