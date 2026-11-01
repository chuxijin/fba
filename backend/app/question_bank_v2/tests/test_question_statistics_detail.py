"""选择题统计详情回归：用时口径、只读约束与新 API 字段。

覆盖：
- 真实 ``get_question_timing`` 在内存 SQLite 上验证上下界、外部导入、考试结算、
  软隐藏会话、删除事实、背题模式、复习/自适应纳入与考试最终答案失效不回退等口径；
- 服务层只复用解析校验并返回已有统计 + 过滤后平均，不判题、不写库、不结算；
- 解析阶段的 Forbidden/NotFound 原样传播且不进入用时查询；
- 新 GET 路由与响应字段的最小 ASGI/schema 契约。
"""

import asyncio

from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.question_bank_v2.service.practice_service as practice_service_module

from backend.app.question_bank_v2.api.router import v1 as question_bank_v2_router
from backend.app.question_bank_v2.crud.crud_question_timing import get_question_timing
from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbQuestionAttempt
from backend.app.question_bank_v2.schema.practice import (
    GetPracticeSolutionDetail,
    PracticeQuestionStatisticsDetail,
)
from backend.app.question_bank_v2.service.practice_service import PracticeService, practice_service
from backend.common.exception import errors
from backend.common.model import Base

QUESTION_ID = 100
OTHER_QUESTION_ID = 200
UNKNOWN_QUESTION_ID = 999
REVIEW_QUESTION_ID = 300
DELETED_FINAL_QUESTION_ID = 400
OUT_OF_BOUND_FINAL_QUESTION_ID = 500

# 1000 + 300000 + 2000 + 6000 + 7000 + 8000 + 9000
EXPECTED_DURATION_SUM = 333_000
EXPECTED_SAMPLE_COUNT = 7
EXPECTED_AVG = Decimal('47571.43')

# 12000 + 2000 + 18000
REVIEW_DURATIONS = (12_000, 2_000, 18_000)


class _SyncSessionAsAsync:
    """把同步 Session 包装成只读 SQL 函数需要的最小异步接口。"""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self._session.execute(statement, *args, **kwargs)


class _ReadOnlyDB:
    """服务层用例的记录型只读库：一旦触碰写接口立即失败。"""

    def __init__(self) -> None:
        self.touched: list[str] = []

    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        self.touched.append('execute')
        raise AssertionError('统计详情不应执行额外数据库操作')

    def add(self, *args: Any, **kwargs: Any) -> None:
        self.touched.append('add')
        raise AssertionError('统计详情不应写库')

    async def flush(self) -> None:
        self.touched.append('flush')
        raise AssertionError('统计详情不应写库')


def _session(
    seed: Any,
    *,
    pk: int,
    key: str,
    mode: str = 'practice',
    status: str = 'in_progress',
    snapshot: dict[str, Any] | None = None,
    deleted: int = 0,
) -> None:
    session = QbPracticeSession(
        session_key=key,
        user_id=1,
        mode=mode,
        source_type='bank',
        status=status,
        source_snapshot={} if snapshot is None else snapshot,
    )
    session.id = pk
    session.deleted = deleted
    seed.add(session)


def _attempt(
    seed: Any,
    *,
    pk: int,
    question_id: int,
    duration: int | None,
    session_id: int | None,
    session_item_id: int | None,
    attempt_no: int = 1,
    grading_result: dict[str, Any] | None = None,
    deleted: int = 0,
) -> None:
    attempt = QbQuestionAttempt(
        user_id=1,
        question_id=question_id,
        response_data={'answer': 'A'},
        session_id=session_id,
        session_item_id=session_item_id,
        attempt_no=attempt_no,
        duration_ms=duration,
        grading_result={} if grading_result is None else grading_result,
    )
    attempt.id = pk
    attempt.deleted = deleted
    seed.add(attempt)


