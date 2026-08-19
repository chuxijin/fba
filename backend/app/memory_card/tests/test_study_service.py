#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ruff: noqa: ANN001, ANN202, DTZ001, RUF029
from datetime import datetime
from types import SimpleNamespace

from backend.app.memory_card.service import study_service as study_module
from backend.app.memory_card.service.study_service import study_service


class _FakeDB:
    """极简异步假数据库：flush 时为主键未赋值对象分配递增 ID。"""

    def __init__(self) -> None:
        self._seq = 0
        self._added: list = []

    def add(self, obj) -> None:
        self._added.append(obj)

    async def flush(self) -> None:
        for obj in self._added:
            if getattr(obj, 'id', None) is None:
                self._seq += 1
                obj.id = self._seq
        self._added = []


def _fake_db() -> _FakeDB:
    return _FakeDB()


def _card(
    card_id: int = 1,
    deck_id: int = 1,
    card_type: str = 'cloze',
    response_mode: str = 'input',
) -> SimpleNamespace:
    return SimpleNamespace(
        id=card_id,
        deck_id=deck_id,
        title='句子测试',
        card_type=card_type,
        response_mode=response_mode,
        status='active',
    )


def _revision(card_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        card_id=card_id,
        revision_no=1,
        content={
            'segments': [
                {'type': 'text', 'text': '我是一个'},
                {'type': 'point', 'id': 'p1', 'correct': '很好', 'wrong': '很坏', 'hint': '品格词'},
                {'type': 'text', 'text': '的人'},
            ],
        },
    )


async def test_check_returns_revealed_answer_and_forecast(monkeypatch) -> None:
    async def fake_load_accessible_card(*args, **kwargs):
        return _card()

    async def fake_get_current(*args, **kwargs):
        return _revision()

    async def fake_get_by_user_and_card(*args, **kwargs):
        return None

    monkeypatch.setattr(study_module.StudyService, '_load_accessible_card', fake_load_accessible_card)
    monkeypatch.setattr(study_module.memory_card_revision_dao, 'get_current', fake_get_current)
    monkeypatch.setattr(study_module.memory_card_user_state_dao, 'get_by_user_and_card', fake_get_by_user_and_card)

    from backend.app.memory_card.schema.study import CheckMemoryCardParam

    result = await study_service.check(
        db=None,
        user_id=7,
        card_id=1,
        obj=CheckMemoryCardParam(response_data={'p1': '很好'}),
    )
    assert result.check_result == 'correct'
    assert result.blanks[0].correct is True
    assert result.blanks[0].blank_id == 'p1'
    assert result.blanks[0].correct_answer == '很好'
    assert result.recommended_rating == 3
    assert result.hints == [{'blank_id': 'p1', 'hint': '品格词'}]


async def test_review_schedules_fsrs_and_is_idempotent(monkeypatch) -> None:
    async def fake_load_accessible_card(*args, **kwargs):
        return _card()

    async def fake_get_current(*args, **kwargs):
        return _revision()

    log_results: list = []

    async def fake_get_by_idempotency(*args, **kwargs):
        return log_results[0] if log_results else None

    async def fake_get_state(*args, **kwargs):
        return None

    monkeypatch.setattr(study_module.StudyService, '_load_accessible_card', fake_load_accessible_card)
    monkeypatch.setattr(study_module.memory_card_revision_dao, 'get_current', fake_get_current)
    monkeypatch.setattr(study_module.memory_card_review_log_dao, 'get_by_idempotency', fake_get_by_idempotency)
    monkeypatch.setattr(study_module.memory_card_user_state_dao, 'get_by_user_and_card', fake_get_state)

    from backend.app.memory_card.schema.study import SubmitMemoryReviewParam

    # 首次提交创建状态与日志
    result = await study_service.review(
        db=_fake_db(),
        user_id=7,
        obj=SubmitMemoryReviewParam(
            card_id=1,
            rating=3,
            idempotency_key='client-review-001',
            check_result='correct',
            response_data={'b1': '很好'},
        ),
    )
    assert result.card_id == 1
    assert result.next_due is not None
    assert result.review_log_id > 0

    # 记录日志占位，模拟幂等命中
    log_results.append(
        SimpleNamespace(
            id=result.review_log_id,
            card_id=1,
            next_due=result.next_due,
            next_state=result.new_state,
            next_stability=result.stability,
            next_difficulty=result.difficulty,
        )
    )
    again = await study_service.review(
        db=_fake_db(),
        user_id=7,
        obj=SubmitMemoryReviewParam(
            card_id=1,
            rating=1,
            idempotency_key='client-review-001',
        ),
    )
    assert again.review_log_id == result.review_log_id
    assert again.next_due == result.next_due


async def test_review_with_existing_state_schedules_next_review(monkeypatch) -> None:
    async def fake_load_accessible_card(*args, **kwargs):
        return _card()

    async def fake_get_current(*args, **kwargs):
        return _revision()

    async def fake_get_by_idempotency(*args, **kwargs):
        return None

    existing = SimpleNamespace(
        user_id=7,
        card_id=1,
        status='active',
        state=2,
        step=0,
        stability=12.0,
        difficulty=5.0,
        due=datetime(2026, 8, 1),
        last_review=datetime(2026, 8, 1),
        learned_revision_id=10,
        review_count=3,
        lapse_count=1,
        last_rating=3,
    )

    async def fake_get_state(*args, **kwargs):
        return existing

    monkeypatch.setattr(study_module.StudyService, '_load_accessible_card', fake_load_accessible_card)
    monkeypatch.setattr(study_module.memory_card_revision_dao, 'get_current', fake_get_current)
    monkeypatch.setattr(study_module.memory_card_review_log_dao, 'get_by_idempotency', fake_get_by_idempotency)
    monkeypatch.setattr(study_module.memory_card_user_state_dao, 'get_by_user_and_card', fake_get_state)

    from backend.app.memory_card.schema.study import SubmitMemoryReviewParam

    result = await study_service.review(
        db=_fake_db(),
        user_id=7,
        obj=SubmitMemoryReviewParam(card_id=1, rating=3, idempotency_key='client-review-002'),
    )
    assert result.new_state == 2
    assert result.next_due is not None
    assert existing.review_count == 4
