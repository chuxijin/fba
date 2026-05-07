#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cms.crud.crud_slot import cms_slot_dao, cms_slot_log_dao
from backend.app.cms.schema.slot import SlotStatsResult
from backend.common.exception import errors
from backend.utils.timezone import timezone

ACTION_SHOW: int = 0
ACTION_CLICK: int = 1
ACTION_CLOSE: int = 2


class StatsService:
    """内容运营位统计服务类"""

    @staticmethod
    async def get_slot_stats(
        *,
        db: AsyncSession,
        slot_id: int,
        days: int = 7,
    ) -> SlotStatsResult:
        """
        获取运营位指定时间窗口内的曝光/点击/关闭/CTR 统计

        :param db: 数据库会话
        :param slot_id: 运营位 ID
        :param days: 统计天数
        :return:
        """
        slot = await cms_slot_dao.select_model(db, slot_id)
        if not slot:
            raise errors.NotFoundError(msg='运营位不存在')

        if days <= 0:
            days = 7

        since = timezone.now() - timedelta(days=days)
        counts = await cms_slot_log_dao.aggregate_actions(db, slot_id=slot_id, since=since)
        show_count = counts.get(ACTION_SHOW, 0)
        click_count = counts.get(ACTION_CLICK, 0)
        close_count = counts.get(ACTION_CLOSE, 0)
        ctr = (click_count / show_count) if show_count else 0.0

        return SlotStatsResult(
            show_count=show_count,
            click_count=click_count,
            close_count=close_count,
            ctr=ctr,
        )


stats_service: StatsService = StatsService()
