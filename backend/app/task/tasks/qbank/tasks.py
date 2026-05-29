#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题库相关定时任务"""
import logging

from datetime import datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy import func, select, update
from sqlalchemy.orm import selectinload

from backend.app.question_bank.crud.crud_daily_rank import daily_rank_dao
from backend.app.question_bank.crud.crud_user_bank_progress import user_bank_progress_dao
from backend.app.question_bank.crud.crud_user_practice_stats import user_practice_stats_dao
from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.model import (
    PracticeRecord,
    PracticeSession,
    Question,
    UserAccount,
)
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


@celery_app.task(name='update_daily_user_ranks')
async def update_daily_user_ranks() -> dict:
    """
    更新每日用户排名（每天0:05执行）

    计算昨天的用户练习数据并生成排名
    """
    try:
        result = await _update_daily_user_ranks()
        logger.info(f"排名更新完成: 共更新 {result['total_users']} 个用户排名")
        return result
    except Exception as e:
        logger.error(f"排名更新失败: {str(e)}")
        return {'total_users': 0, 'error': str(e)}


async def _update_daily_user_ranks() -> dict:
    """更新每日用户排名的异步实现"""
    async with async_db_session() as db:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        today_start = datetime.combine(today, datetime.min.time())

        stmt = (
            select(
                UserAccount.user_id.label('user_id'),
                func.count(PracticeRecord.id).label('practice_count'),
                func.sum(func.cast(PracticeRecord.is_correct, sa.Integer)).label('correct_count'),
            )
            .outerjoin(
                PracticeRecord,
                (PracticeRecord.user_id == UserAccount.user_id)
                & (PracticeRecord.created_time >= yesterday_start)
                & (PracticeRecord.created_time < today_start),
            )
            .group_by(UserAccount.user_id)
            .order_by(func.count(PracticeRecord.id).desc())
        )

        result = await db.execute(stmt)
        user_stats = result.all()

        total_users = len(user_stats)
        created_count = 0

        for rank, row in enumerate(user_stats, 1):
            practice_count = row.practice_count or 0
            correct_count = row.correct_count or 0

            beat_percentage = (
                Decimal((total_users - rank) / total_users * 100).quantize(Decimal('0.01'))
                if total_users > 0
                else Decimal('0')
            )

            accuracy_rate = (
                Decimal((correct_count / practice_count) * 100).quantize(Decimal('0.01'))
                if practice_count > 0
                else Decimal('0')
            )

            await daily_rank_dao.create_rank_record(
                db=db,
                user_id=row.user_id,
                rank_date=yesterday,
                rank=rank,
                total_users=total_users,
                beat_percentage=beat_percentage,
                practice_count=practice_count,
                correct_count=correct_count,
                accuracy_rate=accuracy_rate,
            )
            created_count += 1

        await db.commit()

        return {
            'total_users': total_users,
            'created_ranks': created_count,
            'rank_date': str(yesterday),
        }


@celery_app.task(name='simulate_bot_activity')
async def simulate_bot_activity() -> dict:
    """
    模拟机器人每日活动（每天凌晨 2:00 执行）

    自动创建新机器人用户并模拟已有机器人的刷题行为
    """
    from backend.app.question_bank.service.bot_service import run_bot_simulation

    try:
        result = await run_bot_simulation()
        logger.info(f'机器人模拟完成: {result}')
        return result
    except Exception as e:
        logger.error(f'机器人模拟失败: {str(e)}')
        return {'error': str(e)}


