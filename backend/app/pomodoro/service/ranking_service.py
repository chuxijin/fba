#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from datetime import datetime, timedelta

import sqlalchemy as sa

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Subquery

from backend.app.admin.model.user import User
from backend.app.pomodoro.enums import (
    PomodoroFocusMode,
    PomodoroFocusStatus,
    PomodoroRankingPeriod,
    PomodoroRankingScope,
)
from backend.app.pomodoro.model.focus import PomodoroFocusSession
from backend.app.pomodoro.schema.ranking import GetPomodoroRankingDetail, PomodoroRankingItem
from backend.common.log import log
from backend.database.redis import redis_client
from backend.utils.timezone import timezone


class PomodoroRankingService:
    """番茄排行榜服务类"""

    _cache_ttl_seconds = 180

    @staticmethod
    async def get_ranking(
        *,
        db: AsyncSession,
        user_id: int,
        period: PomodoroRankingPeriod,
        scope: PomodoroRankingScope = PomodoroRankingScope.global_,
        limit: int = 50,
    ) -> GetPomodoroRankingDetail:
        """
        获取番茄排行榜

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param period: 榜单周期
        :param scope: 榜单范围
        :param limit: 返回数量
        :return:
        """
        start_at, end_at = PomodoroRankingService._get_period_range(period=period)
        cache_key = PomodoroRankingService._build_cache_key(
            period=period,
            scope=scope,
            start_at=start_at,
            limit=limit,
        )
        cached_items, generated_at = await PomodoroRankingService._get_cached_items(cache_key=cache_key)

        if cached_items is None:
            cached_items = await PomodoroRankingService._get_top_items(
                db=db,
                start_at=start_at,
                end_at=end_at,
                limit=limit,
            )
            generated_at = timezone.now()
            await PomodoroRankingService._set_cached_items(
                cache_key=cache_key,
                period=period,
                scope=scope,
                generated_at=generated_at,
                items=cached_items,
            )

        my_rank = await PomodoroRankingService._get_user_rank(
            db=db,
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
        )

        return GetPomodoroRankingDetail(
            period=period,
            scope=scope,
            generated_at=generated_at,
            items=cached_items,
            my_rank=my_rank,
        )

    @staticmethod
    async def _get_top_items(
        *,
        db: AsyncSession,
        start_at: datetime,
        end_at: datetime,
        limit: int,
    ) -> list[PomodoroRankingItem]:
        """
        获取排行榜前 N 名

        :param db: 数据库会话
        :param start_at: 开始时间
        :param end_at: 结束时间
        :param limit: 返回数量
        :return:
        """
        ranked_subquery = PomodoroRankingService._build_ranked_subquery(start_at=start_at, end_at=end_at)
        stmt = (
            select(
                ranked_subquery.c.rank,
                ranked_subquery.c.user_id,
                ranked_subquery.c.focused_seconds,
                ranked_subquery.c.completed_pomodoro_count,
                User.nickname,
                User.avatar,
            )
            .outerjoin(User, User.id == ranked_subquery.c.user_id)
            .order_by(ranked_subquery.c.rank.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        items = []
        for row in result.all():
            items.append(
                PomodoroRankingItem(
                    rank=int(row.rank),
                    user_id=int(row.user_id),
                    nickname=row.nickname or f'用户{row.user_id}',
                    avatar=row.avatar,
                    focused_seconds=int(row.focused_seconds or 0),
                    completed_pomodoro_count=int(row.completed_pomodoro_count or 0),
                )
            )
        return items

    @staticmethod
    async def _get_user_rank(
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> PomodoroRankingItem | None:
        """
        获取用户自己的排名

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_at: 开始时间
        :param end_at: 结束时间
        :return:
        """
        ranked_subquery = PomodoroRankingService._build_ranked_subquery(start_at=start_at, end_at=end_at)
        stmt = (
            select(
                ranked_subquery.c.rank,
                ranked_subquery.c.user_id,
                ranked_subquery.c.focused_seconds,
                ranked_subquery.c.completed_pomodoro_count,
                User.nickname,
                User.avatar,
            )
            .outerjoin(User, User.id == ranked_subquery.c.user_id)
            .where(ranked_subquery.c.user_id == user_id)
        )
        result = await db.execute(stmt)
        row = result.first()
        if row is None:
            return None

        return PomodoroRankingItem(
            rank=int(row.rank),
            user_id=int(row.user_id),
            nickname=row.nickname or f'用户{row.user_id}',
            avatar=row.avatar,
            focused_seconds=int(row.focused_seconds or 0),
            completed_pomodoro_count=int(row.completed_pomodoro_count or 0),
        )

    @staticmethod
    def _build_ranked_subquery(*, start_at: datetime, end_at: datetime) -> Subquery:
        """
        构建带排名的统计子查询

        :param start_at: 开始时间
        :param end_at: 结束时间
        :return:
        """
        completed_pomodoro_count = func.coalesce(
            func.sum(
                sa.case(
                    (PomodoroFocusSession.mode == PomodoroFocusMode.pomodoro.value, 1),
                    else_=0,
                )
            ),
            0,
        )
        stats_subquery = (
            select(
                PomodoroFocusSession.user_id.label('user_id'),
                func.coalesce(func.sum(PomodoroFocusSession.focused_seconds), 0).label('focused_seconds'),
                completed_pomodoro_count.label('completed_pomodoro_count'),
            )
            .where(
                PomodoroFocusSession.status == PomodoroFocusStatus.completed.value,
                PomodoroFocusSession.ended_at >= start_at,
                PomodoroFocusSession.ended_at < end_at,
            )
            .group_by(PomodoroFocusSession.user_id)
        ).subquery()

        return (
            select(
                stats_subquery.c.user_id,
                stats_subquery.c.focused_seconds,
                stats_subquery.c.completed_pomodoro_count,
                func.row_number()
                .over(
                    order_by=(
                        stats_subquery.c.focused_seconds.desc(),
                        stats_subquery.c.completed_pomodoro_count.desc(),
                        stats_subquery.c.user_id.asc(),
                    )
                )
                .label('rank'),
            )
        ).subquery()

    @staticmethod
    def _get_period_range(*, period: PomodoroRankingPeriod) -> tuple[datetime, datetime]:
        """
        获取榜单周期范围

        :param period: 榜单周期
        :return:
        """
        now = timezone.now()
        start_at = now.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == PomodoroRankingPeriod.weekly:
            start_at = start_at - timedelta(days=start_at.weekday())
            return start_at, start_at + timedelta(days=7)

        return start_at, start_at + timedelta(days=1)

    @staticmethod
    async def _get_cached_items(*, cache_key: str) -> tuple[list[PomodoroRankingItem] | None, datetime]:
        """
        获取缓存排行榜

        :param cache_key: 缓存键
        :return:
        """
        generated_at = timezone.now()
        try:
            cached = await redis_client.get(cache_key)
        except Exception as exc:
            log.warning('读取番茄排行榜缓存失败: {}', exc)
            return None, generated_at

        if not cached:
            return None, generated_at

        try:
            payload = json.loads(cached)
            items = [PomodoroRankingItem(**item) for item in payload.get('items', [])]
            return items, datetime.fromisoformat(payload['generated_at'])
        except Exception as exc:
            log.warning('解析番茄排行榜缓存失败: {}', exc)
            return None, generated_at

    @staticmethod
    async def _set_cached_items(
        *,
        cache_key: str,
        period: PomodoroRankingPeriod,
        scope: PomodoroRankingScope,
        generated_at: datetime,
        items: list[PomodoroRankingItem],
    ) -> None:
        """
        写入排行榜缓存

        :param cache_key: 缓存键
        :param period: 榜单周期
        :param scope: 榜单范围
        :param generated_at: 生成时间
        :param items: 榜单项
        :return:
        """
        payload = {
            'period': period.value,
            'scope': scope.value,
            'generated_at': generated_at.isoformat(),
            'items': [item.model_dump(mode='json') for item in items],
        }
        try:
            await redis_client.set(
                cache_key,
                json.dumps(payload, ensure_ascii=False),
                ex=PomodoroRankingService._cache_ttl_seconds,
            )
        except Exception as exc:
            log.warning('写入番茄排行榜缓存失败: {}', exc)

    @staticmethod
    def _build_cache_key(
        *,
        period: PomodoroRankingPeriod,
        scope: PomodoroRankingScope,
        start_at: datetime,
        limit: int,
    ) -> str:
        """
        构建排行榜缓存键

        :param period: 榜单周期
        :param scope: 榜单范围
        :param start_at: 周期开始时间
        :param limit: 返回数量
        :return:
        """
        return f'pomodoro:ranking:{scope.value}:{period.value}:{start_at.date().isoformat()}:{limit}'


pomodoro_ranking_service: PomodoroRankingService = PomodoroRankingService()
