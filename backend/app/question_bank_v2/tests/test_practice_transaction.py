"""练习事务边界回归：响应前提交与统计 JSON 分布持久化。

覆盖：
- backend.database.db.CurrentSessionTransactionBeforeResponse 使用 function scope；
- 最小 FastAPI ASGI 应用验证 commit 先于 response.start；
- commit 失败时不返回 200；
- 仅 V2 practice / evaluation 路由改用该别名；
- 真实模型 + 内存 SQLite 复现 A/A/B 三次提交后的 response_distribution。
"""

import asyncio

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace, TracebackType
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from fastapi import FastAPI
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.database.db as db_module

from backend.app.question_bank_v2.api.v1.bank import router as bank_router
from backend.app.question_bank_v2.api.v1.evaluation import router as evaluation_router
from backend.app.question_bank_v2.api.v1.practice import router as practice_router
from backend.app.question_bank_v2.crud.crud_statistics import question_statistics_dao
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.statistics import QbQuestionStatistics
from backend.app.question_bank_v2.service import attempt_projection_service as projection_module
from backend.app.question_bank_v2.service.attempt_projection_service import (
    AttemptProjectionService,
    attempt_projection_service,
)
from backend.common.model import Base


class _FakeBegin:
    """替代 async_db_session.begin()，记录提交并允许注入提交失败。"""

    def __init__(self, events: list[str], *, fail: bool) -> None:
        self.events = events
        self.fail = fail

    async def __aenter__(self) -> SimpleNamespace:
        self.events.append('begin')
        return SimpleNamespace()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        self.events.append('commit')
        if self.fail and exc_type is None:
            raise RuntimeError('commit failed')
        return False


class _ResponseStartRecorder:
    """在 ASGI send 层记录响应开始与提交的先后顺序。"""

    def __init__(self, app: Any, events: list[str]) -> None:
        self.app = app
        self.events = events

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        async def send_wrapper(message: dict[str, Any]) -> None:
            if message['type'] == 'http.response.start':
                self.events.append('response.start')
            await send(message)

        await self.app(scope, receive, send_wrapper)


def _build_probe_app(alias: Any, events: list[str]) -> FastAPI:
    app = FastAPI()

    @app.get('/probe')
    async def probe(session: alias) -> dict[str, bool]:
        events.append('route')
        return {'ok': True}

    return app


async def _request_probe(app: Any) -> httpx.Response:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        return await client.get('/probe')


def _iter_dependants(dependant: Any) -> Any:
    yield dependant
    for child in dependant.dependencies:
        yield from _iter_dependants(child)


def _transaction_scopes(router: Any) -> list[str | None]:
    scopes: list[str | None] = []
    for route in router.routes:
        dependant = getattr(route, 'dependant', None)
        if dependant is None:
            continue
        scopes.extend(
            child.scope for child in _iter_dependants(dependant) if child.call is db_module.get_db_transaction
        )
    return scopes


def test_before_response_alias_exists() -> None:
    """新别名必须暴露在 backend.database.db 上，并绑定 function scope。"""
    alias = getattr(db_module, 'CurrentSessionTransactionBeforeResponse', None)
    assert alias is not None

    metadata = alias.__metadata__
    assert len(metadata) == 1
    depend = metadata[0]
    assert depend.dependency is db_module.get_db_transaction
    assert depend.scope == 'function'


async def test_commit_runs_before_response_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """正常请求：路由 -> commit -> response.start。"""
    alias = db_module.CurrentSessionTransactionBeforeResponse
    events: list[str] = []
    monkeypatch.setattr(
        db_module.async_db_session,
        'begin',
        lambda source='default': _FakeBegin(events, fail=False),
    )
    app = _ResponseStartRecorder(_build_probe_app(alias, events), events)

    response = await _request_probe(app)

    assert response.status_code == 200
    assert events == ['begin', 'route', 'commit', 'response.start']


async def test_commit_failure_never_returns_success(monkeypatch: pytest.MonkeyPatch) -> None:
    """提交失败时不能把成功响应发给客户端。"""
    alias = db_module.CurrentSessionTransactionBeforeResponse
    events: list[str] = []
    monkeypatch.setattr(
        db_module.async_db_session,
        'begin',
        lambda source='default': _FakeBegin(events, fail=True),
    )
    app = _ResponseStartRecorder(_build_probe_app(alias, events), events)

    response = await _request_probe(app)

    assert response.status_code != 200
    assert 'commit' in events


def test_only_practice_and_evaluation_routes_use_before_response_transaction() -> None:
    """V2 practice / evaluation 的写事务全部改用 function scope，其他路由保持原样。"""
    for router in (practice_router, evaluation_router):
        scopes = _transaction_scopes(router)
        assert scopes, '路由应包含数据库事务依赖'
        assert all(scope == 'function' for scope in scopes)

    assert set(_transaction_scopes(bank_router)) == {None}


class _SyncSessionAsAsync:
    """把同步 Session 包装成 DAO 需要的最小异步接口。"""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self._session.execute(statement, *args, **kwargs)

    def add(self, instance: Any) -> None:
        self._session.add(instance)

    def add_all(self, instances: Any) -> None:
        self._session.add_all(instances)

    async def flush(self) -> None:
        self._session.flush()


QUESTION_ID = 100


def _make_attempt(answer: str, *, is_correct: bool, score: Decimal, duration_ms: int, minute: int) -> Any:
    return SimpleNamespace(
        question_id=QUESTION_ID,
        user_id=1,
        response_data={'answer': answer},
        is_correct=is_correct,
        score=score,
        duration_ms=duration_ms,
        submitted_time=datetime(2026, 11, 1, 9, 0, tzinfo=UTC) + timedelta(minutes=minute),
    )


