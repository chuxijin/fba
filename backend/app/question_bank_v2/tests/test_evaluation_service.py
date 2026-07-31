import asyncio

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.service.evaluation_service import EvaluationService


def test_session_evaluation_refreshes_aggregates_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """整场 AI 判分完成后只能重算一次会话聚合"""
    session = SimpleNamespace(id=1, mode='practice', status='submitted')
    contexts = [SimpleNamespace(), SimpleNamespace()]
    runs = [SimpleNamespace(attempt_id=11, id=101), SimpleNamespace(attempt_id=12, id=102)]
    db = AsyncMock()

    get_session = AsyncMock(return_value=session)
    get_contexts = AsyncMock(return_value=contexts)
    prepare = AsyncMock(return_value=([], [SimpleNamespace(), SimpleNamespace()]))
    execute = AsyncMock(return_value=runs)
    refresh = AsyncMock()

    monkeypatch.setattr(
        'backend.app.question_bank_v2.service.evaluation_service.practice_session_dao.get_by_key',
        get_session,
    )
    monkeypatch.setattr(
        'backend.app.question_bank_v2.service.evaluation_service.evaluation_run_dao.list_latest_subjective_contexts',
        get_contexts,
    )
    monkeypatch.setattr(EvaluationService, '_prepare_attempts', prepare)
    monkeypatch.setattr(EvaluationService, '_run_prepared_attempts', execute)
    monkeypatch.setattr(
        'backend.app.question_bank_v2.service.evaluation_service.practice_session_dao.refresh_aggregates',
        refresh,
    )

    result = asyncio.run(
        EvaluationService.evaluate_session_attempts(
            db=db,
            session_key='session-123',
            user_id=7,
            force_regenerate=False,
            model_name=None,
        )
    )

    refresh.assert_awaited_once_with(db, session)
    assert [run.attempt_id for run in result] == [11, 12]
