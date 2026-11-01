"""作答可靠性回归：提交幂等凭据与投影一次性。

覆盖：
- SubmitPracticeItemParam 的 submission_key 约束；
- 无 key 且无 version 时拒绝提交；
- 同 key 同 payload 返回同一 attempt，冲突 payload 拒绝；
- 会话结束后仍可用同 key 重试；
- 旧版本重试不新增，主动新 key / 最新版本新增；
- AttemptProjectionService 的投影标记、只执行一次与 delayed 补判分。
"""

import asyncio
import re

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.question_bank_v2.crud.crud_practice import question_attempt_dao
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.schema.practice import SubmitPracticeItemParam
from backend.app.question_bank_v2.service import attempt_projection_service as projection_module
from backend.app.question_bank_v2.service import evaluation_service as evaluation_module
from backend.app.question_bank_v2.service import practice_service as practice_service_module
from backend.app.question_bank_v2.service.attempt_projection_service import (
    AttemptProjectionService,
    attempt_projection_service,
)
from backend.app.question_bank_v2.service.evaluation_service import EvaluationService
from backend.app.question_bank_v2.service.practice_service import PracticeService, practice_service
from backend.common.exception import errors
from backend.common.model import Base


class _FakeDB:
    """只提供提交链路需要的异步 flush 能力。"""

    def __init__(self) -> None:
        self.flush_count = 0

    async def flush(self) -> None:
        self.flush_count += 1


class _SubmissionHarness:
    """用内存对象模拟会话题目、作答草稿和追加式作答事实。"""

    def __init__(self) -> None:
        self.attempts: list[SimpleNamespace] = []
        self.responses: dict[int, SimpleNamespace] = {}
        self.owned_calls: list[dict[str, Any]] = []
        self.db = _FakeDB()
        self.session = SimpleNamespace(
            id=11,
            user_id=7,
            mode='practice',
            source_type='bank',
            status='in_progress',
            answered_items=0,
            correct_items=0,
            score=Decimal('0.00'),
            delivery_config={'annotations_enabled': False},
            source_snapshot={},
            expires_time=None,
        )
        self.item = SimpleNamespace(
            id=21,
            session_id=11,
            question_id=31,
            max_score=Decimal('1.00'),
            bank_item_id=None,
            display_config={},
        )

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(attempt_projection_service, 'lock_questions', AsyncMock())

        async def fake_owned(**kwargs: Any) -> tuple[SimpleNamespace, SimpleNamespace]:
            await asyncio.sleep(0)
            self.owned_calls.append(kwargs)
            if getattr(self.session, 'deleted', 0) and not kwargs.get('include_hidden'):
                raise errors.NotFoundError(msg='练习会题目不存在')
            return self.session, self.item

        async def fake_get_response(
            db: Any,
            *,
            session_id: int,
            session_item_id: int,
            for_update: bool = False,
        ) -> SimpleNamespace | None:
            await asyncio.sleep(0)
            return self.responses.get(session_item_id)

        async def fake_create_response(db: Any, data: dict[str, Any]) -> SimpleNamespace:
            await asyncio.sleep(0)
            response = SimpleNamespace(**data)
            self.responses[data['session_item_id']] = response
            return response

        async def fake_get_submission(
            db: Any,
            *,
            session_item_id: int,
            submission_key: str,
        ) -> SimpleNamespace | None:
            await asyncio.sleep(0)
            for attempt in self.attempts:
                receipt = (attempt.grading_result or {}).get('_submission') or {}
                if attempt.session_item_id == session_item_id and receipt.get('key') == submission_key:
                    return attempt
            return None

        async def fake_next_attempt_no(db: Any, session_item_id: int) -> int:
            await asyncio.sleep(0)
            return len(self.attempts) + 1

        async def fake_create_attempt(db: Any, data: dict[str, Any]) -> SimpleNamespace:
            await asyncio.sleep(0)
            attempt = SimpleNamespace(id=100 + len(self.attempts), **data)
            self.attempts.append(attempt)
            return attempt

        monkeypatch.setattr(PracticeService, '_get_owned_item', staticmethod(fake_owned))
        monkeypatch.setattr(
            practice_service_module.question_answer_dao,
            'get_by_question',
            AsyncMock(
                return_value=SimpleNamespace(
                    answer_data={'correct': 'A'},
                    grading_method='exact',
                    grading_config={},
                )
            ),
        )
        monkeypatch.setattr(
            practice_service_module.question_dao,
            'get',
            AsyncMock(return_value=SimpleNamespace(question_type='single_choice')),
        )
        monkeypatch.setattr(practice_service_module.practice_response_dao, 'get', fake_get_response)
        monkeypatch.setattr(practice_service_module.practice_response_dao, 'create', fake_create_response)
        monkeypatch.setattr(practice_service_module.question_attempt_dao, 'get_submission', fake_get_submission)
        monkeypatch.setattr(practice_service_module.question_attempt_dao, 'get_next_attempt_no', fake_next_attempt_no)
        monkeypatch.setattr(practice_service_module.question_attempt_dao, 'create', fake_create_attempt)
        monkeypatch.setattr(
            practice_service_module.preference_service,
            'get',
            AsyncMock(return_value=SimpleNamespace(mastery_threshold=3)),
        )
        monkeypatch.setattr(
            practice_service_module.attempt_projection_service,
            'apply',
            AsyncMock(),
        )
        monkeypatch.setattr(
            practice_service_module.statistics_service,
            'question_snapshot',
            AsyncMock(return_value={}),
        )

    async def submit(self, **overrides: Any) -> Any:
        payload: dict[str, Any] = {
            'response_data': {'answer': 'A'},
            'duration_ms': 1000,
            'submission_key': 'client-key-1',
        }
        payload.update(overrides)
        return await practice_service.submit_item(
            db=self.db,
            session_key='sess-key-0001',
            user_id=7,
            session_item_id=self.item.id,
            obj=SubmitPracticeItemParam(**payload),
        )


