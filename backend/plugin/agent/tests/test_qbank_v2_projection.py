import asyncio

from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.plugin.agent.service.adapter import qbank_v2_projection as projection_module
from backend.plugin.agent.service.adapter.qbank_v2_projection import QbankV2ProjectionService


class FakeSession:
    async def flush(self) -> None:
        return None


def _context(*, projection: dict[str, object] | None = None) -> SimpleNamespace:
    attempt = SimpleNamespace(
        id=78,
        user_id=20,
        question_id=29668,
        response_data='作答',
        submitted_time=SimpleNamespace(date=lambda: None),
        duration_ms=1000,
        is_correct=None,
        score=None,
        grading_status='pending',
        grading_method='manual',
        grading_result={'agent_projection': projection} if projection else {},
    )
    return SimpleNamespace(
        attempt=attempt,
        session=SimpleNamespace(id=75),
        session_item=SimpleNamespace(id=1265, max_score=Decimal('10.00'), bank_item_id=1),
    )


def test_projection_score_uses_display_score_and_clamps() -> None:
    service = QbankV2ProjectionService()
    assert service._score({'display_score': 8.456}, Decimal(10)) == Decimal('8.46')
    assert service._score({'display_score': 12}, Decimal(10)) == Decimal(10)
    assert service._score({'score': 100}, Decimal(10)) is None


def test_valid_projection_updates_attempt_without_overwriting_newer_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _context()
    calls = {'review': 0, 'statistics': 0, 'refresh': 0, 'response': 0}

    async def get_context(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return context

    async def apply_review(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        calls['review'] += 1

    async def apply_statistics(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        calls['statistics'] += 1

    async def is_latest(*_args: object, **_kwargs: object) -> bool:
        await asyncio.sleep(0)
        return False

    async def get_response(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        calls['response'] += 1
        return

    async def refresh(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        calls['refresh'] += 1

    monkeypatch.setattr(projection_module.evaluation_run_dao, 'get_attempt_context', get_context)
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_delayed_grade', apply_review)
    monkeypatch.setattr(projection_module.statistics_service, 'apply_delayed_grade', apply_statistics)
    monkeypatch.setattr(projection_module.question_attempt_dao, 'is_latest_for_item', is_latest)
    monkeypatch.setattr(projection_module.practice_response_dao, 'get', get_response)
    monkeypatch.setattr(projection_module.practice_session_dao, 'refresh_aggregates', refresh)
    run = SimpleNamespace(id=1, result_payload={'score_status': 'valid'})

    applied = asyncio.run(
        QbankV2ProjectionService().project_success(
            db=FakeSession(),
            run=run,
            attempt_id=78,
            user_id=20,
            result={'score_status': 'valid', 'display_score': 8.5},
        )
    )

    assert applied is True
    assert context.attempt.score == Decimal('8.50')
    assert context.attempt.is_correct is True
    assert context.attempt.grading_status == 'graded'
    assert context.attempt.grading_method == 'ai'
    assert context.attempt.grading_result['agent_projection'] == {'agent_run_id': 1, 'status': 'graded'}
    assert calls == {'review': 1, 'statistics': 1, 'refresh': 1, 'response': 0}


def test_repeated_projection_does_not_repeat_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(projection={'agent_run_id': 1, 'status': 'graded'})
    calls = {'review': 0, 'statistics': 0}

    async def get_context(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return context

    async def apply_review(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        calls['review'] += 1

    async def apply_statistics(*_args: object, **_kwargs: object) -> None:
        await asyncio.sleep(0)
        calls['statistics'] += 1

    async def is_latest(*_args: object, **_kwargs: object) -> bool:
        await asyncio.sleep(0)
        return False

    monkeypatch.setattr(projection_module.evaluation_run_dao, 'get_attempt_context', get_context)
    monkeypatch.setattr(projection_module.review_schedule_service, 'apply_delayed_grade', apply_review)
    monkeypatch.setattr(projection_module.statistics_service, 'apply_delayed_grade', apply_statistics)
    monkeypatch.setattr(projection_module.question_attempt_dao, 'is_latest_for_item', is_latest)
    run = SimpleNamespace(id=2, result_payload={'score_status': 'valid'})

    applied = asyncio.run(
        QbankV2ProjectionService().project_success(
            db=FakeSession(),
            run=run,
            attempt_id=78,
            user_id=20,
            result={'score_status': 'valid', 'display_score': 9},
        )
    )

    assert applied is True
    assert calls == {'review': 0, 'statistics': 0}
    assert context.attempt.grading_result['agent_projection'] == {'agent_run_id': 2, 'status': 'graded'}
    assert run.result_payload['qbank_projection'] == {
        'status': 'regraded',
        'attempt_id': 78,
        'previous_agent_run_id': 1,
        'score': '9.00',
        'is_correct': True,
    }


def test_older_projection_cannot_overwrite_newer_run(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context(projection={'agent_run_id': 3, 'status': 'graded'})

    async def get_context(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return context

    monkeypatch.setattr(projection_module.evaluation_run_dao, 'get_attempt_context', get_context)
    run = SimpleNamespace(id=2, result_payload={'score_status': 'valid'})

    applied = asyncio.run(
        QbankV2ProjectionService().project_success(
            db=FakeSession(),
            run=run,
            attempt_id=78,
            user_id=20,
            result={'score_status': 'valid', 'display_score': 7},
        )
    )

    assert applied is False
    assert context.attempt.grading_result['agent_projection'] == {'agent_run_id': 3, 'status': 'graded'}
    assert run.result_payload['qbank_projection']['status'] == 'superseded'


def test_provisional_projection_requires_review_without_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _context()
    response = SimpleNamespace(
        status='submitted',
        grading_status='pending',
        is_correct=None,
        score=None,
        graded_time=None,
    )

    async def get_context(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return context

    async def is_latest(*_args: object, **_kwargs: object) -> bool:
        await asyncio.sleep(0)
        return True

    async def get_response(*_args: object, **_kwargs: object) -> SimpleNamespace:
        await asyncio.sleep(0)
        return response

    monkeypatch.setattr(projection_module.evaluation_run_dao, 'get_attempt_context', get_context)
    monkeypatch.setattr(projection_module.question_attempt_dao, 'is_latest_for_item', is_latest)
    monkeypatch.setattr(projection_module.practice_response_dao, 'get', get_response)
    run = SimpleNamespace(id=3, result_payload={'score_status': 'provisional'})

    applied = asyncio.run(
        QbankV2ProjectionService().project_success(
            db=FakeSession(),
            run=run,
            attempt_id=78,
            user_id=20,
            result={'score_status': 'provisional', 'display_score': 8},
        )
    )

    assert applied is False
    assert context.attempt.grading_status == 'review_required'
    assert response.status == 'review_required'
    assert response.grading_status == 'review_required'