def _build_timing_db() -> tuple[Any, Any]:
    """只建会话与作答两张表，直接写入带 ID 的行，不依赖外键约束。"""
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[QbPracticeSession.__table__, QbQuestionAttempt.__table__],
    )
    maker = sessionmaker(bind=engine)
    seed = maker()

    _session(seed, pk=1, key='sess-practice-01')
    _session(seed, pk=2, key='sess-external-02', snapshot={'origin': 'external_practice'})
    _session(seed, pk=3, key='sess-memorize-03', mode='memorize')
    _session(seed, pk=4, key='sess-exam-open-04', mode='exam', status='in_progress')
    _session(seed, pk=5, key='sess-exam-done-05', mode='exam', status='submitted')
    _session(seed, pk=6, key='sess-mock-done-06', mode='mock', status='graded')
    _session(seed, pk=7, key='sess-exam-hidden-07', mode='exam', status='expired', deleted=1)

    # 有效样本：含上下界边界与同一投递题的重复作答（练习模式逐次计入）
    _attempt(seed, pk=1, question_id=QUESTION_ID, duration=1_000, session_id=1, session_item_id=1)
    _attempt(seed, pk=2, question_id=QUESTION_ID, duration=300_000, session_id=1, session_item_id=2)
    _attempt(
        seed,
        pk=3,
        question_id=QUESTION_ID,
        duration=2_000,
        session_id=1,
        session_item_id=2,
        attempt_no=2,
    )

    # 无效样本：越界、空值与超长
    _attempt(seed, pk=4, question_id=QUESTION_ID, duration=999, session_id=1, session_item_id=3)
    _attempt(seed, pk=5, question_id=QUESTION_ID, duration=300_001, session_id=1, session_item_id=4)
    _attempt(seed, pk=6, question_id=QUESTION_ID, duration=None, session_id=1, session_item_id=5)
    _attempt(seed, pk=18, question_id=QUESTION_ID, duration=0, session_id=1, session_item_id=15)
    _attempt(seed, pk=19, question_id=QUESTION_ID, duration=86_400_000, session_id=1, session_item_id=16)

    # 无效样本：逻辑删除的作答、外部导入的作答与会话、背题模式
    _attempt(
        seed,
        pk=7,
        question_id=QUESTION_ID,
        duration=5_000,
        session_id=1,
        session_item_id=6,
        deleted=1,
    )
    _attempt(
        seed,
        pk=8,
        question_id=QUESTION_ID,
        duration=4_000,
        session_id=1,
        session_item_id=7,
        grading_result={'origin': 'external_practice'},
    )
    _attempt(seed, pk=9, question_id=QUESTION_ID, duration=4_000, session_id=2, session_item_id=8)
    _attempt(seed, pk=10, question_id=QUESTION_ID, duration=3_000, session_id=3, session_item_id=9)

    # 无效样本：考试未交卷、考试中间答案；有效：最终答案、模考、隐藏已结算、独立作答
    _attempt(seed, pk=11, question_id=QUESTION_ID, duration=3_500, session_id=4, session_item_id=10)
    _attempt(
        seed,
        pk=12,
        question_id=QUESTION_ID,
        duration=4_000,
        session_id=5,
        session_item_id=11,
        attempt_no=1,
    )
    _attempt(
        seed,
        pk=13,
        question_id=QUESTION_ID,
        duration=6_000,
        session_id=5,
        session_item_id=11,
        attempt_no=2,
    )
    _attempt(seed, pk=14, question_id=QUESTION_ID, duration=7_000, session_id=6, session_item_id=12)
    _attempt(seed, pk=15, question_id=QUESTION_ID, duration=8_000, session_id=7, session_item_id=13)
    _attempt(
        seed,
        pk=16,
        question_id=QUESTION_ID,
        duration=9_000,
        session_id=None,
        session_item_id=None,
    )

    # 不同题隔离
    _attempt(seed, pk=17, question_id=OTHER_QUESTION_ID, duration=11_000, session_id=1, session_item_id=14)

    seed.commit()
    seed.close()
    return engine, maker


