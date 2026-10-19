"""学习会话需保留当前用户的收藏状态，且新词使用默认未收藏状态。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.vocab.service import study_service as module


@pytest.mark.parametrize('mode', ['review', 'learn', 'all'])
async def test_session_preserves_starred_state(monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    db = object()
    now = datetime(2026, 10, 16, tzinfo=UTC)
    words = {
        word_id: SimpleNamespace(id=word_id, word=f'word-{word_id}', frequency=1, created_time=now)
        for word_id in [1, 2, 3]
    }
    due = [
        SimpleNamespace(id=11, word_id=1, is_starred=True),
        SimpleNamespace(id=12, word_id=2, is_starred=False),
    ]
    due_query = AsyncMock(return_value=due)
    monkeypatch.setattr(
        module.user_setting_dao,
        'get_or_create',
        AsyncMock(
            return_value=SimpleNamespace(
                daily_review_limit=20,
                daily_new_target=10,
            )
        ),
    )
    monkeypatch.setattr(module.user_word_dao, 'get_due_words', due_query)
    monkeypatch.setattr(module.user_word_dao, 'get_learned_word_ids', AsyncMock(return_value={1, 2}))
    monkeypatch.setattr(module.user_book_dao, 'get_active_book', AsyncMock(return_value=SimpleNamespace(book_id=7)))
    monkeypatch.setattr(module.book_word_dao, 'get_word_ids_by_book', AsyncMock(return_value=[1, 2, 3]))
    monkeypatch.setattr(module.word_dao, 'select_model', AsyncMock(side_effect=lambda _db, word_id: words[word_id]))
    monkeypatch.setattr(module.definition_dao, 'get_by_word_id', AsyncMock(return_value=[]))
    monkeypatch.setattr(module.example_dao, 'get_by_word_id', AsyncMock(return_value=[]))

    result = await module.StudyService.get_study_session(db=db, user_id=42, mode=mode)
    payload = result.model_dump()
    expected_ids = [3] if mode == 'learn' else [1, 2] if mode == 'review' else [1, 2, 3]
    assert [item['word']['id'] for item in payload['words']] == expected_ids
    assert [item['is_starred'] for item in payload['words']] == [word_id == 1 for word_id in expected_ids]
    assert [item['is_new'] for item in payload['words']] == [word_id == 3 for word_id in expected_ids]
    assert result.new_count == (mode != 'review')
    assert result.review_count == (0 if mode == 'learn' else 2)
    assert result.total == len(expected_ids)
    if mode == 'learn':
        due_query.assert_not_awaited()
    else:
        assert due_query.await_args.args[1] == 42
