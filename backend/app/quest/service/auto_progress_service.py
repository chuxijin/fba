#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自动进度型悬赏任务的事件处理器"""

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.quest.crud.crud_quest import quest_claim_dao, quest_dao
from backend.app.quest.model import Quest, QuestClaim, QuestClaimProgress
from backend.common.events import subscribe
from backend.common.log import log
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

_TRIGGER_INVITE_ACCEPTED = 'invite.accepted'
_TRIGGER_USER_REGISTERED = 'user.registered'
_TRIGGER_USER_LOGGED_IN = 'user.logged_in'
_TRIGGER_SESSION_COMPLETED = 'study.session_completed'

# claim_status: 2 审核通过, 4 已发奖, 5 已放弃, 6 已撤销 → 不再推进
_TERMINAL_CLAIM_STATUSES = frozenset({2, 4, 5, 6})


async def _list_active_triggered_quests(db: AsyncSession, trigger_type: str) -> list[Quest]:
    """
    列出指定 trigger_type 且当前有效的进行中任务

    :param db: 数据库会话
    :param trigger_type: 触发类型
    :return:
    """
    stmt = select(Quest).where(
        Quest.trigger_type.contains([trigger_type]),
        Quest.status == 1,
    )
    result = await db.execute(stmt)
    quests = result.scalars().all()

    now = timezone.now()
    active: list[Quest] = []
    for quest in quests:
        if quest.start_time and now < quest.start_time:
            continue
        if quest.end_time and now > quest.end_time:
            continue
        active.append(quest)
    return active


async def _record_progress_idempotent(db: AsyncSession, claim_id: int, source_key: str) -> bool:
    """
    幂等插入进度流水, 返回 True 表示首次记录

    :param db: 数据库会话
    :param claim_id: 领取记录 ID
    :param source_key: 事件幂等键
    :return:
    """
    try:
        async with db.begin_nested():
            db.add(QuestClaimProgress(claim_id=claim_id, source_key=source_key))
    except IntegrityError:
        return False
    return True


async def _get_or_create_claim(*, db: AsyncSession, quest: Quest, user_id: int) -> QuestClaim | None:
    """
    获取或懒创建用户的进行中领取记录

    :param db: 数据库会话
    :param quest: 任务实体
    :param user_id: 用户 ID
    :return:
    """
    existing = await quest_claim_dao.get_active_claim(db, quest.id, user_id)
    if existing:
        return existing

    if quest.total_quota and quest.claimed_count >= quest.total_quota:
        log.info(f'任务名额已满, 跳过自动进度 quest_id={quest.id} user_id={user_id}')
        return None

    # 检查用户已有的未放弃领取数（含已发奖、进行中、待审核等）
    if quest.max_claims_per_user > 0:
        all_count = await quest_claim_dao.count_active_by_user(db, quest.id, user_id)
        if all_count >= quest.max_claims_per_user:
            log.info(f'已达领取上限, 跳过 quest_id={quest.id} user_id={user_id} count={all_count}')
            return None

    now = timezone.now()
    expire_time = None
    if quest.claim_expire_seconds > 0:
        expire_time = now + timedelta(seconds=quest.claim_expire_seconds)

    claim = QuestClaim(
        quest_id=quest.id,
        user_id=user_id,
        claim_status=0,
        claim_time=now,
        expire_time=expire_time,
        progress=0,
    )
    db.add(claim)
    await db.flush()
    await quest_dao.increment_claimed_count(db, quest.id)
    await db.flush()
    return claim


async def _advance_claim(*, db: AsyncSession, quest: Quest, user_id: int, source_key: str) -> None:
    """
    推进单个 Quest 对单个用户的进度

    :param db: 数据库会话
    :param quest: 任务实体
    :param user_id: 用户 ID
    :param source_key: 事件幂等键
    :return:
    """
    # 锁 quest 行, 序列化对同一任务的并发推进, 避免重复建 claim 和重复 +1
    locked_quest = await quest_dao.lock_for_claim(db, quest.id)
    if not locked_quest or locked_quest.status != 1:
        return

    claim = await _get_or_create_claim(db=db, quest=locked_quest, user_id=user_id)
    if not claim:
        return

    if claim.claim_status in _TERMINAL_CLAIM_STATUSES:
        return

    if not await _record_progress_idempotent(db, claim.id, source_key):
        log.info(f'事件已计入, 跳过 claim_id={claim.id} source_key={source_key}')
        return

    claim.progress = (claim.progress or 0) + 1

    target = locked_quest.trigger_target
    if target > 0 and claim.progress >= target:
        now = timezone.now()
        claim.claim_status = 2
        claim.submit_time = claim.submit_time or now
        claim.review_time = now
        await db.flush()

        from backend.app.quest.service.reward_service import reward_service

        await reward_service.grant_for_claim(db=db, claim=claim, quest=locked_quest)


