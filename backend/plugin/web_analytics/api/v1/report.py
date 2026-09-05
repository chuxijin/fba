from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, Response

from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.plugin.web_analytics.schema import (
    CounterDetail,
    DailyTrendDetail,
    DimensionDetail,
    HeatmapPointDetail,
    OverviewDetail,
    ReplayDetail,
)
from backend.plugin.web_analytics.service import analytics_service
from backend.utils.timezone import timezone

router = APIRouter()


@router.get('/public/{site_key}/counter', summary='获取公开访问计数')
async def public_counter(
    db: CurrentSession,
    response: Response,
    site_key: Annotated[str, Path(description='站点公开标识')],
    path: Annotated[str | None, Query(description='页面路径')] = None,
) -> ResponseSchemaModel[CounterDetail]:
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Cache-Control'] = 'public, max-age=30'
    data = await analytics_service.counter(db=db, site_key=site_key, path=path)
    return response_base.success(data=data)


@router.get('/sites/{site_id}/overview', summary='获取统计总览', dependencies=[DependsJwtAuth])
async def overview(
    db: CurrentSession,
    site_id: Annotated[int, Path(description='站点 ID')],
    start: Annotated[datetime | None, Query(description='开始时间')] = None,
    end: Annotated[datetime | None, Query(description='结束时间')] = None,
) -> ResponseSchemaModel[OverviewDetail]:
    end = end or timezone.now()
    start = start or end - timedelta(days=7)
    data = await analytics_service.overview(db=db, site_id=site_id, start=start, end=end)
    return response_base.success(data=data)


@router.get('/sites/{site_id}/trend', summary='获取每日趋势', dependencies=[DependsJwtAuth])
async def trend(
    db: CurrentSession,
    site_id: Annotated[int, Path(description='站点 ID')],
    start_date: Annotated[date | None, Query(description='开始日期')] = None,
    end_date: Annotated[date | None, Query(description='结束日期')] = None,
) -> ResponseSchemaModel[list[DailyTrendDetail]]:
    end_date = end_date or timezone.now().date()
    start_date = start_date or end_date - timedelta(days=29)
    data = await analytics_service.trend(db=db, site_id=site_id, start_date=start_date, end_date=end_date)
    return response_base.success(data=data)


@router.get('/sites/{site_id}/heatmap', summary='获取点击热力图', dependencies=[DependsJwtAuth])
async def heatmap(
    db: CurrentSession,
    site_id: Annotated[int, Path(description='站点 ID')],
    path: Annotated[str, Query(description='页面路径')],
    start: Annotated[datetime | None, Query(description='开始时间')] = None,
    end: Annotated[datetime | None, Query(description='结束时间')] = None,
) -> ResponseSchemaModel[list[HeatmapPointDetail]]:
    end = end or timezone.now()
    start = start or end - timedelta(days=7)
    data = await analytics_service.heatmap(db=db, site_id=site_id, path=path, start=start, end=end)
    return response_base.success(data=data)


@router.get('/sites/{site_id}/dimensions', summary='获取统计维度排行', dependencies=[DependsJwtAuth])
async def dimensions(
    db: CurrentSession,
    site_id: Annotated[int, Path(description='站点 ID')],
    dimension: Annotated[str, Query(description='维度名称')],
    start: Annotated[datetime | None, Query(description='开始时间')] = None,
    end: Annotated[datetime | None, Query(description='结束时间')] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> ResponseSchemaModel[list[DimensionDetail]]:
    end = end or timezone.now()
    start = start or end - timedelta(days=7)
    data = await analytics_service.dimensions(
        db=db,
        site_id=site_id,
        dimension=dimension,
        start=start,
        end=end,
        limit=limit,
    )
    return response_base.success(data=data)


@router.get('/sites/{site_id}/replays', summary='获取会话回放列表', dependencies=[DependsJwtAuth])
async def replays(
    db: CurrentSession,
    site_id: Annotated[int, Path(description='站点 ID')],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ResponseSchemaModel[list[ReplayDetail]]:
    data = await analytics_service.replays(db=db, site_id=site_id, limit=limit)
    return response_base.success(data=data)


@router.get(
    '/sites/{site_id}/replays/{replay_key}',
    summary='获取会话回放事件',
    dependencies=[DependsJwtAuth],
)
async def replay_chunks(
    db: CurrentSession,
    site_id: Annotated[int, Path(description='站点 ID')],
    replay_key: Annotated[str, Path(description='回放标识')],
) -> ResponseSchemaModel[list[dict[str, Any]]]:
    data = await analytics_service.replay_chunks(db=db, site_id=site_id, replay_key=replay_key)
    return response_base.success(data=data)
