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
            question_id=61,
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
        assert kwargs['candidates'][0].question_id == 61

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


def test_trial_access_is_checked_in_delivery_order(monkeypatch) -> None:
    """试看准入应按投递序号逐题透传, 并在耗尽后截断会话题目"""
    candidates = [SimpleNamespace(question_id=index) for index in range(4)]
    calls: list[dict] = []

    async def fake_ensure(**kwargs):
        calls.append(kwargs)
        if kwargs['question_ordinal'] >= 2:
            return SimpleNamespace(id=21), Decision.deny(reason_code=ReasonCode.TRIAL_EXHAUSTED)
        return SimpleNamespace(id=21), Decision.allow(reason_code=ReasonCode.TRIAL_POLICY)

    monkeypatch.setattr(practice_service_module.bank_access_service, 'ensure_bank_access', fake_ensure)

    result = asyncio.run(
        PracticeService._filter_accessible_candidates(
            db=None,
            user_id=7,
            bank_id=21,
            candidates=candidates,
            source_ref_prefix='qbank:test-session',
            consume=True,
        )
    )

    assert result == candidates[:2]
    assert [call['question_ordinal'] for call in calls] == [0, 1, 2]
    assert all(call['question_total'] == 4 for call in calls)
    assert calls[-1]['source_ref'] == 'qbank:test-session:2'


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


def test_session_report_separates_wrong_pending_and_unanswered(monkeypatch) -> None:
    session = {
        'id': 71,
        'session_key': 'client-session-001',
        'bank_id': 21,
        'mode': 'practice',
        'source_type': 'bank',
        'title_snapshot': '大学英语四级真题',
        'status': 'graded',
        'score': Decimal('3.00'),
        'started_time': practice_service_module.timezone.now(),
        'submitted_time': practice_service_module.timezone.now(),
    }
    rows = [
        {
            'session_item_id': 1,
            'position': 0,
            'question_id': 101,
            'bank_item_id': 201,
            'section_id': 301,
            'section_name': '听力',
            'response_status': 'graded',
            'is_correct': True,
            'score': Decimal('2.00'),
            'max_score': Decimal('2.00'),
            'duration_ms': 1000,
        },
        {
            'session_item_id': 2,
            'position': 1,
            'question_id': 102,
            'bank_item_id': 202,
            'section_id': 301,
            'section_name': '听力',
            'response_status': 'graded',
            'is_correct': False,
            'score': Decimal('0.00'),
            'max_score': Decimal('2.00'),
            'duration_ms': 2000,
        },
        {
            'session_item_id': 3,
            'position': 2,
            'question_id': 103,
            'bank_item_id': 203,
            'section_id': 302,
            'section_name': '写作',
            'response_status': 'submitted',
            'is_correct': None,
            'score': None,
            'max_score': Decimal('10.00'),
            'duration_ms': 3000,
        },
        {
            'session_item_id': 4,
            'position': 3,
            'question_id': 104,
            'bank_item_id': 204,
            'section_id': 302,
            'section_name': '写作',
            'response_status': None,
            'is_correct': None,
            'score': None,
            'max_score': Decimal('10.00'),
            'duration_ms': 0,
        },
    ]

    async def fake_get_detail(*_args, **_kwargs):
        return session

    async def fake_get_report_items(*_args, **_kwargs):
        return rows

    monkeypatch.setattr(practice_service_module.practice_session_dao, 'get_detail', fake_get_detail)
    monkeypatch.setattr(practice_service_module.practice_session_dao, 'get_report_items', fake_get_report_items)

    result = asyncio.run(practice_service.get_report(db=None, session_key='client-session-001', user_id=7))

    assert (result.answered_items, result.graded_items, result.correct_items, result.wrong_items) == (3, 2, 1, 1)
    assert (result.pending_items, result.unanswered_items) == (1, 1)
    assert result.accuracy_rate == Decimal('0.5000')
    assert result.total_score == Decimal('24.00')
    assert result.total_duration_ms == 6000
    assert result.wrong_question_ids == [102]


