import asyncio

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from backend.app.question_bank_v2.service import statistics_service as statistics_module
from backend.app.question_bank_v2.service.difficulty_service import (
    compute_difficulty,
    should_recalculate_difficulty,
)
from backend.app.question_bank_v2.service.statistics_service import StatisticsService


def test_difficulty_requires_enough_valid_attempts() -> None:
    assert compute_difficulty(
        valid_attempts=49,
        valid_correct=10,
        valid_avg_duration_ms=Decimal(5000),
        median_duration_ms=Decimal(5000),
    ) is None


def test_lower_correct_rate_produces_higher_difficulty() -> None:
    easy = compute_difficulty(
        valid_attempts=100,
        valid_correct=90,
        valid_avg_duration_ms=Decimal(5000),
        median_duration_ms=Decimal(5000),
    )
    hard = compute_difficulty(
        valid_attempts=100,
        valid_correct=20,
        valid_avg_duration_ms=Decimal(5000),
        median_duration_ms=Decimal(5000),
    )

    assert easy is not None and hard is not None
    assert Decimal('1.0') <= easy < hard <= Decimal('5.0')


def test_relative_duration_only_adjusts_within_bounds() -> None:
    fast = compute_difficulty(
        valid_attempts=100,
        valid_correct=50,
        valid_avg_duration_ms=Decimal(1000),
        median_duration_ms=Decimal(5000),
    )
    slow = compute_difficulty(
        valid_attempts=100,
        valid_correct=50,
        valid_avg_duration_ms=Decimal(15000),
        median_duration_ms=Decimal(5000),
    )

    assert fast is not None and slow is not None
    assert Decimal('1.0') <= fast < slow <= Decimal('5.0')


def test_recalculate_cadence_starts_at_fifty() -> None:
    assert should_recalculate_difficulty(49) is False
    assert should_recalculate_difficulty(50) is True
    assert should_recalculate_difficulty(51) is False
    assert should_recalculate_difficulty(60) is True


def test_statistics_triggers_difficulty_at_recalculation_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    attempt = SimpleNamespace(question_id=91, is_correct=True)

    async def fake_daily(*_args: Any, **_kwargs: Any) -> bool:
        await asyncio.sleep(0)
        return False

    async def fake_user(*_args: Any, **_kwargs: Any) -> None:
        await asyncio.sleep(0)

    async def fake_question(*_args: Any, **_kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0)
        return SimpleNamespace(graded_count=50)

    async def fake_recalculate(**kwargs: Any) -> None:
        await asyncio.sleep(0)
        calls.append(kwargs['question_id'])

    monkeypatch.setattr(statistics_module.user_daily_statistics_dao, 'apply_attempt', fake_daily)
    monkeypatch.setattr(statistics_module.user_practice_statistics_dao, 'apply_attempt', fake_user)
    monkeypatch.setattr(statistics_module.question_statistics_dao, 'apply_attempt', fake_question)
    monkeypatch.setattr(statistics_module.difficulty_service, 'recalculate', fake_recalculate)

    asyncio.run(StatisticsService.apply_attempt(db=None, attempt=attempt, max_score=Decimal(1)))

    assert calls == [91]
