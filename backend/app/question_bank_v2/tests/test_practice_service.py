import asyncio

from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.access.constants import ReasonCode
from backend.app.access.schema.engine import Decision
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank_v2.service import practice_service as practice_service_module
from backend.app.question_bank_v2.service.grading_service import practice_grading_service
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.common.exception import errors


def test_create_session_checks_bank_access_before_delivery(monkeypatch) -> None:
    """创建会话先做题库准入，再固定当前发布版本和题目版本"""
    bank = SimpleNamespace(id=21, current_revision_id=31)
    revision = SimpleNamespace(
        id=31,
        status='published',
        duration_minutes=None,
        name='大学英语四级真题',
    )
    candidates = [
        SimpleNamespace(
            id=41,
            question_id=51,
            question_revision_id=61,
            score=Decimal('2.00'),
            settings={},
        )
    ]
    created = SimpleNamespace(id=71, session_key='client-session-001')
    call_order: list[str] = []

    async def fake_ensure(**kwargs):
        call_order.append('access')
        assert kwargs['bank_id'] == 21
        return bank, Decision.allow(reason_code=ReasonCode.SUBSCRIPTION_ACCESS)

    async def fake_get_revision(*_args, **_kwargs):
        call_order.append('revision')
        return revision

    async def fake_get_by_key(*_args, **_kwargs):
        return None

    async def fake_get_candidates(*_args, **kwargs):
        call_order.append('candidates')
        assert kwargs['bank_revision_id'] == 31
        return candidates

    async def fake_create(*_args, **_kwargs):
        call_order.append('session')
        return created

    async def fake_create_all(*_args, **kwargs):
        call_order.append('items')
        assert kwargs['candidates'][0].question_revision_id == 61

    expected = SimpleNamespace(session_key='client-session-001')

    async def fake_get_detail(**_kwargs):
        return expected

    monkeypatch.setattr(practice_service_module.bank_access_service, 'ensure_bank_access', fake_ensure)
    monkeypatch.setattr(practice_service_module.bank_revision_dao, 'get', fake_get_revision)
    monkeypatch.setattr(practice_service_module.practice_session_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(practice_service_module.practice_session_item_dao, 'get_candidates', fake_get_candidates)
    monkeypatch.setattr(practice_service_module.practice_session_dao, 'create', fake_create)
    monkeypatch.setattr(practice_service_module.practice_session_item_dao, 'create_all', fake_create_all)
    monkeypatch.setattr(practice_service_module.PracticeService, 'get', fake_get_detail)

    result = asyncio.run(
        practice_service.create(
            db=None,
            user_id=7,
            obj=CreatePracticeSessionParam(bank_id=21, session_key='client-session-001'),
        )
    )

    assert result is expected
    assert call_order == ['access', 'revision', 'candidates', 'session', 'items']


def test_objective_grading_supports_exact_and_unordered_multiple_choice() -> None:
    """内置判分覆盖四六级常用单选与无序多选"""
    exact = practice_grading_service.grade(
        response_data=' A ',
        answer_data={'correct': 'A'},
        grading_method='exact',
        grading_config={},
        question_type='single_choice',
        max_score=Decimal('2.00'),
    )
    multiple = practice_grading_service.grade(
        response_data=['C', 'A'],
        answer_data={'correct': ['A', 'C']},
        grading_method='exact',
        grading_config={},
        question_type='multiple_choice',
        max_score=Decimal('3.00'),
    )

    assert (exact.is_correct, exact.score, exact.grading_status, exact.grading_method) == (
        True,
        Decimal('2.00'),
        'graded',
        'rule',
    )
    assert (multiple.is_correct, multiple.score, multiple.grading_status, multiple.grading_method) == (
        True,
        Decimal('3.00'),
        'graded',
        'rule',
    )


def test_manual_grading_never_fabricates_score() -> None:
    """主观题提交后保持待判分，不能按是否有文本直接给分"""
    result = practice_grading_service.grade(
        response_data='student essay',
        answer_data={'correct': 'reference answer'},
        grading_method='rubric',
        grading_config={},
        question_type='short_answer',
        max_score=Decimal('10.00'),
    )

    assert (result.is_correct, result.score, result.grading_status, result.grading_method) == (
        None,
        None,
        'pending',
        'manual',
    )


def test_idempotent_session_retry_does_not_recheck_access(monkeypatch) -> None:
    """同一创建请求重试应复用既有会话，不受之后权益变化影响"""
    existing = SimpleNamespace(
        user_id=7,
        mode='practice',
        source_snapshot={'bank_id': 21, 'section_id': None},
        delivery_config={'shuffle': False, 'requested_limit': None},
    )

    async def fake_get_by_key(*_args, **_kwargs):
        return existing

    async def fail_access(**_kwargs):
        raise AssertionError('idempotent retry must not recheck bank access')

    expected = SimpleNamespace(session_key='client-session-001')

    async def fake_get_detail(**_kwargs):
        return expected

    monkeypatch.setattr(practice_service_module.practice_session_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(practice_service_module.bank_access_service, 'ensure_bank_access', fail_access)
    monkeypatch.setattr(practice_service_module.PracticeService, 'get', fake_get_detail)

    result = asyncio.run(
        practice_service.create(
            db=None,
            user_id=7,
            obj=CreatePracticeSessionParam(bank_id=21, session_key='client-session-001'),
        )
    )

    assert result is expected


def test_idempotency_key_rejects_different_create_request(monkeypatch) -> None:
    """同一幂等键不能静默复用到不同题库或抽题条件"""
    existing = SimpleNamespace(
        user_id=7,
        mode='practice',
        source_snapshot={'bank_id': 99, 'section_id': None},
        delivery_config={'shuffle': False, 'requested_limit': None},
    )

    async def fake_get_by_key(*_args, **_kwargs):
        return existing

    monkeypatch.setattr(practice_service_module.practice_session_dao, 'get_by_key', fake_get_by_key)

    with pytest.raises(errors.ConflictError, match='会话标识已被其他请求使用'):
        asyncio.run(
            practice_service.create(
                db=None,
                user_id=7,
                obj=CreatePracticeSessionParam(bank_id=21, session_key='client-session-001'),
            )
        )
