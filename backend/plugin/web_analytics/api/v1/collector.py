import json

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import ValidationError
from pyrate_limiter import Duration, Rate
from starlette.responses import FileResponse, Response

from backend.common.exception import errors
from backend.database.db import CurrentSessionTransaction
from backend.plugin.web_analytics.schema import CollectBatchParam, ReplayChunkParam
from backend.plugin.web_analytics.service import analytics_service
from backend.utils.limiter import RateLimiter

router = APIRouter()
TRACKER_FILE = Path(__file__).resolve().parents[2] / 'assets' / 'tracker.js'


async def _read_payload(request: Request) -> dict:
    body = await request.body()
    if len(body) > 1024 * 1024:
        raise errors.RequestError(msg='上报请求体超过大小限制')
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise errors.RequestError(msg='上报数据不是有效 JSON') from exc


@router.get('/script.js', summary='获取统计采集脚本', include_in_schema=False)
async def tracker_script() -> FileResponse:
    return FileResponse(
        TRACKER_FILE,
        media_type='application/javascript; charset=utf-8',
        headers={'Cache-Control': 'public, max-age=3600'},
    )


@router.post(
    '/collect',
    summary='批量采集统计事件',
    status_code=204,
    dependencies=[Depends(RateLimiter(Rate(120, Duration.MINUTE)))],
)
async def collect_events(request: Request, db: CurrentSessionTransaction) -> Response:
    try:
        batch = CollectBatchParam.model_validate(await _read_payload(request))
    except ValidationError as exc:
        raise errors.RequestError(msg='上报数据格式错误', data=exc.errors()) from exc
    await analytics_service.collect(db=db, request=request, batch=batch)
    return Response(status_code=204)


@router.post(
    '/replay',
    summary='采集会话回放分片',
    status_code=204,
    dependencies=[Depends(RateLimiter(Rate(30, Duration.MINUTE)))],
)
async def collect_replay(request: Request, db: CurrentSessionTransaction) -> Response:
    try:
        chunk = ReplayChunkParam.model_validate(await _read_payload(request))
    except ValidationError as exc:
        raise errors.RequestError(msg='回放数据格式错误', data=exc.errors()) from exc
    await analytics_service.collect_replay(db=db, request=request, chunk=chunk)
    return Response(status_code=204)
