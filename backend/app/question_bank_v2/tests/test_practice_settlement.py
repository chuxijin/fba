"""练习结算回归：到期结算幂等、考试延迟投影与交卷结果脱敏。

全部用例只用内存对象和 AsyncMock，不连接真实数据库。
"""

import asyncio

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.question_bank_v2.crud.crud_practice import question_attempt_dao
from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.service import practice_service as practice_module
from backend.app.question_bank_v2.service import statistics_service as statistics_module
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.app.question_bank_v2.service.reward_service import PracticeReward
from backend.app.question_bank_v2.service.statistics_service import statistics_service
from backend.common.model import Base
from backend.utils.timezone import timezone


class _FakeDB:
    """只提供结算链路需要的异步 execute / flush。"""

    def __init__(self) -> None:
        self.statements: list[Any] = []
        self.flush_count = 0

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        self.statements.append(statement)
        return SimpleNamespace(
            scalars=lambda: SimpleNamespace(first=lambda: None),
            first=lambda: None,
        )

    async def flush(self) -> None:
        self.flush_count += 1


async def test_expire_if_due_settles_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """到期结算只执行一次；再次调用时已终态不再重复累计统计。"""
    session = SimpleNamespace(
        user_id=7,
        status='in_progress',
        expires_time=timezone.now() - timedelta(minutes=1),
        submitted_time=None,
    )
    apply_deferred = AsyncMock()
    apply_submission = AsyncMock()
    monkeypatch.setattr(PracticeService, '_apply_deferred_attempts', staticmethod(apply_deferred))
    monkeypatch.setattr(statistics_module.statistics_service, 'apply_session_submission', apply_submission)
    db = _FakeDB()

    first = await PracticeService._expire_if_due(db=db, session=session)

    assert first is True
    assert session.status == 'expired'
    assert session.submitted_time is not None
    apply_deferred.assert_awaited_once_with(db=db, session=session)
    apply_submission.assert_awaited_once_with(db=db, user_id=7)

    second = await PracticeService._expire_if_due(db=db, session=session)

    assert second is False
    apply_deferred.assert_awaited_once()
    apply_submission.assert_awaited_once()


async def test_practice_mode_never_defers_projection(monkeypatch: pytest.MonkeyPatch) -> None:
    """普通练习提交即投影，结算阶段不应再延迟重放。"""
    session = SimpleNamespace(id=11, user_id=7, mode='practice')
    lock_questions = AsyncMock()
    apply = AsyncMock()
    get_latest = AsyncMock()
    monkeypatch.setattr(practice_module.attempt_projection_service, 'lock_questions', lock_questions)
    monkeypatch.setattr(practice_module.attempt_projection_service, 'apply', apply)
    monkeypatch.setattr(practice_module.question_attempt_dao, 'get_latest_by_session', get_latest)

    await PracticeService._apply_deferred_attempts(db=_FakeDB(), session=session)

    get_latest.assert_not_awaited()
    lock_questions.assert_not_awaited()
    apply.assert_not_awaited()


async def test_exam_deferred_projection_applies_once_per_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """同一作答反复结算只投影一次，依靠真实 _projection 标记，不 mock apply。"""
    from backend.app.question_bank_v2.service import attempt_projection_service as projection_module

    attempt = SimpleNamespace(
        id=41,
        user_id=7,
        question_id=31,
        is_correct=True,
        score=Decimal('1.00'),
        grading_result={'_submission': {'key': 'key:k', 'fingerprint': 'f' * 64, 'save_version': 1}},
    )
    item = SimpleNamespace(id=21, question_id=31, max_score=Decimal('1.00'))
    session = SimpleNamespace(id=11, user_id=7, mode='exam')
    monkeypatch.setattr(
        practice_module.preference_service,
        'get',
        AsyncMock(return_value=SimpleNamespace(mastery_threshold=3)),
    )
    monkeypatch.setattr(
        practice_module.question_attempt_dao,
        'get_latest_by_session',
        AsyncMock(return_value=[(attempt, item)]),
    )
    review_apply = AsyncMock()
    statistics_apply = AsyncMock()
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_attempt', review_apply)
    monkeypatch.setattr(projection_module.statistics_service, 'apply_attempt', statistics_apply)
    db = _FakeDB()

    await PracticeService._apply_deferred_attempts(db=db, session=session)

    assert attempt.grading_result['_projection'] == {'submitted': True, 'graded': True}
    review_apply.assert_awaited_once()
    statistics_apply.assert_awaited_once()

    await PracticeService._apply_deferred_attempts(db=db, session=session)

    review_apply.assert_awaited_once()
    statistics_apply.assert_awaited_once()
    assert attempt.grading_result['_projection'] == {'submitted': True, 'graded': True}