def test_submission_key_is_optional_and_bounded() -> None:
    """submission_key 默认空、最大 128 字符。"""
    assert SubmitPracticeItemParam(response_data={'answer': 'A'}).submission_key is None
    assert SubmitPracticeItemParam(response_data={'answer': 'A'}, submission_key='x' * 128).submission_key == (
        'x' * 128
    )
    with pytest.raises(ValidationError):
        SubmitPracticeItemParam(response_data={'answer': 'A'}, submission_key='x' * 129)


async def test_submit_requires_submission_key_or_save_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """无 key 且无 version 无法构造兼容幂等键，直接拒绝。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)

    with pytest.raises(errors.RequestError):
        await harness.submit(submission_key=None, save_version=None)

    assert harness.attempts == []


async def test_same_key_same_payload_returns_same_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """网络重试复用 key 时必须返回同一作答事实，不重复追加。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)

    first = await harness.submit(submission_key='retry-1')
    receipt = harness.attempts[0].grading_result['_submission']

    assert len(harness.attempts) == 1
    assert receipt['key'] == 'key:retry-1'
    assert receipt['save_version'] == first.save_version == 1
    assert len(receipt['fingerprint']) == 64
    int(receipt['fingerprint'], 16)

    second = await harness.submit(submission_key='retry-1')

    assert len(harness.attempts) == 1
    assert second.attempt_id == first.attempt_id
    assert second.attempt_no == first.attempt_no
    assert second.save_version == first.save_version


async def test_same_key_canonicalizes_response_key_order(monkeypatch: pytest.MonkeyPatch) -> None:
    """同内容不同键序视为同 payload，fingerprint 应保持一致。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)

    first = await harness.submit(submission_key='retry-order', response_data={'answer': 'A', 'extra': 1})
    fingerprint = harness.attempts[0].grading_result['_submission']['fingerprint']
    second = await harness.submit(submission_key='retry-order', response_data={'extra': 1, 'answer': 'A'})

    assert len(harness.attempts) == 1
    assert second.attempt_id == first.attempt_id
    assert harness.attempts[0].grading_result['_submission']['fingerprint'] == fingerprint


@pytest.mark.parametrize(
    'overrides',
    [
        {'response_data': {'answer': 'B'}},
        {'duration_ms': 2000},
        {'save_version': 0},
    ],
)
async def test_same_key_with_different_payload_conflicts(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
) -> None:
    """同一提交标识不能复用在不同答案、时长或版本上。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)

    await harness.submit(submission_key='retry-conflict')

    with pytest.raises(errors.ConflictError):
        await harness.submit(submission_key='retry-conflict', **overrides)

    assert len(harness.attempts) == 1


