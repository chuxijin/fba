#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.engine.snapshot import snapshot_service
from backend.app.growth.crud import experience_rule_dao
from backend.app.growth.crud.crud_growth_event import growth_event_dao
from backend.app.growth.service.experience_service import experience_service
from backend.app.question_bank.crud.crud_check_in import check_in_dao
from backend.app.question_bank.crud.crud_user_practice_stats import user_practice_stats_dao
from backend.app.question_bank_v2.crud.crud_practice import practice_response_dao
from backend.common.log import log
from backend.utils.timezone import timezone

#: 练习答对经验的事件编码，对应 experience_rule.event_code
PRACTICE_CORRECT_EVENT = 'practice_correct'

#: 签到经验的事件编码，对应 experience_rule.event_code
CHECK_IN_EVENT = 'check_in'

#: 签到奖励周期天数，与 experience_rule.cycle_day 取值范围一致
CHECK_IN_CYCLE_DAYS = 7


@dataclass(frozen=True)
class PracticeReward:
    """练习交卷奖励发放结果，未达门槛或发放失败时保持默认零值"""

    reward_exp: int = 0
    practice_reward_exp: int = 0
    check_in_reward_exp: int = 0
    tier_grade: int | None = None
    exp: int | None = None
    available_exp: int | None = None
    is_auto_checked_in: bool = False
    check_in_streak: int | None = None


