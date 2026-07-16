#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""悬赏任务相关定时任务"""

import logging

from sqlalchemy import select

from backend.app.quest.crud.crud_quest import quest_dao
from backend.app.quest.model import QuestClaim
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


@celery_app.task(name='quest:release_expired_quest_claims')
async def release_expired_quest_claims() -> dict:
    """释放领取超时的悬赏任务记录, 回退名额"""
    try:
        result = await _release_expired_quest_claims()
        logger.info(f'悬赏超时释放完成: 共释放 {result["released"]} 条记录')
        return result
    except Exception as exc:
        logger.error(f'悬赏超时释放失败: {exc!s}')
        return {'released': 0, 'error': str(exc)}


async def _release_expired_quest_claims() -> dict:
    """异步实现"""
    async with async_db_session.begin() as db:
        now = timezone.now()
        stmt = select(QuestClaim).where(
            QuestClaim.claim_status == 0,
            QuestClaim.expire_time.isnot(None),
            QuestClaim.expire_time < now,
        )
        result = await db.execute(stmt)
        expired_claims = result.scalars().all()

        released = 0
        for claim in expired_claims:
            quest = await quest_dao.lock_for_claim(db, claim.quest_id)
            if not quest:
                continue

            claim.claim_status = 5
            if quest.claimed_count > 0:
                quest.claimed_count -= 1
            released += 1

        return {'released': released}
