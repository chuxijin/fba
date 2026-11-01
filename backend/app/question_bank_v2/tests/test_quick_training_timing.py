"""限时训练：考试倒计时、幂等时长匹配与入参边界回归。"""

import asyncio

from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError

from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam, PracticeModuleQuota
from backend.app.question_bank_v2.service import practice_service as module
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.app.question_bank_v2.tests.test_practice_quick_entries import (
    _matching_session,
    _patch_create_common,
)
from backend.common.exception import errors


def _timed_exam(**overrides: Any) -> CreatePracticeSessionParam:
    params: dict[str, Any] = {
        'source_type': 'custom',
        'knowledge_point_ids': [201],
        'mode': 'exam',
        'duration_minutes': 10,
        'limit': 2,
    }
    params.update(overrides)
    return CreatePracticeSessionParam(**params)


def _quota_exam(duration_minutes: int) -> CreatePracticeSessionParam:
    return CreatePracticeSessionParam(
        source_type='custom',
        module_quotas=[PracticeModuleQuota(knowledge_point_id=201, count=2)],
        limit=2,
        mode='exam',
        duration_minutes=duration_minutes,
    )


def _create(monkeypatch: pytest.MonkeyPatch, obj: CreatePracticeSessionParam, candidates: Any) -> dict[str, Any]:
    captured = _patch_create_common(monkeypatch, candidates)
    asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj))
    return captured['values']


def test_custom_knowledge_exam_sets_ten_minute_window(monkeypatch: pytest.MonkeyPatch) -> None:
    values = _create(
        monkeypatch,
        _timed_exam(),
        [SimpleNamespace(question_id=11), SimpleNamespace(question_id=12)],
    )

    assert values['started_time'] is not None
    assert values['expires_time'] - values['started_time'] == timedelta(minutes=10)
    assert values['delivery_config']['requested_duration_minutes'] == 10
    # 自由组题不依赖题库发布版本
    assert values['bank_revision_id'] is None
    assert values['source_snapshot']['bank_id'] is None
    assert values['source_snapshot']['bank_revision_id'] is None


def test_module_quota_exam_sets_thirty_minute_window(monkeypatch: pytest.MonkeyPatch) -> None:
    def candidates(**_kwargs: Any) -> list[Any]:
        return [SimpleNamespace(question_id=11), SimpleNamespace(question_id=12)]

    values = _create(monkeypatch, _quota_exam(30), candidates)

    assert values['expires_time'] - values['started_time'] == timedelta(minutes=30)
    assert values['delivery_config']['requested_duration_minutes'] == 30
    assert values['delivery_config']['module_quotas'] == [{'knowledge_point_id': 201, 'count': 2}]
    assert values['bank_revision_id'] is None
    assert values['source_snapshot']['bank_id'] is None


def test_idempotent_match_distinguishes_duration() -> None:
    ten = _timed_exam(session_key='duration-key-10', duration_minutes=10)
    thirty = _timed_exam(session_key='duration-key-30', duration_minutes=30)
    session = _matching_session(thirty)

    assert PracticeService._matches_create_request(session=session, user_id=7, obj=thirty) is True
    assert PracticeService._matches_create_request(session=session, user_id=7, obj=ten) is False


def test_create_rejects_idempotency_key_with_different_duration(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_create_common(monkeypatch, [])
    session = _matching_session(_quota_exam(30))
    session.session_key = 'shared-key-01'
    monkeypatch.setattr(module.practice_session_dao, 'get_by_key', AsyncMock(return_value=session))

    obj = _timed_exam(session_key='shared-key-01', duration_minutes=10)
    with pytest.raises(errors.ConflictError, match='会话标识已被其他请求使用'):
        asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj))


@pytest.mark.parametrize('duration_minutes', [1, 600])
def test_duration_accepts_inclusive_bounds(duration_minutes: int) -> None:
    assert _timed_exam(duration_minutes=duration_minutes).duration_minutes == duration_minutes


@pytest.mark.parametrize('duration_minutes', [0, -1, 601])
def test_duration_rejects_out_of_range(duration_minutes: int) -> None:
    with pytest.raises(ValidationError):
        _timed_exam(duration_minutes=duration_minutes)


def test_high_error_practice_does_not_set_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = CreatePracticeSessionParam(
        source_type='custom',
        knowledge_point_ids=[201],
        selection_strategy='high_error',
        mode='practice',
        duration_minutes=10,
        limit=20,
    )

    values = _create(monkeypatch, obj, [SimpleNamespace(question_id=11)])

    assert values['started_time'] is not None
    assert values['expires_time'] is None
    assert values['delivery_config']['requested_duration_minutes'] == 10
    assert values['delivery_config']['selection_strategy'] == 'high_error'