class PracticeRewardService:
    """练习会话交卷后的经验发放"""

    @staticmethod
    def _source_key(session_id: int) -> str:
        """经验来源键：一个会话只发一次"""
        return f'{PRACTICE_CORRECT_EVENT}:{session_id}'

    @staticmethod
    def _reward_idempotency_key(*, user_id: int, session_id: int) -> str:
        """与 ExperienceService.add_experience 内部拼法一致，用于回查已发放记录"""
        return f'exp_add:{user_id}:{PRACTICE_CORRECT_EVENT}:{PracticeRewardService._source_key(session_id)}'

    @staticmethod
    async def grant_practice_correct_experience(
        *,
        db: AsyncSession,
        user_id: int,
        session_id: int,
        answered_count: int,
        correct_count: int,
    ) -> PracticeReward:
        """
        按答对题数发放练习经验

        门槛来自 experience_rule：答对至少 1 题、命中启用的 practice_correct 规则（含权益差异）、
        达到最低做题数与最低练习时长。重复交卷由经验幂等键兜底，不会重复发放。

        作答时长查询与发放一起放在保存点内：奖励是交卷的副作用，任何失败都只记 warning 并返回零值，
        绝不能反过来阻断交卷。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 练习会话 ID
        :param answered_count: 已提交题数
        :param correct_count: 答对题数
        :return:
        """
        try:
            async with db.begin_nested():
                total_duration = await PracticeRewardService._total_duration_seconds(db=db, session_id=session_id)
                return await PracticeRewardService._grant(
                    db=db,
                    user_id=user_id,
                    session_id=session_id,
                    answered_count=answered_count,
                    correct_count=correct_count,
                    total_duration=total_duration,
                )
        except SQLAlchemyError as exc:
            log.warning(
                'practice_reward_grant_failed | user_id={} session_id={} error={}',
                user_id,
                session_id,
                exc,
            )
            return PracticeReward()

    @staticmethod
    async def _total_duration_seconds(*, db: AsyncSession, session_id: int) -> int:
        """累计有效作答时长（秒），与整场报告同口径：逐题 duration_ms 求和"""
        total_ms = await practice_response_dao.get_total_duration_ms(db, session_id)
        return int(total_ms // 1000)

    @staticmethod
    async def _grant(
        *,
        db: AsyncSession,
        user_id: int,
        session_id: int,
        answered_count: int,
        correct_count: int,
        total_duration: int,
    ) -> PracticeReward:
        """命中规则并发放经验"""
        if correct_count <= 0:
            return PracticeReward()

        snapshot = await snapshot_service.load(db, user_id=user_id, ts=timezone.now())
        rule = await experience_rule_dao.get_active_rule(
            db,
            event_code=PRACTICE_CORRECT_EVENT,
            held_entitlement_codes=snapshot.all_entitlement_codes,
        )
        if rule is None:
            return PracticeReward()
        if answered_count < rule.min_practice_count:
            return PracticeReward()
        if total_duration < rule.min_practice_duration:
            return PracticeReward()

        exp_delta = rule.exp_delta * correct_count
        if exp_delta <= 0:
            return PracticeReward()

        progress = await experience_service.add_experience(
            db,
            user_id=user_id,
            exp_delta=exp_delta,
            source=PRACTICE_CORRECT_EVENT,
            source_key=PracticeRewardService._source_key(session_id),
            reason=f'完成练习答对 {correct_count} 题奖励',
        )
        return PracticeReward(
            reward_exp=exp_delta,
            practice_reward_exp=exp_delta,
            tier_grade=progress.get('current_grade'),
            exp=progress.get('total_exp'),
            available_exp=progress.get('available_exp'),
        )

    @staticmethod
    async def resolve_granted_practice_reward(
        *,
        db: AsyncSession,
        user_id: int,
        session_id: int,
    ) -> PracticeReward:
        """
        回查本会话已经发放过的练习奖励

        重复交卷（客户端重试、用户二次点交卷）走幂等分支时，用它把上次发放的结果原样返回，
        既不再发一次，也不会让前端丢掉"本次 +N 经验"的展示。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 练习会话 ID
        :return:
        """
        try:
            async with db.begin_nested():
                event = await growth_event_dao.get_by_idempotency_key(
                    db,
                    PracticeRewardService._reward_idempotency_key(user_id=user_id, session_id=session_id),
                )
                if event is None:
                    return PracticeReward()
                progress = await experience_service.get_user_progress(db, user_id=user_id) or {}
                return PracticeReward(
                    reward_exp=event.exp_delta,
                    practice_reward_exp=event.exp_delta,
                    tier_grade=progress.get('current_grade'),
                    exp=progress.get('total_exp'),
                    available_exp=progress.get('available_exp'),
                )
        except SQLAlchemyError as exc:
            log.warning(
                'practice_reward_lookup_failed | user_id={} session_id={} error={}',
                user_id,
                session_id,
                exc,
            )
            return PracticeReward()

    @staticmethod
    async def try_auto_check_in(*, db: AsyncSession, user_id: int) -> PracticeReward:
        """
        交卷后尝试自动签到

        当天已签到、缺少启用的签到规则、或今日练习未达门槛时静默跳过。
        签到记录写既有的 study_user_check_in 表（打卡日历与连签的事实表），
        但"今日练习进度"按 v2 表统计 —— 旧口径读的 SessionQuestion 在 v2 流程下不再更新。

        与练习经验一样放在保存点内并只记 warning：签到失败不能阻断交卷。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        try:
            async with db.begin_nested():
                return await PracticeRewardService._auto_check_in(db=db, user_id=user_id)
        except SQLAlchemyError as exc:
            log.warning('auto_check_in_failed | user_id={} error={}', user_id, exc)
            return PracticeReward()

    @staticmethod
    async def _auto_check_in(*, db: AsyncSession, user_id: int) -> PracticeReward:
        """命中签到规则后写打卡记录并发经验"""
        now = timezone.now()
        today = now.date()

        if await check_in_dao.get_by_user_and_date(db, user_id, today) is not None:
            return PracticeReward()

        streak_before_today = await check_in_dao.get_streak(db, user_id)
        cycle_day = (streak_before_today % CHECK_IN_CYCLE_DAYS) + 1

        snapshot = await snapshot_service.load(db, user_id=user_id, ts=now)
        rule = await experience_rule_dao.get_active_rule(
            db,
            event_code=CHECK_IN_EVENT,
            cycle_day=cycle_day,
            held_entitlement_codes=snapshot.all_entitlement_codes,
        )
        if rule is None:
            return PracticeReward()

        summary = await practice_response_dao.get_today_practice_summary(
            db,
            user_id=user_id,
            since=PracticeRewardService._today_start(now),
        )
        if summary['practice_count'] < rule.min_practice_count:
            return PracticeReward()
        if summary['duration_seconds'] < rule.min_practice_duration:
            return PracticeReward()

        await check_in_dao.check_in(
            db,
            user_id,
            practice_count=summary['practice_count'],
            practice_duration=summary['duration_seconds'],
        )

        reward_exp = int(rule.exp_delta or 0)
        progress: dict[str, Any] | None = None
        if reward_exp > 0:
            progress = await experience_service.add_experience(
                db,
                user_id=user_id,
                exp_delta=reward_exp,
                source=CHECK_IN_EVENT,
                source_key=PracticeRewardService._check_in_source_key(user_id=user_id, check_date=today),
                reason=f'连续签到第 {cycle_day} 天奖励',
            )

        streak = await check_in_dao.get_streak(db, user_id)
        await PracticeRewardService._sync_streak_days(db=db, user_id=user_id, streak=streak)

        return PracticeReward(
            reward_exp=reward_exp,
            check_in_reward_exp=reward_exp,
            tier_grade=(progress or {}).get('current_grade'),
            exp=(progress or {}).get('total_exp'),
            available_exp=(progress or {}).get('available_exp'),
            is_auto_checked_in=True,
            check_in_streak=streak,
        )

    @staticmethod
    async def resolve_granted_check_in_reward(*, db: AsyncSession, user_id: int) -> PracticeReward:
        """
        回查今日已发放的签到奖励

        重复交卷走幂等分支时，用它把今天这次签到原样返回，既不重复签到，也不丢展示。

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        try:
            async with db.begin_nested():
                today = timezone.now().date()
                if await check_in_dao.get_by_user_and_date(db, user_id, today) is None:
                    return PracticeReward()
                event = await growth_event_dao.get_by_idempotency_key(
                    db,
                    PracticeRewardService._check_in_reward_idempotency_key(user_id=user_id, check_date=today),
                )
                progress = await experience_service.get_user_progress(db, user_id=user_id) or {}
                reward_exp = int(event.exp_delta) if event is not None else 0
                return PracticeReward(
                    reward_exp=reward_exp,
                    check_in_reward_exp=reward_exp,
                    tier_grade=progress.get('current_grade'),
                    exp=progress.get('total_exp'),
                    available_exp=progress.get('available_exp'),
                    is_auto_checked_in=True,
                    check_in_streak=await check_in_dao.get_streak(db, user_id),
                )
        except SQLAlchemyError as exc:
            log.warning('check_in_reward_lookup_failed | user_id={} error={}', user_id, exc)
            return PracticeReward()

    @staticmethod
    async def _sync_streak_days(*, db: AsyncSession, user_id: int, streak: int) -> None:
        """把连续签到天数同步到旧统计表：坚持天数榜读的是它"""
        stats = await user_practice_stats_dao.get_or_create(db, user_id)
        if stats.streak_days != streak:
            await user_practice_stats_dao.update_model(db, stats.id, {'streak_days': streak})

    @staticmethod
    def _check_in_source_key(*, user_id: int, check_date: date) -> str:
        """签到来源键：一个用户一天只发一次"""
        return f'{CHECK_IN_EVENT}:{user_id}:{check_date.isoformat()}'

    @staticmethod
    def _check_in_reward_idempotency_key(*, user_id: int, check_date: date) -> str:
        """与 ExperienceService.add_experience 内部拼法一致，用于回查当日签到经验"""
        source_key = PracticeRewardService._check_in_source_key(user_id=user_id, check_date=check_date)
        return f'exp_add:{user_id}:{CHECK_IN_EVENT}:{source_key}'

    @staticmethod
    def _today_start(now: datetime) -> datetime:
        """当天零点（带时区），用于统计今日练习"""
        return datetime.combine(now.date(), datetime.min.time(), tzinfo=timezone.tz_info)


practice_reward_service: PracticeRewardService = PracticeRewardService()