async def test_hide_settles_open_session_before_hiding(monkeypatch: pytest.MonkeyPatch) -> None:
    """隐藏进行中会话先结算再标记删除，状态落为已交卷。"""
    session = SimpleNamespace(
        id=11,
        user_id=7,
        status='in_progress',
        source_snapshot={},
        deleted=0,
        deleted_time=None,
        submitted_time=None,
    )
    deleted_when_settled: list[int] = []
    apply_deferred = AsyncMock()

    def observe(**kwargs: Any) -> None:
        deleted_when_settled.append(session.deleted)

    apply_deferred.side_effect = observe
    apply_submission = AsyncMock()
    monkeypatch.setattr(practice_module.practice_session_dao, 'get_by_key', AsyncMock(return_value=session))
    monkeypatch.setattr(PracticeService, '_apply_deferred_attempts', staticmethod(apply_deferred))
    monkeypatch.setattr(statistics_module.statistics_service, 'apply_session_submission', apply_submission)
    db = _FakeDB()

    await PracticeService.hide(db=db, session_key='session-123', user_id=7)

    assert deleted_when_settled == [0]
    assert session.status == 'submitted'
    assert session.submitted_time is not None
    assert session.deleted == 11
    assert session.deleted_time is not None
    apply_submission.assert_awaited_once_with(db=db, user_id=7)


async def test_hide_preserves_terminal_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """已终态会话隐藏时不改写状态、不重复结算。"""
    submitted_time = timezone.now() - timedelta(hours=1)
    session = SimpleNamespace(
        id=12,
        user_id=7,
        status='graded',
        source_snapshot={},
        deleted=0,
        deleted_time=None,
        submitted_time=submitted_time,
    )
    apply_deferred = AsyncMock()
    apply_submission = AsyncMock()
    monkeypatch.setattr(practice_module.practice_session_dao, 'get_by_key', AsyncMock(return_value=session))
    monkeypatch.setattr(PracticeService, '_apply_deferred_attempts', staticmethod(apply_deferred))
    monkeypatch.setattr(statistics_module.statistics_service, 'apply_session_submission', apply_submission)

    await PracticeService.hide(db=_FakeDB(), session_key='session-123', user_id=7)

    apply_deferred.assert_not_awaited()
    apply_submission.assert_not_awaited()
    assert session.status == 'graded'
    assert session.submitted_time == submitted_time
    assert session.deleted == 12


async def test_get_session_solutions_locks_session_for_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """整卷解析必须带 for_update，避免与结算交错读到半更新状态。"""
    session = SimpleNamespace(id=11, user_id=7, status='submitted', source_snapshot={})
    get_by_key = AsyncMock(return_value=session)
    monkeypatch.setattr(practice_module.practice_session_dao, 'get_by_key', get_by_key)
    monkeypatch.setattr(
        practice_module.practice_session_dao,
        'get_solutions',
        AsyncMock(return_value=[]),
    )

    db = _FakeDB()

    result = await PracticeService.get_session_solutions(db=db, session_key='session-123', user_id=7)

    assert result == []
    get_by_key.assert_awaited_once_with(db, 'session-123', user_id=7, for_update=True)


async def test_expired_submit_is_idempotent_and_never_conflicts(monkeypatch: pytest.MonkeyPatch) -> None:
    """到时交卷落到 expired，重复交卷原样返回，不抛 Conflict。"""
    session = SimpleNamespace(
        id=11,
        user_id=7,
        session_key='session-123',
        mode='exam',
        status='in_progress',
        expires_time=timezone.now() - timedelta(minutes=1),
        submitted_time=None,
        total_items=2,
        answered_items=1,
        correct_items=1,
        score=Decimal('1.00'),
        source_snapshot={},
    )
    monkeypatch.setattr(practice_module.practice_session_dao, 'get_by_key', AsyncMock(return_value=session))
    monkeypatch.setattr(PracticeService, '_apply_deferred_attempts', staticmethod(AsyncMock()))
    monkeypatch.setattr(statistics_module.statistics_service, 'apply_session_submission', AsyncMock())
    monkeypatch.setattr(
        practice_module.practice_reward_service,
        'resolve_granted_practice_reward',
        AsyncMock(return_value=PracticeReward()),
    )
    monkeypatch.setattr(
        practice_module.practice_reward_service,
        'resolve_granted_check_in_reward',
        AsyncMock(return_value=PracticeReward()),
    )
    db = _FakeDB()

    first = await PracticeService.submit_session(db=db, session_key='session-123', user_id=7)
    second = await PracticeService.submit_session(db=db, session_key='session-123', user_id=7)

    assert first.status == 'expired'
    assert second.status == 'expired'
    assert first.submitted_time == second.submitted_time


async def test_submission_result_hides_exam_grade_before_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    """考试未交卷时单题提交不回传判分与统计快照。"""
    snapshot = AsyncMock(return_value={'correct_rate': Decimal(1)})
    monkeypatch.setattr(statistics_module.statistics_service, 'question_snapshot', snapshot)
    session = SimpleNamespace(mode='exam', status='in_progress')
    item = SimpleNamespace(id=21, question_id=31, max_score=Decimal('2.00'))
    attempt = SimpleNamespace(
        id=41,
        attempt_no=1,
        grading_status='graded',
        grading_method='exact',
        is_correct=True,
        score=Decimal('2.00'),
    )

    result = await PracticeService._submission_result(
        db=_FakeDB(),
        session=session,
        session_item=item,
        attempt=attempt,
        save_version=1,
    )

    assert result.is_correct is None
    assert result.score is None
    assert result.response_status == 'graded'
    assert result.max_score == Decimal('2.00')
    snapshot.assert_not_awaited()


