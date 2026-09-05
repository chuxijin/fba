from collections.abc import Sequence
from datetime import date, datetime
from operator import itemgetter
from typing import Any

from sqlalchemy import Select, and_, case, distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.web_analytics.model import (
    AnalyticsDaily,
    AnalyticsEvent,
    AnalyticsReplayChunk,
    AnalyticsReplaySession,
    AnalyticsSession,
    AnalyticsSite,
)


class AnalyticsDAO:
    async def get_site(self, db: AsyncSession, site_id: int) -> AnalyticsSite | None:
        return await db.get(AnalyticsSite, site_id)

    async def get_site_by_key(self, db: AsyncSession, site_key: str) -> AnalyticsSite | None:
        result = await db.execute(
            select(AnalyticsSite).where(AnalyticsSite.site_key == site_key, AnalyticsSite.deleted == 0)
        )
        return result.scalar_one_or_none()

    def get_sites_select(self) -> Select[tuple[AnalyticsSite]]:
        return select(AnalyticsSite).where(AnalyticsSite.deleted == 0).order_by(AnalyticsSite.created_time.desc())

    async def get_existing_event_keys(
        self,
        db: AsyncSession,
        site_id: int,
        event_keys: list[str],
    ) -> set[str]:
        result = await db.execute(
            select(AnalyticsEvent.event_key).where(
                AnalyticsEvent.site_id == site_id,
                AnalyticsEvent.event_key.in_(event_keys),
            )
        )
        return set(result.scalars().all())

    async def get_session(
        self,
        db: AsyncSession,
        site_id: int,
        session_key: str,
    ) -> AnalyticsSession | None:
        result = await db.execute(
            select(AnalyticsSession).where(
                AnalyticsSession.site_id == site_id,
                AnalyticsSession.session_key == session_key,
            )
        )
        return result.scalar_one_or_none()

    async def get_replay(
        self,
        db: AsyncSession,
        site_id: int,
        replay_key: str,
    ) -> AnalyticsReplaySession | None:
        result = await db.execute(
            select(AnalyticsReplaySession).where(
                AnalyticsReplaySession.site_id == site_id,
                AnalyticsReplaySession.replay_key == replay_key,
            )
        )
        return result.scalar_one_or_none()

    async def replay_chunk_exists(
        self,
        db: AsyncSession,
        site_id: int,
        replay_key: str,
        sequence: int,
    ) -> bool:
        result = await db.execute(
            select(AnalyticsReplayChunk.id).where(
                AnalyticsReplayChunk.site_id == site_id,
                AnalyticsReplayChunk.replay_key == replay_key,
                AnalyticsReplayChunk.sequence == sequence,
            )
        )
        return result.scalar_one_or_none() is not None

    async def overview(
        self,
        db: AsyncSession,
        site_id: int,
        start: datetime,
        end: datetime,
    ) -> dict[str, int]:
        event_filter = and_(
            AnalyticsEvent.site_id == site_id,
            AnalyticsEvent.occurred_at >= start,
            AnalyticsEvent.occurred_at < end,
        )
        event_result = await db.execute(
            select(
                func.count(AnalyticsEvent.id),
                func.count(distinct(AnalyticsEvent.visitor_hash)),
                func.count(distinct(AnalyticsEvent.session_key)),
            ).where(event_filter)
        )
        events, uv, sessions = event_result.one()
        pv_result = await db.execute(
            select(func.count(AnalyticsEvent.id)).where(event_filter, AnalyticsEvent.event_type == 'pageview')
        )
        ip_result = await db.execute(
            select(func.count(distinct(AnalyticsSession.ip_hash))).where(
                AnalyticsSession.site_id == site_id,
                AnalyticsSession.started_at < end,
                AnalyticsSession.last_seen_at >= start,
            )
        )
        session_result = await db.execute(
            select(
                func.sum(AnalyticsSession.duration_seconds),
                func.sum(case((AnalyticsSession.pageviews <= 1, 1), else_=0)),
            ).where(
                AnalyticsSession.site_id == site_id,
                AnalyticsSession.started_at < end,
                AnalyticsSession.last_seen_at >= start,
            )
        )
        duration, bounces = session_result.one()
        return {
            'pv': pv_result.scalar() or 0,
            'uv': uv or 0,
            'ip': ip_result.scalar() or 0,
            'sessions': sessions or 0,
            'events': events or 0,
            'bounces': bounces or 0,
            'duration_seconds': duration or 0,
        }

    async def daily_trend(
        self,
        db: AsyncSession,
        site_id: int,
        start_date: date,
        end_date: date,
    ) -> Sequence[AnalyticsDaily]:
        result = await db.execute(
            select(AnalyticsDaily)
            .where(
                AnalyticsDaily.site_id == site_id,
                AnalyticsDaily.stats_date >= start_date,
                AnalyticsDaily.stats_date <= end_date,
            )
            .order_by(AnalyticsDaily.stats_date)
        )
        return result.scalars().all()

    async def total_counter(self, db: AsyncSession, site_id: int, path: str | None) -> tuple[int, int, int | None]:
        base_filter = (AnalyticsEvent.site_id == site_id, AnalyticsEvent.event_type == 'pageview')
        result = await db.execute(
            select(
                func.count(AnalyticsEvent.id),
                func.count(distinct(AnalyticsEvent.visitor_hash)),
            ).where(*base_filter)
        )
        site_pv, site_uv = result.one()
        page_pv = None
        if path is not None:
            page_result = await db.execute(
                select(func.count(AnalyticsEvent.id)).where(*base_filter, AnalyticsEvent.path == path)
            )
            page_pv = page_result.scalar() or 0
        return site_pv or 0, site_uv or 0, page_pv

    async def heatmap_points(
        self,
        db: AsyncSession,
        site_id: int,
        path: str,
        start: datetime,
        end: datetime,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(AnalyticsEvent.properties).where(
                AnalyticsEvent.site_id == site_id,
                AnalyticsEvent.event_type == 'click',
                AnalyticsEvent.path == path,
                AnalyticsEvent.occurred_at >= start,
                AnalyticsEvent.occurred_at < end,
            )
        )
        buckets: dict[tuple[int, int], int] = {}
        for properties in result.scalars():
            if not properties:
                continue
            try:
                x = min(1.0, max(0.0, float(properties['x_ratio'])))
                y = min(1.0, max(0.0, float(properties['y_ratio'])))
            except (KeyError, TypeError, ValueError):
                continue
            bucket = (round(x * 100), round(y * 100))
            buckets[bucket] = buckets.get(bucket, 0) + 1
        return [
            {'x_ratio': x / 100, 'y_ratio': y / 100, 'count': count}
            for (x, y), count in sorted(buckets.items(), key=itemgetter(1), reverse=True)
        ]

    async def dimension_ranking(
        self,
        db: AsyncSession,
        site_id: int,
        dimension: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[dict[str, Any]]:
        event_dimensions = {
            'event': AnalyticsEvent.event_name,
            'page': AnalyticsEvent.path,
        }
        session_dimensions = {
            'browser': AnalyticsSession.browser,
            'city': AnalyticsSession.city,
            'country': AnalyticsSession.country,
            'device': AnalyticsSession.device,
            'os': AnalyticsSession.os,
            'referrer': AnalyticsSession.referrer_host,
            'region': AnalyticsSession.region,
            'utm_campaign': AnalyticsSession.utm_campaign,
            'utm_source': AnalyticsSession.utm_source,
        }
        if dimension in event_dimensions:
            column = event_dimensions[dimension]
            filters = [
                AnalyticsEvent.site_id == site_id,
                AnalyticsEvent.occurred_at >= start,
                AnalyticsEvent.occurred_at < end,
                column.is_not(None),
            ]
            if dimension == 'page':
                filters.append(AnalyticsEvent.event_type == 'pageview')
            else:
                filters.append(AnalyticsEvent.event_type == 'custom')
            stmt = (
                select(column.label('name'), func.count(AnalyticsEvent.id).label('value'))
                .where(*filters)
                .group_by(column)
                .order_by(func.count(AnalyticsEvent.id).desc())
                .limit(limit)
            )
        elif dimension in session_dimensions:
            column = session_dimensions[dimension]
            stmt = (
                select(column.label('name'), func.count(AnalyticsSession.id).label('value'))
                .where(
                    AnalyticsSession.site_id == site_id,
                    AnalyticsSession.started_at < end,
                    AnalyticsSession.last_seen_at >= start,
                    column.is_not(None),
                )
                .group_by(column)
                .order_by(func.count(AnalyticsSession.id).desc())
                .limit(limit)
            )
        else:
            raise ValueError(f'Unsupported dimension: {dimension}')
        result = await db.execute(stmt)
        return [{'name': str(name), 'value': value} for name, value in result.all() if name]

    async def list_replays(
        self,
        db: AsyncSession,
        site_id: int,
        limit: int,
    ) -> Sequence[AnalyticsReplaySession]:
        result = await db.execute(
            select(AnalyticsReplaySession)
            .where(AnalyticsReplaySession.site_id == site_id)
            .order_by(AnalyticsReplaySession.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    async def get_replay_chunks(
        self,
        db: AsyncSession,
        site_id: int,
        replay_key: str,
    ) -> Sequence[AnalyticsReplayChunk]:
        result = await db.execute(
            select(AnalyticsReplayChunk)
            .where(
                AnalyticsReplayChunk.site_id == site_id,
                AnalyticsReplayChunk.replay_key == replay_key,
            )
            .order_by(AnalyticsReplayChunk.sequence)
        )
        return result.scalars().all()


analytics_dao = AnalyticsDAO()
