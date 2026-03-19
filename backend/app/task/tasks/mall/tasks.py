#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from backend.app.mall.service.team_service import team_service
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='mall:process_expired_teams')
def process_expired_teams() -> dict[str, int]:
    """
    处理过期的拼团团队

    定时任务：每 5 分钟执行一次
    功能：检查过期的拼团团队，根据配置决定是否模拟成团或标记为失败
    """
    logger.info('开始处理过期拼团团队')

    async def _process() -> int:
        async with async_db_session.begin() as db:
            count = await team_service.process_expired_teams(db=db)
            return count

    from backend.utils.async_helper import run_await
    count = run_await(_process())

    logger.info(f'处理完成，共处理 {count} 个过期团队')
    return {'processed_count': count}