async def test_submission_result_reveals_grade_after_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    """考试交卷后单题提交才回传判分与统计快照。"""
    snapshot = AsyncMock(return_value={'correct_rate': Decimal(1)})
    monkeypatch.setattr(statistics_module.statistics_service, 'question_snapshot', snapshot)
    session = SimpleNamespace(mode='exam', status='submitted')
    item = SimpleNamespace(id=21, question_id=31, max_score=Decimal('2.00'))
    attempt = SimpleNamespace(
        id=41,
        attempt_no=1,
        grading_status='graded',
        grading_method='exact',
        is_correct=True,
        score=Decimal('2.00'),
    )

    result = await PracticeService._submission_result(
        db=_FakeDB(),
        session=session,
        session_item=item,
        attempt=attempt,
        save_version=1,
    )

    assert result.is_correct is True
    assert result.score == Decimal('2.00')
    snapshot.assert_awaited_once()


async def test_question_snapshot_without_samples_returns_none_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    """没有已判样本时正确率为空，而不是伪装成 0%。"""
    monkeypatch.setattr(
        statistics_module.question_statistics_dao,
        'get_by_question',
        AsyncMock(return_value=None),
    )

    snapshot = await statistics_service.question_snapshot(db=_FakeDB(), question_id=31)

    assert snapshot['correct_rate'] is None
    assert snapshot['graded_count'] == 0
    assert snapshot['attempt_count'] == 0
    assert snapshot['option_select_stats'] == {}


async def test_question_snapshot_two_of_three(monkeypatch: pytest.MonkeyPatch) -> None:
    """2/3 个已判样本的正确率按真实比例输出。"""
    statistics = SimpleNamespace(
        graded_count=3,
        correct_count=2,
        attempt_count=5,
        response_distribution={'A': 1, 'B': 1, 'C': 1},
    )
    monkeypatch.setattr(
        statistics_module.question_statistics_dao,
        'get_by_question',
        AsyncMock(return_value=statistics),
    )

    snapshot = await statistics_service.question_snapshot(db=_FakeDB(), question_id=31)

    assert snapshot['graded_count'] == 3
    assert float(snapshot['correct_rate']) == pytest.approx(2 / 3)


async def test_question_snapshot_splits_multiple_choice_combinations(monkeypatch: pytest.MonkeyPatch) -> None:
    """多选组合按选项拆分计数，A,C 与 B,C 各为每项加频次。"""
    statistics = SimpleNamespace(
        graded_count=3,
        correct_count=1,
        attempt_count=3,
        response_distribution={'A,C': 2, 'B,C': 1},
    )
    monkeypatch.setattr(
        statistics_module.question_statistics_dao,
        'get_by_question',
        AsyncMock(return_value=statistics),
    )

    snapshot = await statistics_service.question_snapshot(db=_FakeDB(), question_id=31)

    assert snapshot['option_select_stats'] == {'A': 2, 'C': 3, 'B': 1}


class _SyncSessionAsAsync:
    """把同步 Session 包装成 DAO 需要的最小异步接口。"""

    def __init__(self, session: Any) -> None:
        self._session = session

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self._session.execute(statement, *args, **kwargs)


def test_latest_attempt_per_item_excludes_intermediate_modifications() -> None:
    """结算投影读取每题最高 attempt_no，交卷前的中间修改不进入统计样本。"""
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        engine,
        tables=[QbPracticeSessionItem.__table__, QbQuestionAttempt.__table__],
    )
    maker = sessionmaker(bind=engine)
    seed = maker()
    item = QbPracticeSessionItem(session_id=11, question_id=31, position=0)
    item.id = 21
    seed.add(item)
    for attempt_no, answer in ((1, 'A'), (2, 'B'), (3, 'C')):
        attempt = QbQuestionAttempt(
            user_id=7,
            question_id=31,
            response_data={'answer': answer},
            session_id=11,
            session_item_id=21,
            attempt_no=attempt_no,
            grading_result={
                '_submission': {
                    'key': f'key:{attempt_no}',
                    'fingerprint': 'f' * 64,
                    'save_version': attempt_no,
                },
            },
        )
        attempt.id = 40 + attempt_no
        seed.add(attempt)
    seed.commit()
    seed.close()

    session = maker()
    try:
        rows = asyncio.run(question_attempt_dao.get_latest_by_session(_SyncSessionAsAsync(session), 11))
    finally:
        session.close()
        engine.dispose()

    assert len(rows) == 1
    latest, delivered_item = rows[0]
    assert latest.session_item_id == 21
    assert latest.attempt_no == 3
    assert latest.response_data == {'answer': 'C'}
    assert delivered_item.id == 21
