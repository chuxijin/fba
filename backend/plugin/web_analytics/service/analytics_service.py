import json

from datetime import date, datetime, time, timedelta
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.context import ctx
from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.web_analytics.constants import EVENT_CLICK, EVENT_HEARTBEAT, EVENT_PAGEVIEW, EVENT_SCROLL
from backend.plugin.web_analytics.crud import analytics_dao
from backend.plugin.web_analytics.model import (
    AnalyticsDaily,
    AnalyticsEvent,
    AnalyticsReplayChunk,
    AnalyticsReplaySession,
    AnalyticsSession,
    AnalyticsSite,
)
from backend.plugin.web_analytics.schema import (
    CollectBatchParam,
    CollectResult,
    CounterDetail,
    CreateSiteParam,
    DailyTrendDetail,
    DimensionDetail,
    HeatmapPointDetail,
    OverviewDetail,
    ReplayChunkParam,
    ReplayDetail,
    SiteDetail,
    UpdateSiteParam,
)
from backend.plugin.web_analytics.service.security import (
    anonymize_ip,
    digest_identifier,
    domain_allowed,
    generate_site_key,
    sanitize_properties,
    sanitize_url,
    source_host,
)
from backend.utils.timezone import timezone


class AnalyticsService:
    @staticmethod
    async def create_site(*, db: AsyncSession, obj: CreateSiteParam) -> SiteDetail:
        try:
            ZoneInfo(obj.timezone)
        except ZoneInfoNotFoundError as exc:
            raise errors.RequestError(msg='无效的统计时区') from exc
        site = AnalyticsSite(site_key=generate_site_key(), **obj.model_dump())
        db.add(site)
        await db.flush()
        await db.refresh(site)
        return SiteDetail.model_validate(site)

    @staticmethod
    async def update_site(*, db: AsyncSession, site_id: int, obj: UpdateSiteParam) -> SiteDetail:
        site = await analytics_dao.get_site(db, site_id)
        if not site or site.deleted:
            raise errors.NotFoundError(msg='统计站点不存在')
        values = obj.model_dump(exclude_none=True)
        if 'timezone' in values:
            try:
                ZoneInfo(values['timezone'])
            except ZoneInfoNotFoundError as exc:
                raise errors.RequestError(msg='无效的统计时区') from exc
        for key, value in values.items():
            setattr(site, key, value)
        await db.flush()
        await db.refresh(site)
        return SiteDetail.model_validate(site)

    @staticmethod
    async def list_sites(*, db: AsyncSession) -> list[SiteDetail]:
        result = await db.execute(analytics_dao.get_sites_select())
        return [SiteDetail.model_validate(site) for site in result.scalars()]

    @staticmethod
    async def get_site(*, db: AsyncSession, site_id: int) -> SiteDetail:
        site = await analytics_dao.get_site(db, site_id)
        if not site or site.deleted:
            raise errors.NotFoundError(msg='统计站点不存在')
        return SiteDetail.model_validate(site)

    async def collect(
        self,
        *,
        db: AsyncSession,
        request: Request,
        batch: CollectBatchParam,
    ) -> CollectResult:
        max_batch_size = int(getattr(settings, 'WEB_ANALYTICS_MAX_BATCH_SIZE', 50))
        if len(batch.events) > max_batch_size:
            raise errors.RequestError(msg=f'单次最多上报 {max_batch_size} 个事件')
        site = await self._collector_site(db=db, request=request, site_key=batch.site)
        existing = await analytics_dao.get_existing_event_keys(db, site.id, [event.id for event in batch.events])
        now = timezone.now()
        visitor_hash = digest_identifier(site.site_key, batch.visitor)
        ip_hash = digest_identifier(site.site_key, anonymize_ip(ctx.ip))
        accepted_events = []
        seen_event_keys = set(existing)
        for event in batch.events:
            if event.id in seen_event_keys:
                continue
            seen_event_keys.add(event.id)
            if event.type in {EVENT_CLICK, EVENT_SCROLL} and not site.heatmap_enabled:
                continue
            occurred_at = self._safe_occurred_at(event.timestamp, now)
            accepted_events.append(
                AnalyticsEvent(
                    site_id=site.id,
                    event_key=event.id,
                    session_key=batch.session,
                    visitor_hash=visitor_hash,
                    event_type=event.type,
                    event_name=event.name,
                    path=(sanitize_url(event.path) or '/')[:1024],
                    title=event.title,
                    referrer=sanitize_url(event.referrer, default=''),
                    occurred_at=occurred_at,
                    received_at=now,
                    properties=sanitize_properties(event.properties),
                    screen_width=event.screen_width,
                    screen_height=event.screen_height,
                    viewport_width=event.viewport_width,
                    viewport_height=event.viewport_height,
                )
            )
        if not accepted_events:
            return CollectResult(accepted=0, duplicate=len(batch.events))
        db.add_all(accepted_events)
        await self._upsert_session(
            db=db,
            site=site,
            batch=batch,
            events=accepted_events,
            visitor_hash=visitor_hash,
            ip_hash=ip_hash,
        )
        await db.flush()
        return CollectResult(accepted=len(accepted_events), duplicate=len(batch.events) - len(accepted_events))

    async def collect_replay(
        self,
        *,
        db: AsyncSession,
        request: Request,
        chunk: ReplayChunkParam,
    ) -> bool:
        site = await self._collector_site(db=db, request=request, site_key=chunk.site)
        if not site.replay_enabled:
            raise errors.ForbiddenError(msg='站点未启用会话回放')
        payload = json.dumps(chunk.events, ensure_ascii=True, separators=(',', ':'))
        max_bytes = int(getattr(settings, 'WEB_ANALYTICS_MAX_REPLAY_BYTES', 524288))
        if len(payload.encode()) > max_bytes:
            raise errors.RequestError(msg='回放分片超过大小限制')
        if await analytics_dao.replay_chunk_exists(db, site.id, chunk.replay, chunk.sequence):
            return False
        now = timezone.now()
        occurred_at = self._safe_occurred_at(chunk.timestamp, now)
        visitor_hash = digest_identifier(site.site_key, chunk.visitor)
        replay = await analytics_dao.get_replay(db, site.id, chunk.replay)
        payload_bytes = len(payload.encode())
        if replay is None:
            replay = AnalyticsReplaySession(
                site_id=site.id,
                replay_key=chunk.replay,
                session_key=chunk.session,
                visitor_hash=visitor_hash,
                path=(sanitize_url(chunk.path) or '/')[:1024],
                started_at=occurred_at,
                last_event_at=occurred_at,
                chunk_count=1,
                total_bytes=payload_bytes,
            )
            db.add(replay)
        else:
            replay.last_event_at = max(replay.last_event_at, occurred_at)
            replay.chunk_count += 1
            replay.total_bytes += payload_bytes
        db.add(
            AnalyticsReplayChunk(
                site_id=site.id,
                replay_key=chunk.replay,
                sequence=chunk.sequence,
                encoding='json',
                payload=payload,
                event_count=len(chunk.events),
                occurred_at=occurred_at,
            )
        )
        await db.flush()
        return True

    @staticmethod
    async def overview(
        *,
        db: AsyncSession,
        site_id: int,
        start: datetime,
        end: datetime,
    ) -> OverviewDetail:
        await AnalyticsService._require_site(db, site_id)
        if end <= start or end - start > timedelta(days=366):
            raise errors.RequestError(msg='查询时间范围无效或超过 366 天')
        values = await analytics_dao.overview(db, site_id, start, end)
        sessions = values['sessions']
        duration = values['duration_seconds']
        return OverviewDetail(
            **values,
            bounce_rate=round(values['bounces'] / sessions * 100, 2) if sessions else 0,
            average_duration_seconds=round(duration / sessions, 2) if sessions else 0,
            active_visitors=await AnalyticsService._active_visitors(db, site_id),
        )

    @staticmethod
    async def trend(
        *,
        db: AsyncSession,
        site_id: int,
        start_date: date,
        end_date: date,
    ) -> list[DailyTrendDetail]:
        site = await AnalyticsService._require_site(db, site_id)
        if end_date < start_date or end_date - start_date > timedelta(days=366):
            raise errors.RequestError(msg='查询日期范围无效或超过 366 天')
        output = []
        current = start_date
        while current <= end_date:
            day_start = datetime.combine(current, time.min, tzinfo=ZoneInfo(site.timezone))
            values = await analytics_dao.overview(db, site_id, day_start, day_start + timedelta(days=1))
            output.append(
                DailyTrendDetail(
                    date=current,
                    pv=values['pv'],
                    uv=values['uv'],
                    sessions=values['sessions'],
                    events=values['events'],
                    bounces=values['bounces'],
                    duration_seconds=values['duration_seconds'],
                )
            )
            current += timedelta(days=1)
        return output

    @staticmethod
    async def counter(*, db: AsyncSession, site_key: str, path: str | None) -> CounterDetail:
        site = await analytics_dao.get_site_by_key(db, site_key)
        if not site or not site.is_active or not site.is_public:
            raise errors.NotFoundError(msg='公开统计不存在')
        sanitized_path = (sanitize_url(path) or '/')[:1024] if path else None
        site_pv, site_uv, page_pv = await analytics_dao.total_counter(db, site.id, sanitized_path)
        return CounterDetail(site_pv=site_pv, site_uv=site_uv, page_pv=page_pv)

    @staticmethod
    async def heatmap(
        *,
        db: AsyncSession,
        site_id: int,
        path: str,
        start: datetime,
        end: datetime,
    ) -> list[HeatmapPointDetail]:
        await AnalyticsService._require_site(db, site_id)
        points = await analytics_dao.heatmap_points(db, site_id, (sanitize_url(path) or '/')[:1024], start, end)
        return [HeatmapPointDetail(**point) for point in points]

    @staticmethod
    async def dimensions(
        *,
        db: AsyncSession,
        site_id: int,
        dimension: str,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> list[DimensionDetail]:
        await AnalyticsService._require_site(db, site_id)
        supported = {
            'browser',
            'city',
            'country',
            'device',
            'event',
            'os',
            'page',
            'referrer',
            'region',
            'utm_campaign',
            'utm_source',
        }
        if dimension not in supported:
            raise errors.RequestError(msg='不支持的统计维度')
        if end <= start or end - start > timedelta(days=366):
            raise errors.RequestError(msg='查询时间范围无效或超过 366 天')
        rows = await analytics_dao.dimension_ranking(db, site_id, dimension, start, end, limit)
        return [DimensionDetail(**row) for row in rows]

    @staticmethod
    async def replays(*, db: AsyncSession, site_id: int, limit: int) -> list[ReplayDetail]:
        await AnalyticsService._require_site(db, site_id)
        rows = await analytics_dao.list_replays(db, site_id, limit)
        return [ReplayDetail.model_validate(row, from_attributes=True) for row in rows]

    @staticmethod
    async def replay_chunks(*, db: AsyncSession, site_id: int, replay_key: str) -> list[dict]:
        await AnalyticsService._require_site(db, site_id)
        rows = await analytics_dao.get_replay_chunks(db, site_id, replay_key)
        if not rows:
            raise errors.NotFoundError(msg='会话回放不存在')
        return [
            {
                'sequence': row.sequence,
                'encoding': row.encoding,
                'events': json.loads(row.payload),
                'occurred_at': row.occurred_at,
            }
            for row in rows
        ]

    @staticmethod
    async def aggregate_day(*, db: AsyncSession, site_id: int, target_date: date) -> AnalyticsDaily:
        site = await AnalyticsService._require_site(db, site_id)
        zone = ZoneInfo(site.timezone)
        local_start = datetime.combine(target_date, time.min, tzinfo=zone)
        local_end = local_start + timedelta(days=1)
        values = await analytics_dao.overview(db, site_id, local_start, local_end)
        result = await db.execute(
            select(AnalyticsDaily).where(
                AnalyticsDaily.site_id == site_id,
                AnalyticsDaily.stats_date == target_date,
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = AnalyticsDaily(site_id=site_id, stats_date=target_date)
            db.add(row)
        row.pv = values['pv']
        row.uv = values['uv']
        row.sessions = values['sessions']
        row.events = values['events']
        row.bounces = values['bounces']
        row.duration_seconds = values['duration_seconds']
        await db.flush()
        return row

    @staticmethod
    async def cleanup(*, db: AsyncSession, now: datetime | None = None) -> dict[str, int]:
        now = now or timezone.now()
        sites_result = await db.execute(analytics_dao.get_sites_select())
        deleted_events = 0
        deleted_replays = 0
        for site in sites_result.scalars():
            event_result = await db.execute(
                delete(AnalyticsEvent).where(
                    AnalyticsEvent.site_id == site.id,
                    AnalyticsEvent.occurred_at < now - timedelta(days=site.event_retention_days),
                )
            )
            replay_keys = select(AnalyticsReplaySession.replay_key).where(
                AnalyticsReplaySession.site_id == site.id,
                AnalyticsReplaySession.started_at < now - timedelta(days=site.replay_retention_days),
            )
            chunk_result = await db.execute(
                delete(AnalyticsReplayChunk).where(
                    AnalyticsReplayChunk.site_id == site.id,
                    AnalyticsReplayChunk.replay_key.in_(replay_keys),
                )
            )
            replay_result = await db.execute(
                delete(AnalyticsReplaySession).where(
                    AnalyticsReplaySession.site_id == site.id,
                    AnalyticsReplaySession.started_at < now - timedelta(days=site.replay_retention_days),
                )
            )
            deleted_events += event_result.rowcount or 0
            deleted_replays += (chunk_result.rowcount or 0) + (replay_result.rowcount or 0)
        return {'events': deleted_events, 'replays': deleted_replays}

    @staticmethod
    async def run_maintenance(*, db: AsyncSession, now: datetime | None = None) -> dict[str, int]:
        now = now or timezone.now()
        sites_result = await db.execute(analytics_dao.get_sites_select())
        aggregated = 0
        for site in sites_result.scalars():
            target_date = now.astimezone(ZoneInfo(site.timezone)).date() - timedelta(days=1)
            await AnalyticsService.aggregate_day(db=db, site_id=site.id, target_date=target_date)
            aggregated += 1
        cleanup_result = await AnalyticsService.cleanup(db=db, now=now)
        return {'aggregated': aggregated, **cleanup_result}

    async def _collector_site(self, *, db: AsyncSession, request: Request, site_key: str) -> AnalyticsSite:
        site = await analytics_dao.get_site_by_key(db, site_key)
        if not site or not site.is_active:
            raise errors.NotFoundError(msg='统计站点不存在或已停用')
        host = source_host(request.headers.get('origin'), request.headers.get('referer'))
        if not domain_allowed(host, site.domains):
            raise errors.ForbiddenError(msg='上报来源域名不在站点白名单中')
        return site

    @staticmethod
    async def _require_site(db: AsyncSession, site_id: int) -> AnalyticsSite:
        site = await analytics_dao.get_site(db, site_id)
        if not site or site.deleted:
            raise errors.NotFoundError(msg='统计站点不存在')
        return site

    @staticmethod
    async def _active_visitors(db: AsyncSession, site_id: int) -> int:
        result = await db.execute(
            select(func.count(func.distinct(AnalyticsSession.visitor_hash))).where(
                AnalyticsSession.site_id == site_id,
                AnalyticsSession.last_seen_at >= timezone.now() - timedelta(minutes=5),
            )
        )
        return result.scalar() or 0

    @staticmethod
    def _safe_occurred_at(value: datetime | None, now: datetime) -> datetime:
        if value is None:
            return now
        if value.tzinfo is None:
            value = value.replace(tzinfo=now.tzinfo)
        if abs(now - value) > timedelta(days=1):
            return now
        return value

    @staticmethod
    async def _upsert_session(
        *,
        db: AsyncSession,
        site: AnalyticsSite,
        batch: CollectBatchParam,
        events: list[AnalyticsEvent],
        visitor_hash: str,
        ip_hash: str,
    ) -> None:
        session = await analytics_dao.get_session(db, site.id, batch.session)
        pageviews = sum(event.event_type == EVENT_PAGEVIEW for event in events)
        event_count = len(events)
        first = min(events, key=lambda item: item.occurred_at)
        last = max(events, key=lambda item: item.occurred_at)
        heartbeat_seconds = sum(
            min(60, max(0, int((event.properties or {}).get('seconds', 0))))
            for event in events
            if event.event_type == EVENT_HEARTBEAT
        )
        if session is not None:
            session.last_seen_at = max(session.last_seen_at, last.occurred_at)
            session.exit_path = last.path
            session.pageviews += pageviews
            session.event_count += event_count
            session.duration_seconds += heartbeat_seconds
            return
        query = parse_qs(urlsplit(first.path).query)
        referrer_host = urlsplit(first.referrer).hostname if first.referrer else None
        session = AnalyticsSession(
            site_id=site.id,
            session_key=batch.session,
            visitor_hash=visitor_hash,
            ip_hash=ip_hash,
            started_at=first.occurred_at,
            last_seen_at=last.occurred_at,
            entry_path=first.path,
            exit_path=last.path,
            referrer=first.referrer,
            referrer_host=referrer_host,
            utm_source=(query.get('utm_source') or [None])[0],
            utm_medium=(query.get('utm_medium') or [None])[0],
            utm_campaign=(query.get('utm_campaign') or [None])[0],
            country=ctx.country,
            region=ctx.region,
            city=ctx.city,
            browser=ctx.browser,
            os=ctx.os,
            device=ctx.device,
            pageviews=pageviews,
            event_count=event_count,
            duration_seconds=heartbeat_seconds,
        )
        db.add(session)


analytics_service = AnalyticsService()
