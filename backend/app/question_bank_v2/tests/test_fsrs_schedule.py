import asyncio

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.service import review_schedule_service as schedule_module
from backend.app.question_bank_v2.service.practice_schedule_service import (
    ALGORITHM,
    first_practice_time,
    schedule,
)
from backend.app.question_bank_v2.service.practice_schedule_service import (
    engine as qbank_engine,
)
from backend.app.question_bank_v2.service.review_schedule_service import ReviewScheduleService
from backend.common.fsrs import FSRSEngine


def _new_wrong_state(**overrides: object) -> SimpleNamespace:
    data = {
        'id': 31,
        'user_id': 7,
        'question_id': 11,
        'status': 'active',
        'resolved_time': None,
        'wrong_count': 1,
        'correct_streak': 0,
        'review_count': 0,
        'fsrs_data': {},
        'last_rating': None,
        'last_duration_ms': None,
        'next_practice_time': None,
        'entry_metadata': {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _new_attempt(**overrides: object) -> SimpleNamespace:
    data = {
        'id': 101,
        'user_id': 7,
        'question_id': 11,
        'is_correct': False,
        'attempt_no': 1,
        'duration_ms': 5000,
        'submitted_time': datetime(2026, 7, 27, 12, tzinfo=UTC),
        'response_data': 'B',
        'grading_result': {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_public_fsrs_defaults_not_mutated_by_qbank_config() -> None:
    """公共 FSRS 默认参数独立，不被题库配置改变（如 fuzzing 等）"""
    public_engine = FSRSEngine()
    assert public_engine.scheduler.enable_fuzzing is True
    assert qbank_engine.scheduler.enable_fuzzing is False
    assert qbank_engine.scheduler.desired_retention == pytest.approx(0.9)
    assert public_engine.scheduler.desired_retention == pytest.approx(0.9)
    assert qbank_engine.scheduler.learning_steps == ()
    assert qbank_engine.scheduler.relearning_steps == ()
    assert public_engine.scheduler.learning_steps
    assert public_engine.scheduler.relearning_steps


@pytest.mark.parametrize('duration_ms', [200, 1500, 8000, 30000])
def test_different_durations_wrong_always_again(duration_ms: int) -> None:
    """不同用时答错均派生 Again (rating=1)，真实调用 FSRS 引擎计算 next_due"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    state = _new_wrong_state(fsrs_data={})
    attempt = _new_attempt(duration_ms=duration_ms, is_correct=False, submitted_time=now)

    ReviewScheduleService._advance_schedule(wrong_state=state, attempt=attempt)

    assert state.last_rating == 1
    assert state.fsrs_data['state'] == 2
    assert state.fsrs_data['last_attempt_id'] == attempt.id
    assert state.next_practice_time is not None
    # 验证真实的 FSRS schedule 产生 Next due
    _, expected_due = schedule({}, rating=1, now=now)
    assert state.next_practice_time == expected_due
    # attempt 的 grading_result 补齐 _memory
    assert attempt.grading_result['_memory']['rating'] == 1
    assert attempt.grading_result['_memory']['algorithm'] == ALGORITHM


@pytest.mark.parametrize('duration_ms', [200, 1500, 8000, 30000])
def test_correct_defaults_to_good(duration_ms: int) -> None:
    """正确默认 Good (rating=3)，真实计算 next_due 和记忆状态"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    state = _new_wrong_state(fsrs_data={})
    attempt = _new_attempt(duration_ms=duration_ms, is_correct=True, submitted_time=now)

    ReviewScheduleService._advance_schedule(wrong_state=state, attempt=attempt)

    assert state.last_rating == 3
    assert state.fsrs_data['last_attempt_id'] == attempt.id
    _, expected_due = schedule({}, rating=3, now=now)
    assert state.next_practice_time == expected_due
    assert attempt.grading_result['_memory']['rating'] == 3


def test_first_wrong_starts_next_day() -> None:
    """第一次错误次日冷启动 (+1天)，但 FSRS 仍记录 Again 记忆证据"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    due = first_practice_time(now)
    assert due == now + timedelta(days=1)


def test_same_attempt_will_not_advance_twice() -> None:
    """同 attempt 不会二次推进，避免重复回调累积推进记忆"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    state = _new_wrong_state(fsrs_data={})
    attempt = _new_attempt(id=999, is_correct=True, submitted_time=now)

    ReviewScheduleService._advance_schedule(wrong_state=state, attempt=attempt)
    first_snapshot = dict(state.fsrs_data)
    first_due = state.next_practice_time

    # 二次调用
    ReviewScheduleService._advance_schedule(wrong_state=state, attempt=attempt)
    assert state.fsrs_data == first_snapshot
    assert state.next_practice_time == first_due


def test_second_attempt_in_same_session_does_not_change_memory() -> None:
    """同会话第二次提交 (attempt_no != 1) 不改变记忆"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    state = _new_wrong_state(fsrs_data={'state': 1, 'stability': 1.0, 'last_attempt_id': 100})
    # 第二次作答
    attempt = _new_attempt(id=102, attempt_no=2, is_correct=True, submitted_time=now)

    ReviewScheduleService._advance_schedule(wrong_state=state, attempt=attempt)
    assert state.fsrs_data['last_attempt_id'] == 100
    assert state.last_rating is None


def test_late_grading_does_not_regress_memory() -> None:
    """迟到判分不倒退：AI 慢判提交时间早于已记录的 last_review 时丢弃调度更新"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    newer_time = now + timedelta(hours=2)
    state = _new_wrong_state(
        fsrs_data={'state': 1, 'last_review': newer_time.isoformat(), 'last_attempt_id': 200},
        last_rating=3,
        next_practice_time=newer_time + timedelta(days=3),
    )
    # 迟到的更早作答 (submitted_time 早于 newer_time)
    late_attempt = _new_attempt(id=190, attempt_no=1, is_correct=False, submitted_time=now)

    ReviewScheduleService._advance_schedule(wrong_state=state, attempt=late_attempt)
    assert state.fsrs_data['last_attempt_id'] == 200
    assert state.fsrs_data['last_review'] == newer_time.isoformat()
    assert state.last_rating == 3


def test_resolved_still_scheduled() -> None:
    """resolved 题目仍推进记忆排期，不终止回测"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    state = _new_wrong_state(status='resolved', fsrs_data={})
    attempt = _new_attempt(id=301, is_correct=True, submitted_time=now)

    ReviewScheduleService._advance_schedule(wrong_state=state, attempt=attempt)
    assert state.fsrs_data['last_attempt_id'] == 301
    assert state.last_rating == 3
    assert state.next_practice_time is not None


def test_suspended_skipped() -> None:
    """suspended 状态的错题跳过 FSRS 调度推进"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    state = _new_wrong_state(status='suspended', fsrs_data={})
    attempt = _new_attempt(id=401, is_correct=True, submitted_time=now)

    ReviewScheduleService._advance_schedule(wrong_state=state, attempt=attempt)
    assert state.fsrs_data == {}
    assert state.last_rating is None
    assert state.next_practice_time is None


@pytest.mark.asyncio
async def test_memorize_mode_does_not_advance_fsrs(monkeypatch: pytest.MonkeyPatch) -> None:
    """背题/旧卷回看模式 (memorize) 不推进 FSRS 调度"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    state = _new_wrong_state(fsrs_data={})
    mastery = SimpleNamespace(
        attempt_count=0, correct_count=0, last_attempt_time=None, state='learning', mastery_score=Decimal(0)
    )
    attempt = _new_attempt(
        id=501,
        is_correct=False,
        response_data={'mode': 'memorize'},
        submitted_time=now,
    )
    session_item = SimpleNamespace(bank_item_id=17, display_config={})

    monkeypatch.setattr(schedule_module.wrong_question_state_dao, 'get_by_question', AsyncMock(return_value=state))

    await ReviewScheduleService._sync_wrong_state(
        db=None,
        attempt=attempt,
        session_item=session_item,
        mastery=mastery,
        resolve_threshold=3,
    )

    assert state.fsrs_data == {}
    assert state.last_rating is None


@pytest.mark.asyncio
async def test_wrong_answer_first_practice_time_and_memory_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """首次答错建立错题本状态，启动规则为次日 (+1天)，但 FSRS 真实推进 Again 状态"""
    now = datetime(2026, 7, 27, 12, tzinfo=UTC)
    mastery = SimpleNamespace(
        attempt_count=0, correct_count=0, last_attempt_time=None, state='learning', mastery_score=Decimal(0)
    )
    attempt = _new_attempt(id=601, is_correct=False, duration_ms=4500, submitted_time=now)
    session_item = SimpleNamespace(bank_item_id=17, display_config={})

    created_state: SimpleNamespace | None = None

    async def fake_create(_db: object, data: dict[str, object]) -> SimpleNamespace:
        nonlocal created_state
        await asyncio.sleep(0)
        created_state = _new_wrong_state(**{k: v for k, v in data.items() if k != 'created_by'})
        return created_state

    monkeypatch.setattr(schedule_module.wrong_question_state_dao, 'get_by_question', AsyncMock(return_value=None))
    monkeypatch.setattr(schedule_module.wrong_question_state_dao, 'create', fake_create)

    await ReviewScheduleService._sync_wrong_state(
        db=None,
        attempt=attempt,
        session_item=session_item,
        mastery=mastery,
        resolve_threshold=3,
    )

    assert created_state is not None
    # 首次答错次日冷启动验证
    assert created_state.next_practice_time == now + timedelta(days=1)
    # FSRS 记忆状态如实记录 Again
    assert created_state.last_rating == 1
    assert created_state.fsrs_data.get('last_attempt_id') == 601
    assert created_state.fsrs_data.get('state') == 2
    assert attempt.grading_result.get('_memory') is not None


@pytest.mark.asyncio
async def test_late_grading_preserves_last_practice_time_and_wrong_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """迟到判分不得覆盖 last_practice_time 与错题状态（如 resolved/active/streak）"""
    newer_time = datetime(2026, 7, 27, 14, tzinfo=UTC)
    earlier_time = datetime(2026, 7, 27, 10, tzinfo=UTC)

    state = _new_wrong_state(
        status='resolved',
        correct_streak=3,
        last_practice_time=newer_time,
        last_wrong_time=newer_time,
        last_rating=3,
        next_practice_time=newer_time + timedelta(days=5),
        fsrs_data={'state': 1, 'last_review': newer_time.isoformat(), 'last_attempt_id': 200},
    )
    mastery = SimpleNamespace(
        attempt_count=3, correct_count=3, last_attempt_time=newer_time, state='mastered', mastery_score=Decimal('1.0')
    )
    late_attempt = _new_attempt(id=190, attempt_no=1, is_correct=False, submitted_time=earlier_time)
    session_item = SimpleNamespace(bank_item_id=17, display_config={})

    monkeypatch.setattr(schedule_module.wrong_question_state_dao, 'get_by_question', AsyncMock(return_value=state))

    await ReviewScheduleService._sync_wrong_state(
        db=None,
        attempt=late_attempt,
        session_item=session_item,
        mastery=mastery,
        resolve_threshold=3,
    )

    # 验证状态未被较早的答错覆盖为 active，streak 未被清零，last_practice_time 仍为 newer_time
    assert state.status == 'resolved'
    assert state.correct_streak == 3
    assert state.last_practice_time == newer_time
    assert state.last_rating == 3
    assert state.fsrs_data['last_attempt_id'] == 200
    assert state.fsrs_data['last_review'] == newer_time.isoformat()