def _build_mode_scope_db() -> tuple[Any, Any]:
    """复习/自适应纳入与考试最终答案失效不回退，共用一套最小事实表。"""
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[QbPracticeSession.__table__, QbQuestionAttempt.__table__],
    )
    maker = sessionmaker(bind=engine)
    seed = maker()

    _session(seed, pk=1, key='sess-review-scope-01', mode='review')
    _session(seed, pk=2, key='sess-adaptive-scope-02', mode='adaptive')
    _session(seed, pk=3, key='sess-exam-deleted-final-03', mode='exam', status='graded')
    _session(seed, pk=4, key='sess-exam-timeout-final-04', mode='exam', status='submitted')

    # 复习与自适应：与普通练习同口径，有效作答逐条纳入
    _attempt(seed, pk=1, question_id=REVIEW_QUESTION_ID, duration=12_000, session_id=1, session_item_id=1)
    _attempt(
        seed,
        pk=2,
        question_id=REVIEW_QUESTION_ID,
        duration=2_000,
        session_id=1,
        session_item_id=1,
        attempt_no=2,
    )
    _attempt(seed, pk=3, question_id=REVIEW_QUESTION_ID, duration=18_000, session_id=2, session_item_id=2)

    # 考试最终答案被逻辑删除：删除事实不计入，旧答案也不回退
    _attempt(seed, pk=4, question_id=DELETED_FINAL_QUESTION_ID, duration=5_000, session_id=3, session_item_id=3)
    _attempt(
        seed,
        pk=5,
        question_id=DELETED_FINAL_QUESTION_ID,
        duration=4_000,
        session_id=3,
        session_item_id=3,
        attempt_no=2,
        deleted=1,
    )

    # 考试最终答案越界：过滤后的最终答案同样不回退到此前有效用时
    _attempt(
        seed,
        pk=6,
        question_id=OUT_OF_BOUND_FINAL_QUESTION_ID,
        duration=6_000,
        session_id=4,
        session_item_id=4,
    )
    _attempt(
        seed,
        pk=7,
        question_id=OUT_OF_BOUND_FINAL_QUESTION_ID,
        duration=999,
        session_id=4,
        session_item_id=4,
        attempt_no=2,
    )
    _attempt(
        seed,
        pk=8,
        question_id=OUT_OF_BOUND_FINAL_QUESTION_ID,
        duration=7_000,
        session_id=4,
        session_item_id=5,
    )
    _attempt(
        seed,
        pk=9,
        question_id=OUT_OF_BOUND_FINAL_QUESTION_ID,
        duration=300_001,
        session_id=4,
        session_item_id=5,
        attempt_no=2,
    )

    seed.commit()
    seed.close()
    return engine, maker


def _query_timing(maker: Any, question_id: int) -> tuple[Decimal | None, int]:
    session = maker()
    try:
        return asyncio.run(
            get_question_timing(
                _SyncSessionAsAsync(session),
                question_id=question_id,
            )
        )
    finally:
        session.close()


def test_question_timing_counts_only_eligible_online_samples() -> None:
    """真实 SQL 聚合：边界含入，越界/外部/未结算/删除/背题全部排除。"""
    engine, maker = _build_timing_db()
    try:
        average, count = _query_timing(maker, QUESTION_ID)
    finally:
        engine.dispose()

    assert count == EXPECTED_SAMPLE_COUNT
    assert average == EXPECTED_AVG
    assert average is not None
    assert average == (Decimal(EXPECTED_DURATION_SUM) / Decimal(EXPECTED_SAMPLE_COUNT)).quantize(Decimal('0.01'))


def test_question_timing_is_isolated_and_null_when_no_samples() -> None:
    """题目之间互不串样本；无有效样本时平均为空、次数为 0。"""
    engine, maker = _build_timing_db()
    try:
        other_average, other_count = _query_timing(maker, OTHER_QUESTION_ID)
        missing_average, missing_count = _query_timing(maker, UNKNOWN_QUESTION_ID)
    finally:
        engine.dispose()

    assert (other_average, other_count) == (Decimal('11000.00'), 1)
    assert (missing_average, missing_count) == (None, 0)


def test_question_timing_includes_review_and_adaptive_sessions() -> None:
    """复习与自适应和普通练习同口径，逐条计入有效作答，平均与样本数一致。"""
    engine, maker = _build_mode_scope_db()
    try:
        average, count = _query_timing(maker, REVIEW_QUESTION_ID)
    finally:
        engine.dispose()

    assert count == len(REVIEW_DURATIONS)
    assert average == (Decimal(sum(REVIEW_DURATIONS)) / Decimal(len(REVIEW_DURATIONS))).quantize(Decimal('0.01'))
    assert average == Decimal('10666.67')


