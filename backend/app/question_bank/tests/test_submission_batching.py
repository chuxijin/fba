import asyncio

from collections.abc import Coroutine
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank.api.v1 import session as session_api
from backend.app.question_bank.crud.crud_mastery import mastery_dao
from backend.app.question_bank.crud.crud_question import question_statistics_dao
from backend.app.question_bank.schema.practice import SubmitPracticeSessionParam, SubmitPracticeSessionResult

T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async unit under the project's synchronous test setup."""
    return asyncio.run(coro)


class ScalarResult:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows

    def scalars(self) -> 'ScalarResult':
        return self

    def all(self) -> list[Any]:
        return self.rows


class RowResult:
    def __init__(self, rows: list[tuple[int, Decimal | None]]) -> None:
        self.rows = rows

    def all(self) -> list[tuple[int, Decimal | None]]:
        return self.rows


class FakeMasteryDb:
    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
        self.execute_count = 0
        self.flush_count = 0

    async def execute(self, _stmt: object) -> ScalarResult:
        self.execute_count += 1
        return ScalarResult(self.rows)

    async def flush(self) -> None:
        self.flush_count += 1

    def add(self, _row: object) -> None:
        raise AssertionError('existing mastery rows should be updated in place')


class TransactionContext:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, _exc_type: object, _exc: object, _tb: object) -> bool:
        return False


class FakeTransactionDb:
    def __init__(self) -> None:
        self.begin_count = 0

    def begin(self) -> TransactionContext:
        self.begin_count += 1
        return TransactionContext()


def test_median_answer_time_map_uses_one_query() -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=RowResult([(11, Decimal('5.555')), (12, None)])))

    result = run(question_statistics_dao.get_median_answer_time_map(db, [11, 12]))

    assert result == {11: Decimal('5.56')}
    db.execute.assert_awaited_once()


def test_apply_answer_batch_loads_and_flushes_once() -> None:
    correct_row = SimpleNamespace(
        question_id=11,
        status='learning',
        correct_streak=2,
        mastered_time=None,
        last_practice_time=None,
        next_review_time=None,
    )
    wrong_row = SimpleNamespace(
        question_id=12,
        status='mastered',
        correct_streak=4,
        mastered_time=object(),
        last_practice_time=None,
        next_review_time=None,
    )
    db = FakeMasteryDb([correct_row, wrong_row])

    result = run(
        mastery_dao.apply_answer_batch(
            db,
            user_id=7,
            answers=[(11, True), (12, False)],
            mastery_threshold=3,
        )
    )

    assert result == [correct_row, wrong_row]
    assert db.execute_count == 1
    assert db.flush_count == 1
    assert correct_row.correct_streak == 3
    assert correct_row.status == 'mastered'
    assert correct_row.mastered_time is not None
    assert wrong_row.correct_streak == 0
    assert wrong_row.status == 'learning'


def test_idempotent_submit_skips_completion_side_effects(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SubmitPracticeSessionResult(
        completed_count=2,
        correct_count=1,
        wrong_count=1,
        accuracy_rate=Decimal(50),
    )
    db = FakeTransactionDb()
    publish = AsyncMock()

    monkeypatch.setattr(session_api, '_resolve_session_id', AsyncMock(return_value=31))
    monkeypatch.setattr(session_api.session_service, 'submit_session', AsyncMock(return_value=(result, False)))
    monkeypatch.setattr(session_api, 'publish', publish)

    response = run(
        session_api.submit_session(
            request=SimpleNamespace(user=SimpleNamespace(id=7)),
            db=db,
            session_key='session-key',
            obj=SubmitPracticeSessionParam(total_time=30),
        )
    )

    assert response.data == result
    assert db.begin_count == 1
    publish.assert_not_awaited()