@subscribe(_TRIGGER_INVITE_ACCEPTED)
async def on_invite_accepted(
    *,
    inviter_user_id: int | None = None,
    relation_id: int | None = None,
    **_: Any,
) -> None:
    """
    处理邀请成功事件, 推进所有 trigger_type=invite.accepted 的任务进度

    :param inviter_user_id: 邀请人用户 ID
    :param relation_id: 邀请关系 ID
    :return:
    """
    if not inviter_user_id or not relation_id:
        log.warning(f'invite.accepted 事件缺少必要字段 inviter_user_id={inviter_user_id} relation_id={relation_id}')
        return

    async with async_db_session.begin() as db:
        quests = await _list_active_triggered_quests(db, _TRIGGER_INVITE_ACCEPTED)
        if not quests:
            return

        source_key = f'invite_relation:{relation_id}'
        for quest in quests:
            try:
                await _advance_claim(db=db, quest=quest, user_id=inviter_user_id, source_key=source_key)
            except Exception as exc:
                log.warning(f'推进任务进度异常 quest_id={quest.id} user_id={inviter_user_id} error={exc}')


@subscribe(_TRIGGER_USER_REGISTERED)
async def on_user_registered(
    *,
    user_id: int | None = None,
    **_: Any,
) -> None:
    """
    处理用户注册事件, 推进所有 trigger_type=user.registered 的任务进度

    :param user_id: 用户 ID
    :return:
    """
    if not user_id:
        log.warning('user.registered 事件缺少 user_id')
        return

    async with async_db_session.begin() as db:
        quests = await _list_active_triggered_quests(db, _TRIGGER_USER_REGISTERED)
        if not quests:
            return

        source_key = f'user_registered:{user_id}'
        for quest in quests:
            try:
                await _advance_claim(db=db, quest=quest, user_id=user_id, source_key=source_key)
            except Exception as exc:
                log.warning(f'推进任务进度异常 quest_id={quest.id} user_id={user_id} error={exc}')


@subscribe(_TRIGGER_USER_LOGGED_IN)
async def on_user_logged_in(
    *,
    user_id: int | None = None,
    **_: Any,
) -> None:
    """
    处理用户登录事件, 推进所有 trigger_type=user.logged_in 的任务进度

    :param user_id: 用户 ID
    :return:
    """
    if not user_id:
        log.warning('user.logged_in 事件缺少 user_id')
        return

    async with async_db_session.begin() as db:
        quests = await _list_active_triggered_quests(db, _TRIGGER_USER_LOGGED_IN)
        if not quests:
            return

        source_key = f'user_login:{user_id}:{timezone.now().strftime("%Y%m%d")}'
        for quest in quests:
            try:
                await _advance_claim(db=db, quest=quest, user_id=user_id, source_key=source_key)
            except Exception as exc:
                log.warning(f'推进任务进度异常 quest_id={quest.id} user_id={user_id} error={exc}')


@subscribe(_TRIGGER_SESSION_COMPLETED)
async def on_session_completed(
    *,
    user_id: int | None = None,
    session_id: int | None = None,
    **_: Any,
) -> None:
    """
    处理做题交卷事件, 推进所有 trigger_type=study.session_completed 的任务进度

    :param user_id: 用户 ID
    :param session_id: 会话 ID
    :return:
    """
    if not user_id:
        log.warning('study.session_completed 事件缺少 user_id')
        return

    async with async_db_session.begin() as db:
        quests = await _list_active_triggered_quests(db, _TRIGGER_SESSION_COMPLETED)
        if not quests:
            return

        source_key = f'session:{session_id}'
        for quest in quests:
            try:
                await _advance_claim(db=db, quest=quest, user_id=user_id, source_key=source_key)
            except Exception as exc:
                log.warning(f'推进任务进度异常 quest_id={quest.id} user_id={user_id} error={exc}')