def test_exam_deleted_final_answer_does_not_fall_back() -> None:
    """考试最终答案被删除：删除事实被排除，也不回退把旧答案当最终样本。"""
    engine, maker = _build_mode_scope_db()
    try:
        average, count = _query_timing(maker, DELETED_FINAL_QUESTION_ID)
    finally:
        engine.dispose()

    assert (average, count) == (None, 0)


def test_exam_filtered_final_answer_does_not_fall_back() -> None:
    """考试最终答案越界被过滤：不因最终样本失效而回退采用旧答案。"""
    engine, maker = _build_mode_scope_db()
    try:
        average, count = _query_timing(maker, OUT_OF_BOUND_FINAL_QUESTION_ID)
    finally:
        engine.dispose()

    assert (average, count) == (None, 0)


def _solution_detail() -> GetPracticeSolutionDetail:
    return GetPracticeSolutionDetail(
        session_item_id=21,
        question_id=31,
        correct_rate=Decimal('0.5'),
        graded_count=4,
        attempt_count=6,
        option_select_stats={'A': 3, 'B': 3},
        answer_data={'correct': 'A'},
        grading_method='rule',
        grading_config={},
    )


def _install_service_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    solution: Any = None,
) -> tuple[AsyncMock, AsyncMock]:
    get_solution = AsyncMock(return_value=solution or _solution_detail())
    timing = AsyncMock(return_value=(Decimal('1234.50'), 3))
    monkeypatch.setattr(PracticeService, 'get_solution', get_solution)
    monkeypatch.setattr(
        practice_service_module.question_dao,
        'get',
        AsyncMock(return_value=SimpleNamespace(question_type='single_choice')),
    )
    monkeypatch.setattr(practice_service_module, 'get_question_timing', timing)
    return get_solution, timing


async def test_question_statistics_returns_filtered_average(monkeypatch: pytest.MonkeyPatch) -> None:
    """正常样本：复用既有统计字段并附加过滤后的平均用时。"""
    get_solution, timing = _install_service_stubs(monkeypatch)
    db = _ReadOnlyDB()

    detail = await practice_service.get_question_statistics(
        db=db,
        session_key='sess-practice-01',
        user_id=7,
        session_item_id=21,
    )

    assert isinstance(detail, PracticeQuestionStatisticsDetail)
    assert detail.correct_rate == Decimal('0.5')
    assert detail.graded_count == 4
    assert detail.attempt_count == 6
    assert detail.option_select_stats == {'A': 3, 'B': 3}
    assert detail.avg_duration_ms == Decimal('1234.50')
    assert detail.duration_sample_count == 3
    assert detail.duration_min_ms == 1_000
    assert detail.duration_max_ms == 300_000
    get_solution.assert_awaited_once_with(
        db=db,
        session_key='sess-practice-01',
        user_id=7,
        session_item_id=21,
    )
    assert timing.await_args.args[0] is db
    assert timing.await_args.kwargs['question_id'] == 31
    assert db.touched == []