async def test_same_key_retry_after_session_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """会话结束后仍可凭同一 key 取回已提交事实。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)

    first = await harness.submit(submission_key='retry-closed')
    harness.session.status = 'graded'

    second = await harness.submit(submission_key='retry-closed')

    assert len(harness.attempts) == 1
    assert second.attempt_id == first.attempt_id


async def test_new_key_appends_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """主动使用新 key 表示一次新的提交。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)

    first = await harness.submit(submission_key='key-1')
    second = await harness.submit(submission_key='key-2')

    assert len(harness.attempts) == 2
    assert second.attempt_id != first.attempt_id
    assert second.attempt_no == 2
    assert harness.attempts[1].grading_result['_submission']['key'] == 'key:key-2'


async def test_version_derived_key_idempotency_and_latest_version_append(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """无 key 时用 save_version 派生兼容键；旧版本不新增，最新版本新增。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)

    first = await harness.submit(submission_key=None, save_version=0)
    receipt = harness.attempts[0].grading_result['_submission']

    assert len(harness.attempts) == 1
    assert receipt['key'] == 'version:0'
    assert receipt['save_version'] == first.save_version == 1

    retry = await harness.submit(submission_key=None, save_version=0)

    assert len(harness.attempts) == 1
    assert retry.attempt_id == first.attempt_id

    latest = await harness.submit(submission_key=None, save_version=1)

    assert len(harness.attempts) == 2
    assert latest.attempt_id != first.attempt_id
    assert latest.attempt_no == 2
    assert latest.save_version == 2
    assert harness.attempts[1].grading_result['_submission']['key'] == 'version:1'


async def test_exam_answer_change_appends_fact_and_old_key_retry_keeps_original(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """考试交卷前允许改答案：新 key 追加事实，旧 key 重试只回放原事实，不覆盖新答案。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)
    harness.session.mode = 'exam'

    first = await harness.submit(submission_key='exam-key-a', save_version=0, response_data={'answer': 'A'})
    second = await harness.submit(submission_key='exam-key-b', save_version=1, response_data={'answer': 'B'})

    assert len(harness.attempts) == 2
    assert second.attempt_id != first.attempt_id
    assert second.attempt_no == 2
    assert second.save_version == 2
    assert harness.attempts[1].grading_result['_submission']['key'] == 'key:exam-key-b'

    retry = await harness.submit(submission_key='exam-key-a', save_version=0, response_data={'answer': 'A'})

    assert len(harness.attempts) == 2
    assert retry.attempt_id == first.attempt_id
    assert retry.attempt_no == first.attempt_no == 1
    assert harness.attempts[0].response_data == {'answer': 'A'}
    assert harness.attempts[1].response_data == {'answer': 'B'}
    assert harness.responses[harness.item.id].response_data == {'answer': 'B'}


async def test_hidden_session_same_key_returns_receipt_but_new_key_is_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """隐藏会话仍可用同一 key 取回回执；新写入必须被会话打开校验拒绝。"""
    harness = _SubmissionHarness()
    harness.install(monkeypatch)

    first = await harness.submit(submission_key='hidden-key-same')
    harness.session.deleted = 1

    retry = await harness.submit(submission_key='hidden-key-same')

    assert len(harness.attempts) == 1
    assert retry.attempt_id == first.attempt_id
    assert harness.owned_calls[-1]['include_hidden'] is True

    with pytest.raises(errors.ConflictError):
        await harness.submit(submission_key='hidden-key-new')

    assert len(harness.attempts) == 1
    assert harness.responses[harness.item.id].response_data == {'answer': 'A'}