@celery_app.task(name='qbank_process_record_side_effects')
async def process_record_side_effects(
    user_id: int,
    session_id: int,
    record_ids: list[int],
    allow_judge_now: bool = True,
) -> dict:
    """
    异步处理答题记录的副作用：服务端判题 + 错题本维护 + 进度同步 + 统计快照 + 缓存失效

    :param user_id: 用户 ID
    :param session_id: 会话 ID
    :param record_ids: 已落盘的 PracticeRecord ID 列表
    :param allow_judge_now: 是否允许立即判题（考试模式下应为 False）
    :return:
    """
    from backend.app.question_bank.service.question_service import QuestionService
    from backend.app.question_bank.service.user_settings_service import user_settings_service

    if not record_ids:
        return {'processed': 0}

    SUBJECTIVE_TYPES = {'shortAnswer', 'essay'}

    judge_time = timezone.now()
    wrong_create_rows: list[dict] = []
    wrong_update_rows: list[dict] = []
    objective_count = 0
    correct_count = 0
    duration_sum = 0

    async with async_db_session.begin() as db:
        # 1. 加载记录
        record_stmt = select(PracticeRecord).where(PracticeRecord.id.in_(record_ids))
        records = (await db.execute(record_stmt)).scalars().all()
        if not records:
            return {'processed': 0}

        # 2. 服务端判题（仅 allow_judge_now 时执行；考试模式跳过判题保持 is_correct=NULL）
        if allow_judge_now:
            question_ids = list({r.question_id for r in records})
            q_stmt = (
                select(Question)
                .where(Question.id.in_(question_ids))
                .options(
                    selectinload(Question.analyses),
                    selectinload(Question.statistics),
                )
            )
            question_map = {q.id: q for q in (await db.execute(q_stmt)).scalars().all()}

            mastery_threshold = await user_settings_service.get_mastery_threshold(
                db=db,
                user_id=user_id,
            )

            existing_wrongs = await wrong_question_dao.list_by_user_and_questions(
                db=db,
                user_id=user_id,
                question_ids=question_ids,
            )
            existing_wrongs_by_qid: dict[int, list] = {}
            for wrong in existing_wrongs:
                existing_wrongs_by_qid.setdefault(wrong.question_id, []).append(wrong)

            for record in records:
                if record.is_correct is not None:
                    continue

                question = question_map.get(record.question_id)
                if not question:
                    continue
                if question.type in SUBJECTIVE_TYPES:
                    continue
                analysis = next(
                    (a for a in question.analyses if a.is_default),
                    question.analyses[0] if question.analyses else None,
                )
                if not analysis or not analysis.answer_data:
                    continue

                is_correct = QuestionService.check_answer(
                    question.type,
                    record.user_answer,
                    analysis.answer_data,
                )
                full = record.full_score or Decimal('0')
                record.is_correct = is_correct
                record.score = full if is_correct else Decimal('0')
                record.judged_at = judge_time

                objective_count += 1
                if is_correct:
                    correct_count += 1
                duration_sum += record.answer_time or 0

                # 错题本维护
                existing_wrong_list = existing_wrongs_by_qid.get(record.question_id, [])
                if is_correct:
                    for existing_wrong in existing_wrong_list:
                        new_streak = existing_wrong.correct_streak + 1
                        is_mastered = existing_wrong.is_mastered or new_streak >= mastery_threshold
                        mastered_time = existing_wrong.mastered_time
                        if is_mastered and mastered_time is None:
                            mastered_time = judge_time
                        wrong_update_rows.append({
                            'filter_wrong_id': existing_wrong.id,
                            'set_wrong_count': existing_wrong.wrong_count,
                            'set_correct_streak': new_streak,
                            'set_last_wrong_time': existing_wrong.last_wrong_time,
                            'set_last_practice_time': judge_time,
                            'set_is_mastered': is_mastered,
                            'set_mastered_time': mastered_time,
                        })
                else:
                    if existing_wrong_list:
                        for existing_wrong in existing_wrong_list:
                            wrong_update_rows.append({
                                'filter_wrong_id': existing_wrong.id,
                                'set_wrong_count': existing_wrong.wrong_count + 1,
                                'set_correct_streak': 0,
                                'set_last_wrong_time': judge_time,
                                'set_last_practice_time': existing_wrong.last_practice_time,
                                'set_is_mastered': False,
                                'set_mastered_time': None,
                            })
                    else:
                        wrong_create_rows.append({
                            'user_id': user_id,
                            'question_id': record.question_id,
                            'placement_id': record.placement_id,
                            'wrong_count': 1,
                            'correct_streak': 0,
                            'first_wrong_time': judge_time,
                            'last_wrong_time': judge_time,
                            'last_practice_time': None,
                            'is_mastered': False,
                            'mastered_time': None,
                            'created_by': user_id,
                        })

            if wrong_create_rows:
                await wrong_question_dao.batch_create(db=db, rows=wrong_create_rows)
            if wrong_update_rows:
                await wrong_question_dao.batch_update(db=db, rows=wrong_update_rows)

        # 3. 会话进度（考试模式也要做）
        count_subq = (
            select(func.count(PracticeRecord.id))
            .where(PracticeRecord.session_id == session_id)
            .scalar_subquery()
        )
        await db.execute(
            update(PracticeSession)
            .where(PracticeSession.id == session_id)
            .values(completed_count=count_subq)
        )

        # 4. 用户练习统计快照（仅 allow_judge_now 时增量）
        if allow_judge_now and objective_count > 0:
            await user_practice_stats_dao.increment(
                db=db,
                user_id=user_id,
                answered=objective_count,
                correct=correct_count,
                duration=duration_sum,
            )

        await user_bank_progress_dao.upsert_by_record_ids(db=db, record_ids=record_ids)

    # 5. Redis 错题统计缓存失效（出事务后做）
    if wrong_create_rows or wrong_update_rows:
        from backend.app.question_bank.service.wrong_question_service import wrong_question_service

        await wrong_question_service._clear_statistics_cache(user_id)

    return {
        'processed': len(record_ids),
        'judged': objective_count,
        'correct': correct_count,
        'wrongs_created': len(wrong_create_rows),
        'wrongs_updated': len(wrong_update_rows),
    }