async def test_question_statistics_without_timing_samples_returns_null_average(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无有效用时样本时平均为空、次数为 0，其余统计照常返回。"""
    get_solution, _ = _install_service_stubs(monkeypatch)
    timing = AsyncMock(return_value=(None, 0))
    monkeypatch.setattr(practice_service_module, 'get_question_timing', timing)
    db = _ReadOnlyDB()

    detail = await practice_service.get_question_statistics(
        db=db,
        session_key='sess-practice-01',
        user_id=7,
        session_item_id=21,
    )

    assert detail.avg_duration_ms is None
    assert detail.duration_sample_count == 0
    assert detail.graded_count == 4
    assert detail.attempt_count == 6
    get_solution.assert_awaited_once()
    assert db.touched == []


@pytest.mark.parametrize('error_type', ['ForbiddenError', 'NotFoundError'])
async def test_solution_errors_propagate_without_timing(
    monkeypatch: pytest.MonkeyPatch,
    error_type: str,
) -> None:
    """解析阶段的可见性/归属错误原样抛出，且不进入题型与时用查询。"""
    error = getattr(errors, error_type)(msg='提交答案后才可查看解析')
    monkeypatch.setattr(PracticeService, 'get_solution', AsyncMock(side_effect=error))
    question_get = AsyncMock()
    timing = AsyncMock()
    monkeypatch.setattr(practice_service_module.question_dao, 'get', question_get)
    monkeypatch.setattr(practice_service_module, 'get_question_timing', timing)

    with pytest.raises(type(error)):
        await practice_service.get_question_statistics(
            db=_ReadOnlyDB(),
            session_key='sess-practice-01',
            user_id=7,
            session_item_id=21,
        )

    question_get.assert_not_awaited()
    timing.assert_not_awaited()


@pytest.mark.parametrize('question_type', ['fill_blank', 'short_answer', None])
async def test_unsupported_question_type_is_rejected_before_timing(
    monkeypatch: pytest.MonkeyPatch,
    question_type: str | None,
) -> None:
    """仅选择题支持用时统计，其他题型或缺失题目直接 RequestError。"""
    _install_service_stubs(monkeypatch)
    question = None if question_type is None else SimpleNamespace(question_type=question_type)
    monkeypatch.setattr(
        practice_service_module.question_dao,
        'get',
        AsyncMock(return_value=question),
    )
    timing = AsyncMock()
    monkeypatch.setattr(practice_service_module, 'get_question_timing', timing)

    with pytest.raises(errors.RequestError, match='仅选择题支持选择与用时统计'):
        await practice_service.get_question_statistics(
            db=_ReadOnlyDB(),
            session_key='sess-practice-01',
            user_id=7,
            session_item_id=21,
        )

    timing.assert_not_awaited()


STATISTICS_PATH = '/api/v1/qbank-v2/sessions/{session_key}/items/{session_item_id}/statistics'


def test_statistics_route_exposes_detail_schema() -> None:
    """真实路由注册新 GET，并通过响应模型暴露四个用时字段。"""
    app = FastAPI()
    app.include_router(question_bank_v2_router)
    spec = app.openapi()

    assert STATISTICS_PATH in spec['paths']
    operation = spec['paths'][STATISTICS_PATH]['get']
    assert operation['operationId'] == 'qbank_v2_get_practice_question_statistics'

    wrappers = spec['components']['schemas']
    ref = operation['responses']['200']['content']['application/json']['schema']['$ref']
    wrapper = wrappers[ref.rsplit('/', 1)[-1]]
    assert set(wrapper['properties']) == {'code', 'msg', 'data'}

    detail = wrappers['PracticeQuestionStatisticsDetail']['properties']
    assert {'avg_duration_ms', 'duration_sample_count', 'duration_min_ms', 'duration_max_ms'} <= set(detail)
    assert detail['avg_duration_ms']['anyOf'][0]['type'] in {'string', 'number'}
    assert detail['duration_min_ms']['default'] == 1_000
    assert detail['duration_max_ms']['default'] == 300_000


async def _request_detail(detail: PracticeQuestionStatisticsDetail) -> dict[str, Any]:
    app = FastAPI()

    @app.get('/detail')
    async def get_detail() -> PracticeQuestionStatisticsDetail:
        return detail

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url='http://testserver') as client:
        response = await client.get('/detail')
    assert response.status_code == 200
    return response.json()


async def test_statistics_detail_serializes_average_and_null_case() -> None:
    """最小 ASGI 契约：平均用时按十进制串返回，无样本时为空值。"""
    with_samples = await _request_detail(
        PracticeQuestionStatisticsDetail(
            avg_duration_ms=Decimal('1234.50'),
            duration_sample_count=3,
        )
    )
    without_samples = await _request_detail(
        PracticeQuestionStatisticsDetail(
            avg_duration_ms=None,
            duration_sample_count=0,
        )
    )

    assert with_samples['avg_duration_ms'] == '1234.50'
    assert with_samples['duration_sample_count'] == 3
    assert with_samples['duration_min_ms'] == 1_000
    assert with_samples['duration_max_ms'] == 300_000
    assert without_samples['avg_duration_ms'] is None
    assert without_samples['duration_sample_count'] == 0