@pytest.mark.parametrize('mode', ['exam', 'mock'])
async def test_evaluate_attempt_rejects_replaced_exam_answer(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """考试/模考只允许评测每题最新事实，被替换的作答直接冲突。"""
    context = SimpleNamespace(
        session=SimpleNamespace(mode=mode, status='submitted'),
        attempt=SimpleNamespace(session_item_id=21),
    )
    db = AsyncMock()
    is_latest = AsyncMock(return_value=False)
    prepare = AsyncMock()
    monkeypatch.setattr(
        evaluation_module.evaluation_run_dao,
        'get_attempt_context',
        AsyncMock(return_value=context),
    )
    monkeypatch.setattr(evaluation_module.question_attempt_dao, 'is_latest_for_item', is_latest)
    monkeypatch.setattr(EvaluationService, '_prepare_attempts', prepare)

    with pytest.raises(errors.ConflictError):
        await EvaluationService.evaluate_attempt(
            db=db,
            attempt_id=41,
            user_id=7,
            force_regenerate=False,
            model_name=None,
        )

    is_latest.assert_awaited_once_with(db, context.attempt)
    prepare.assert_not_awaited()


def _projection_attempt(*, is_correct: bool | None = True, grading_result: dict[str, Any] | None = None) -> Any:
    return SimpleNamespace(
        id=41,
        user_id=7,
        question_id=31,
        is_correct=is_correct,
        score=Decimal('1.00') if is_correct is not None else None,
        duration_ms=1000,
        grading_result={} if grading_result is None else grading_result,
    )


def _projection_item() -> Any:
    return SimpleNamespace(
        id=21,
        question_id=31,
        bank_item_id=None,
        max_score=Decimal('1.00'),
        display_config={},
    )


async def test_projection_marks_attempt_and_applies_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """首次投影同时写标记与两个统计，后续再调用不重复累计。"""
    db = _FakeDB()
    attempt = _projection_attempt(is_correct=True)
    item = _projection_item()
    review = AsyncMock()
    statistics = AsyncMock()
    lock = AsyncMock()
    monkeypatch.setattr(AttemptProjectionService, 'lock_questions', lock)
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_attempt', review)
    monkeypatch.setattr(projection_module.statistics_service, 'apply_attempt', statistics)

    await attempt_projection_service.apply(db=db, attempt=attempt, session_item=item)

    assert attempt.grading_result['_projection'] == {'submitted': True, 'graded': True}
    assert review.await_count == 1
    assert statistics.await_count == 1
    lock.assert_awaited_once()
    assert lock.await_args.args[0] is db
    assert lock.await_args.args[1] == [attempt.question_id]

    await attempt_projection_service.apply(db=db, attempt=attempt, session_item=item)

    assert review.await_count == 1
    assert statistics.await_count == 1


async def test_projection_marks_pending_attempt_as_not_graded(monkeypatch: pytest.MonkeyPatch) -> None:
    """主观题待判时投影只记 submitted，graded 为 False。"""
    attempt = _projection_attempt(is_correct=None)
    monkeypatch.setattr(AttemptProjectionService, 'lock_questions', AsyncMock())
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_attempt', AsyncMock())
    monkeypatch.setattr(projection_module.statistics_service, 'apply_attempt', AsyncMock())

    await attempt_projection_service.apply(db=_FakeDB(), attempt=attempt, session_item=_projection_item())

    assert attempt.grading_result['_projection'] == {'submitted': True, 'graded': False}


async def test_delayed_projection_uses_delayed_grade_only_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """已提交未判分的事实补分时只走 apply_delayed_grade，且只补一次。"""
    attempt = _projection_attempt(
        is_correct=True,
        grading_result={
            '_submission': {'key': 'key:k', 'fingerprint': 'f' * 64, 'save_version': 1},
            '_projection': {'submitted': True, 'graded': False},
        },
    )
    item = _projection_item()
    review_delayed = AsyncMock()
    statistics_delayed = AsyncMock()
    review = AsyncMock()
    statistics = AsyncMock()
    monkeypatch.setattr(AttemptProjectionService, 'lock_questions', AsyncMock())
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_delayed_grade', review_delayed)
    monkeypatch.setattr(projection_module.statistics_service, 'apply_delayed_grade', statistics_delayed)
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_attempt', review)
    monkeypatch.setattr(projection_module.statistics_service, 'apply_attempt', statistics)

    await attempt_projection_service.apply(db=_FakeDB(), attempt=attempt, session_item=item, delayed=True)

    assert review_delayed.await_count == 1
    assert statistics_delayed.await_count == 1
    assert review.await_count == 0
    assert statistics.await_count == 0
    assert attempt.grading_result['_projection'] == {'submitted': True, 'graded': True}

    await attempt_projection_service.apply(db=_FakeDB(), attempt=attempt, session_item=item, delayed=True)

    assert review_delayed.await_count == 1
    assert statistics_delayed.await_count == 1


async def test_delayed_legacy_attempt_never_replays_apply_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """没有 _submission/_projection 的老事实当作已统计基数，不重复 apply_attempt。"""
    attempt = _projection_attempt(is_correct=True, grading_result={})
    review = AsyncMock()
    statistics = AsyncMock()
    review_delayed = AsyncMock()
    statistics_delayed = AsyncMock()
    monkeypatch.setattr(AttemptProjectionService, 'lock_questions', AsyncMock())
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_attempt', review)
    monkeypatch.setattr(projection_module.statistics_service, 'apply_attempt', statistics)
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_delayed_grade', review_delayed)
    monkeypatch.setattr(projection_module.statistics_service, 'apply_delayed_grade', statistics_delayed)

    await attempt_projection_service.apply(
        db=_FakeDB(),
        attempt=attempt,
        session_item=_projection_item(),
        delayed=True,
    )

    assert review.await_count == 0
    assert statistics.await_count == 0
    assert review_delayed.await_count == 1
    assert statistics_delayed.await_count == 1
    assert attempt.grading_result['_projection'] == {'submitted': True, 'graded': True}


async def test_lock_questions_locks_sorted_unique_ids() -> None:
    """真实 lock_questions 对题目 ID 先去重升序后逐条执行。"""
    executed: list[Any] = []

    class _LockDB:
        async def execute(self, statement: Any) -> None:
            executed.append(statement)

    await AttemptProjectionService.lock_questions(_LockDB(), [3, 1, 3, 2])

    assert len(executed) == 3
    locked_ids = []
    for statement in executed:
        sql = str(statement.compile(compile_kwargs={'literal_binds': True}))
        match = re.search(r'qbank_v2_question\.id = (\d+)', sql)
        assert match is not None
        locked_ids.append(int(match.group(1)))
    assert locked_ids == [1, 2, 3]


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


def test_get_submission_reads_receipt_from_in_memory_sqlite() -> None:
    """get_submission 用真实模型在内存 SQLite 上按 submission_key 命中事实。"""
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[QbQuestionAttempt.__table__])
    maker = sessionmaker(bind=engine)
    seed = maker()
    attempt = QbQuestionAttempt(
        user_id=7,
        question_id=31,
        response_data={'answer': 'A'},
        session_id=11,
        session_item_id=21,
        attempt_no=1,
        grading_result={
            '_submission': {
                'key': 'key:retry-1',
                'fingerprint': 'f' * 64,
                'save_version': 1,
            },
        },
        submitted_time=datetime(2026, 11, 1, 9, 0, tzinfo=UTC),
    )
    attempt.id = 1
    seed.add(attempt)
    seed.commit()
    seed.close()

    session = maker()
    try:
        found = asyncio.run(
            question_attempt_dao.get_submission(
                _SyncSessionAsAsync(session),
                session_item_id=21,
                submission_key='key:retry-1',
            )
        )
        missing = asyncio.run(
            question_attempt_dao.get_submission(
                _SyncSessionAsAsync(session),
                session_item_id=21,
                submission_key='key:absent',
            )
        )
    finally:
        session.close()
        engine.dispose()

    assert found is not None
    assert found.id == 1
    assert found.grading_result['_submission']['key'] == 'key:retry-1'
    assert missing is None
