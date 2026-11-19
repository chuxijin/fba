"""真实 HTTP 查询绑定与路由分流；只替换身份和数据库，不启动外部服务。"""

from collections.abc import Iterator
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from backend.app.question_bank_v2.api.v1 import review
from backend.app.question_bank_v2.schema.wrong_trend import GetWrongTrend, WrongTrendPoint
from backend.database.db import get_db

type Endpoint = tuple[TestClient, AsyncMock, AsyncMock, object]


@pytest.fixture
def endpoint(monkeypatch: pytest.MonkeyPatch) -> Iterator[Endpoint]:
    app = FastAPI()
    app.include_router(review.router, prefix='/api/v1/qbank-v2/wrong-questions')
    db = object()

    async def identity(request: Request) -> None:  # ruff: ignore[unused-async] -- 保持与被覆盖的异步身份依赖一致
        request.scope['user'] = SimpleNamespace(id=77)

    app.dependency_overrides[review.router.dependencies[0].dependency] = identity
    app.dependency_overrides[get_db] = lambda: db
    today = WrongTrendPoint(date=date(2026, 11, 19), wrong=0, reviewed=0, mastered=None)
    service = AsyncMock(return_value=GetWrongTrend(
        start_date=today.date, end_date=today.date, timezone='Asia/Shanghai',
        mastery_known_from=None, today=today, points=[today],
    ))
    detail = AsyncMock()
    monkeypatch.setattr(review.wrong_trend_service, 'get_trend', service)
    monkeypatch.setattr(review.wrong_review_service, 'get_detail', detail)
    with TestClient(app) as client:
        yield client, service, detail, db


@pytest.mark.parametrize(('query', 'days'), [('', 7), ('?days=7', 7), ('?days=30', 30)])
def test_http_string_days_and_default_reach_trend_not_integer_detail(endpoint: Endpoint, query: str, days: int) -> None:
    client, service, detail, db = endpoint
    response = client.get(f'/api/v1/qbank-v2/wrong-questions/trend{query}')
    assert response.status_code == 200, response.text
    assert response.json()['data']['today']['mastered'] is None
    service.assert_awaited_once_with(
        db=db, user_id=77, start_date=None, end_date=None, domain_category_id=None, days=days,
    )
    assert type(service.await_args.kwargs['days']) is int
    detail.assert_not_awaited()


@pytest.mark.parametrize(
    'query', ['days=8', 'days=abc', 'days=', 'days=7.5', 'domain_category_id=0', 'start_date=2026-02-30']
)
def test_invalid_http_query_rejected_before_service(endpoint: Endpoint, query: str) -> None:
    client, service, detail, _ = endpoint
    response = client.get(f'/api/v1/qbank-v2/wrong-questions/trend?{query}')
    assert response.status_code == 422
    assert all(error['loc'][0] == 'query' for error in response.json()['detail'])
    service.assert_not_awaited()
    detail.assert_not_awaited()


def test_http_custom_dates_and_domain_bind_without_coercing_path_id(endpoint: Endpoint) -> None:
    client, service, detail, db = endpoint
    response = client.get('/api/v1/qbank-v2/wrong-questions/trend', params={
        'start_date': '2026-11-01', 'end_date': '2026-11-02', 'days': '30', 'domain_category_id': '1400',
    })
    assert response.status_code == 200, response.text
    service.assert_awaited_once_with(
        db=db, user_id=77, start_date=date(2026, 11, 1), end_date=date(2026, 11, 2),
        domain_category_id=1400, days=30,
    )
    detail.assert_not_awaited()
