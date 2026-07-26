import asyncio

from collections.abc import Coroutine
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank.api.v1 import question as question_api
from backend.app.question_bank.api.v1 import upload as upload_api
from backend.app.question_bank.schema.question import UpdateQuestionParam
from backend.app.question_bank.service.question_service import QuestionService

T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async unit under the project's synchronous test setup."""
    return asyncio.run(coro)


def test_question_detail_does_not_include_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    question = SimpleNamespace(options=[], placements=[])
    captured: dict[str, bool] = {}

    def fake_serialize_question(**kwargs: object) -> dict[str, object]:
        captured['include_analysis'] = bool(kwargs['include_analysis'])
        return {}

    monkeypatch.setattr(
        'backend.app.question_bank.service.question_service.question_dao.get_with_relations',
        AsyncMock(return_value=question),
    )
    monkeypatch.setattr(QuestionService, 'serialize_question', staticmethod(fake_serialize_question))

    data = run(QuestionService.get(db=object(), pk=1))

    assert captured['include_analysis'] is False
    assert 'answer_data' not in data
    assert 'analyses' not in data


def test_solution_endpoint_verifies_question_access(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_verify = AsyncMock()
    fake_get_solution = AsyncMock(return_value={'correct_answer': 'A'})

    monkeypatch.setattr(question_api.membership_service, 'verify_question_access', fake_verify)
    monkeypatch.setattr(question_api.question_service, 'get_solution', fake_get_solution)

    request = SimpleNamespace(user=SimpleNamespace(id=7, is_superuser=False))
    db = object()
    run(question_api.get_question_solution(request=request, db=db, pk=11, user_answer=None))

    fake_verify.assert_awaited_once_with(db=db, user_id=7, question_id=11)


def test_solution_cache_uses_fresh_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    cached = {
        'content': {'correct_answer': 'A', 'analysis': 'cached analysis'},
        'question_type': 'single',
        'answer_data': {'correct': 'A'},
    }
    statistics = SimpleNamespace(correct_rate=Decimal('75.50'), option_select_stats={'A': 3})

    monkeypatch.setattr(
        'backend.app.question_bank.service.question_service.solution_content_cache.get',
        AsyncMock(return_value=cached),
    )
    monkeypatch.setattr(
        'backend.app.question_bank.service.question_service.question_statistics_dao.get_by_question_id',
        AsyncMock(return_value=statistics),
    )

    payload = run(QuestionService.get_solution(db=object(), question_id=1, user_answer='A'))

    assert payload['analysis'] == 'cached analysis'
    assert payload['correct_rate'] == Decimal('75.50')
    assert payload['option_select_stats'] == {'A': 3}
    assert payload['is_correct'] is True


def test_question_update_invalidates_solution_content(monkeypatch: pytest.MonkeyPatch) -> None:
    question = SimpleNamespace(options=[])
    invalidate = AsyncMock()

    class FakeDb:
        async def flush(self) -> None:
            return None

    monkeypatch.setattr(
        'backend.app.question_bank.service.question_service.question_dao.get',
        AsyncMock(return_value=question),
    )
    monkeypatch.setattr(
        'backend.app.question_bank.service.question_service.solution_content_cache.invalidate',
        invalidate,
    )

    result = run(
        QuestionService.update(
            db=FakeDb(),
            pk=9,
            obj=UpdateQuestionParam(options=[]),
            user_id=3,
        )
    )

    assert result == 1
    invalidate.assert_awaited_once_with(9)


def test_upload_avatar_uses_authenticated_user(monkeypatch: pytest.MonkeyPatch) -> None:
    update_avatar = AsyncMock()

    monkeypatch.setattr(upload_api, 'upload_file_verify', lambda _file: None)
    monkeypatch.setattr(
        upload_api.storage_service,
        'upload',
        AsyncMock(return_value=('https://cdn.example/avatar.png', 'avatar-key')),
    )
    monkeypatch.setattr(upload_api.user_account_dao, 'update_avatar_by_sys_user_id', update_avatar)

    request = SimpleNamespace(user=SimpleNamespace(id=23))
    db = object()
    run(upload_api.upload_avatar(request=request, db=db, file=object()))

    update_avatar.assert_awaited_once_with(db, 23, 'https://cdn.example/avatar.png')