def test_session_solutions_require_submission(monkeypatch) -> None:
    async def fake_get_by_key(*_args, **_kwargs):
        return SimpleNamespace(id=71, status='in_progress')

    async def fail_get_solutions(*_args, **_kwargs):
        raise AssertionError('open session must not load authoritative answers')

    monkeypatch.setattr(practice_service_module.practice_session_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(practice_service_module.practice_session_dao, 'get_solutions', fail_get_solutions)

    with pytest.raises(errors.ForbiddenError, match='交卷后才可查看整场答案解析'):
        asyncio.run(
            practice_service.get_session_solutions(db=None, session_key='client-session-001', user_id=7)
        )


class _HookDb:
    """交卷回调只需要 flush 与 begin_nested，其余走 fake"""

    def __init__(self) -> None:
        self.nested_count = 0

    async def flush(self) -> None:
        return None

    def begin_nested(self) -> '_HookDb':
        self.nested_count += 1
        return self

    async def __aenter__(self) -> '_HookDb':
        return self

    async def __aexit__(self, *_exc_info) -> bool:
        return False


def _submitted_session() -> SimpleNamespace:
    return SimpleNamespace(
        id=71,
        session_key='client-session-001',
        user_id=7,
        status='in_progress',
        submitted_time=None,
        total_items=3,
        answered_items=3,
        correct_items=2,
        score=Decimal('6.00'),
    )


def _patch_submit_dependencies(monkeypatch, session) -> None:
    async def fake_get_by_key(*_args, **_kwargs):
        return session

    async def fake_ensure_open(**_kwargs):
        return None

    async def fake_apply_deferred(**_kwargs):
        return None

    async def fake_has_pending(*_args, **_kwargs):
        return False

    async def fake_apply_submission(**_kwargs):
        return None

    monkeypatch.setattr(practice_service_module.practice_session_dao, 'get_by_key', fake_get_by_key)
    monkeypatch.setattr(practice_service_module.PracticeService, '_ensure_session_open', fake_ensure_open)
    monkeypatch.setattr(practice_service_module.PracticeService, '_apply_deferred_attempts', fake_apply_deferred)
    monkeypatch.setattr(practice_service_module.practice_response_dao, 'has_pending_grading', fake_has_pending)
    monkeypatch.setattr(practice_service_module.statistics_service, 'apply_session_submission', fake_apply_submission)


def test_submit_session_notifies_study_plan(monkeypatch) -> None:
    """交卷后回调学习计划，把已答与答对题数透传给计划项"""
    session = _submitted_session()
    _patch_submit_dependencies(monkeypatch, session)

    received: dict = {}

    async def fake_hook(_db, **kwargs):
        received.update(kwargs)

    monkeypatch.setattr(
        'backend.app.study_plan.service.session_hook.handle_session_completed',
        fake_hook,
    )

    result = asyncio.run(practice_service.submit_session(db=_HookDb(), session_key='client-session-001', user_id=7))

    assert result.status == 'graded'
    assert received == {
        'session_key': 'client-session-001',
        'user_id': 7,
        'correct_count': 2,
        'total_count': 3,
    }


def test_submit_session_survives_study_plan_failure(monkeypatch) -> None:
    """学习计划同步失败不能阻断交卷主流程"""
    from sqlalchemy.exc import SQLAlchemyError

    session = _submitted_session()
    _patch_submit_dependencies(monkeypatch, session)

    async def failing_hook(_db, **_kwargs):
        raise SQLAlchemyError('study plan write failed')

    monkeypatch.setattr(
        'backend.app.study_plan.service.session_hook.handle_session_completed',
        failing_hook,
    )

    result = asyncio.run(practice_service.submit_session(db=_HookDb(), session_key='client-session-001', user_id=7))

    assert result.status == 'graded'
    assert result.submitted_time is not None