def test_response_distribution_persists_across_commits() -> None:
    """真实模型 + 内存 SQLite 复现三次 A/A/B 提交，分布应为 {A:2, B:1}。"""
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[QbQuestionStatistics.__table__])
    maker = sessionmaker(bind=engine)

    seed = maker()
    statistics = QbQuestionStatistics(question_id=QUESTION_ID)
    statistics.id = 1
    seed.add(statistics)
    seed.commit()
    seed.close()

    attempts = [
        _make_attempt('A', is_correct=True, score=Decimal('1.00'), duration_ms=1000, minute=1),
        _make_attempt('A', is_correct=True, score=Decimal('1.00'), duration_ms=1200, minute=2),
        _make_attempt('B', is_correct=False, score=Decimal('0.00'), duration_ms=800, minute=3),
    ]
    for attempt in attempts:
        session = maker()
        try:
            asyncio.run(
                question_statistics_dao.apply_attempt(
                    _SyncSessionAsAsync(session),
                    attempt=attempt,
                    max_score=Decimal('1.00'),
                )
            )
            session.commit()
        finally:
            session.close()

    session = maker()
    try:
        row = (
            session
            .execute(select(QbQuestionStatistics).where(QbQuestionStatistics.question_id == QUESTION_ID))
            .scalars()
            .first()
        )
    finally:
        session.close()
        engine.dispose()

    assert row is not None
    assert row.attempt_count == 3
    assert dict(row.response_distribution or {}) == {'A': 2, 'B': 1}


PROJECTION_QUESTION_ID = 1
PROJECTION_ATTEMPT_ID = 500


def _projection_session_item() -> Any:
    return SimpleNamespace(
        id=21,
        question_id=PROJECTION_QUESTION_ID,
        bank_item_id=None,
        max_score=Decimal('1.00'),
        display_config={},
    )


def _load_projection_row(session: Any) -> Any:
    row = (
        session
        .execute(select(QbQuestionAttempt).where(QbQuestionAttempt.id == PROJECTION_ATTEMPT_ID))
        .scalars()
        .first()
    )
    assert row is not None
    return row


def _load_question_statistics(session: Any) -> Any:
    row = (
        session
        .execute(
            select(QbQuestionStatistics).where(QbQuestionStatistics.question_id == PROJECTION_QUESTION_ID),
        )
        .scalars()
        .first()
    )
    assert row is not None
    return row


def test_projection_rollback_then_retry_never_double_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """真实 Session 回滚后标记与统计都不生效；重试提交只累计一次，重复投影不再累计。"""
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[QbQuestionStatistics.__table__, QbQuestionAttempt.__table__],
    )
    maker = sessionmaker(bind=engine)

    seed = maker()
    statistics = QbQuestionStatistics(question_id=PROJECTION_QUESTION_ID)
    statistics.id = 1
    attempt = QbQuestionAttempt(
        user_id=1,
        question_id=PROJECTION_QUESTION_ID,
        response_data={'answer': 'A'},
        attempt_no=1,
        is_correct=True,
        score=Decimal('1.00'),
        duration_ms=1000,
        grading_result={
            '_submission': {'key': 'key:retry-1', 'fingerprint': 'f' * 64, 'save_version': 1},
        },
        submitted_time=datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
    )
    attempt.id = PROJECTION_ATTEMPT_ID
    seed.add_all([statistics, attempt])
    seed.commit()
    seed.close()

    item = _projection_session_item()
    monkeypatch.setattr(AttemptProjectionService, 'lock_questions', AsyncMock())
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_attempt', AsyncMock())

    async def apply_real_question_statistics(*, db: Any, attempt: Any, max_score: Decimal) -> None:
        await question_statistics_dao.apply_attempt(db, attempt=attempt, max_score=max_score)

    monkeypatch.setattr(
        projection_module.statistics_service,
        'apply_attempt',
        apply_real_question_statistics,
    )

    async def projection_then_fail(db: Any, row: Any) -> None:
        await attempt_projection_service.apply(db=db, attempt=row, session_item=item)
        raise RuntimeError('forced rollback')

    session = maker()
    try:
        row = _load_projection_row(session)
        with pytest.raises(RuntimeError, match='forced rollback'):
            asyncio.run(projection_then_fail(_SyncSessionAsAsync(session), row))
        session.rollback()
    finally:
        session.close()

    session = maker()
    try:
        row = _load_projection_row(session)
        assert '_projection' not in (row.grading_result or {})
        rolled_back = _load_question_statistics(session)
        assert (rolled_back.attempt_count, rolled_back.graded_count, rolled_back.correct_count) == (0, 0, 0)
        assert dict(rolled_back.response_distribution or {}) == {}
    finally:
        session.close()

    session = maker()
    try:
        row = _load_projection_row(session)
        asyncio.run(
            attempt_projection_service.apply(
                db=_SyncSessionAsAsync(session),
                attempt=row,
                session_item=item,
            )
        )
        session.commit()
    finally:
        session.close()

    session = maker()
    try:
        row = _load_projection_row(session)
        assert row.grading_result['_projection'] == {'submitted': True, 'graded': True}
        asyncio.run(
            attempt_projection_service.apply(
                db=_SyncSessionAsAsync(session),
                attempt=row,
                session_item=item,
            )
        )
        session.commit()
    finally:
        session.close()

    session = maker()
    try:
        row = _load_projection_row(session)
        committed = _load_question_statistics(session)
        assert row.grading_result['_projection'] == {'submitted': True, 'graded': True}
        assert committed.attempt_count == 1
        assert committed.graded_count == 1
        assert committed.correct_count == 1
        assert dict(committed.response_distribution or {}) == {'A': 1}
    finally:
        session.close()
        engine.dispose()
