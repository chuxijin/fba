from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from backend.app.question_bank_v2.service.practice_schedule_service import schedule
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.common.exception import errors

if TYPE_CHECKING:
    from backend.app.question_bank_v2.schema.practice import GetPracticeSolutionDetail


@pytest.mark.asyncio
async def test_confirm_memory_feedback_not_recall() -> None:
    """非 recall 会话拒绝调用 confirm_memory_feedback (RequestError)"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, user_id=10, delivery_config={})
    item = SimpleNamespace(id=2, question_id=101)

    with patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, item))):
        with pytest.raises(errors.RequestError, match='仅独立回测支持记忆反馈'):
            await PracticeService.confirm_memory_feedback(
                db=db, session_key='regular-session', user_id=10, session_item_id=2, rating=3
            )


@pytest.mark.asyncio
async def test_confirm_memory_feedback_no_valid_grading_receipt() -> None:
    """未判分或没有有效 _memory 回执拒绝 (ConflictError)"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, user_id=10, delivery_config={'recall_message_id': 888})
    item = SimpleNamespace(id=2, question_id=101)
    attempt = SimpleNamespace(id=1001, is_correct=True, grading_result={})
    db.scalar.return_value = attempt

    lock_q = 'backend.app.question_bank_v2.service.attempt_projection_service.attempt_projection_service.lock_questions'
    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, item))),
        patch(lock_q, new=AsyncMock()),
    ):
        with pytest.raises(errors.ConflictError, match='本题尚未获得有效判分反馈'):
            await PracticeService.confirm_memory_feedback(
                db=db, session_key='recall-sess', user_id=10, session_item_id=2, rating=3
            )


@pytest.mark.asyncio
async def test_confirm_memory_feedback_wrong_cannot_upgrade() -> None:
    """答错题只能记为 Again (1)，不可升 2/3/4 (RequestError)"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, user_id=10, delivery_config={'recall_message_id': 888})
    item = SimpleNamespace(id=2, question_id=101)
    attempt = SimpleNamespace(
        id=1001,
        is_correct=False,
        grading_result={'_memory': {'rating': 1, 'before': {}, 'due': '2026-11-03T00:00:00+00:00'}},
    )
    db.scalar.return_value = attempt

    lock_q = 'backend.app.question_bank_v2.service.attempt_projection_service.attempt_projection_service.lock_questions'
    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, item))),
        patch(lock_q, new=AsyncMock()),
    ):
        for r in (2, 3, 4):
            with pytest.raises(errors.RequestError, match='没有成功回忆只能记为“没想起来”'):
                await PracticeService.confirm_memory_feedback(
                    db=db, session_key='recall-sess', user_id=10, session_item_id=2, rating=r
                )


@pytest.mark.asyncio
async def test_confirm_memory_feedback_correct_allows_1_2_3_4() -> None:
    """正确默认 Good (3)，支持一次确认 1/2/3/4，且从 before 快照执行真实 FSRS 重算"""
    now = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)
    lock_q = 'backend.app.question_bank_v2.service.attempt_projection_service.attempt_projection_service.lock_questions'
    dao_q = 'backend.app.question_bank_v2.crud.crud_review.wrong_question_state_dao.get_by_question'
    for target_rating in (1, 2, 3, 4):
        db = AsyncMock()
        session = SimpleNamespace(id=1, user_id=10, delivery_config={'recall_message_id': 888})
        item = SimpleNamespace(id=2, question_id=101)
        initial_before = {'stability': 2.0, 'difficulty': 5.0, 'state': 1, 'reps': 1}
        attempt = SimpleNamespace(
            id=1001,
            is_correct=True,
            submitted_time=now,
            grading_result={
                '_memory': {
                    'rating': 3,
                    'before': dict(initial_before),
                    'due': '2026-11-05T12:00:00+00:00',
                    'confirmed': False,
                }
            },
        )
        db.scalar.return_value = attempt

        state = SimpleNamespace(
            id=50,
            status='active',
            fsrs_data={'last_attempt_id': 1001},
            next_practice_time=None,
            last_rating=3,
        )

        with (
            patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, item))),
            patch(lock_q, new=AsyncMock()),
            patch(dao_q, new=AsyncMock(return_value=state)),
        ):
            res = await PracticeService.confirm_memory_feedback(
                db=db, session_key='recall-sess', user_id=10, session_item_id=2, rating=target_rating
            )

        assert res['rating'] == target_rating
        assert res['confirmed'] is True

        expected_after, expected_due = schedule(initial_before, rating=target_rating, now=now)
        assert res['due'] == expected_due.isoformat()
        assert state.fsrs_data['stability'] == expected_after['stability']
        assert state.fsrs_data['difficulty'] == expected_after['difficulty']
        assert state.fsrs_data['last_attempt_id'] == 1001
        assert state.next_practice_time == expected_due
        assert state.last_rating == target_rating
        assert attempt.grading_result['_memory']['confirmed'] is True
        assert db.flush.called


@pytest.mark.asyncio
async def test_confirm_memory_feedback_same_rating_idempotent() -> None:
    """已确认后再次以相同 feedback 调用应幂等返回，不抛异常"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, user_id=10, delivery_config={'recall_message_id': 888})
    item = SimpleNamespace(id=2, question_id=101)
    attempt = SimpleNamespace(
        id=1001,
        is_correct=True,
        grading_result={
            '_memory': {
                'rating': 4,
                'due': '2026-11-10T12:00:00+00:00',
                'confirmed': True,
            }
        },
    )
    db.scalar.return_value = attempt

    lock_q = 'backend.app.question_bank_v2.service.attempt_projection_service.attempt_projection_service.lock_questions'
    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, item))),
        patch(lock_q, new=AsyncMock()),
    ):
        res = await PracticeService.confirm_memory_feedback(
            db=db, session_key='recall-sess', user_id=10, session_item_id=2, rating=4
        )

    assert res == {'rating': 4, 'due': '2026-11-10T12:00:00+00:00', 'confirmed': True}


@pytest.mark.asyncio
async def test_confirm_memory_feedback_different_rating_conflict() -> None:
    """已确认后以不同 feedback 调用被拒绝 (ConflictError)"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, user_id=10, delivery_config={'recall_message_id': 888})
    item = SimpleNamespace(id=2, question_id=101)
    attempt = SimpleNamespace(
        id=1001,
        is_correct=True,
        grading_result={
            '_memory': {
                'rating': 4,
                'due': '2026-11-10T12:00:00+00:00',
                'confirmed': True,
            }
        },
    )
    db.scalar.return_value = attempt

    lock_q = 'backend.app.question_bank_v2.service.attempt_projection_service.attempt_projection_service.lock_questions'
    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, item))),
        patch(lock_q, new=AsyncMock()),
    ):
        with pytest.raises(errors.ConflictError, match='本次反馈已确认，不能重复修改'):
            await PracticeService.confirm_memory_feedback(
                db=db, session_key='recall-sess', user_id=10, session_item_id=2, rating=2
            )


@pytest.mark.asyncio
async def test_confirm_memory_feedback_later_attempt_updated_conflict() -> None:
    """后来的作答已更新 state (last_attempt_id 不匹配或 state 处于 suspended) 拒绝 (ConflictError)"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, user_id=10, delivery_config={'recall_message_id': 888})
    item = SimpleNamespace(id=2, question_id=101)
    attempt = SimpleNamespace(
        id=1001,
        is_correct=True,
        submitted_time=datetime(2026, 11, 2, 12, 0, tzinfo=UTC),
        grading_result={
            '_memory': {
                'rating': 3,
                'before': {},
                'due': '2026-11-05T12:00:00+00:00',
                'confirmed': False,
            }
        },
    )
    db.scalar.return_value = attempt

    state_newer = SimpleNamespace(
        id=50,
        status='active',
        fsrs_data={'last_attempt_id': 1002},
    )

    lock_q = 'backend.app.question_bank_v2.service.attempt_projection_service.attempt_projection_service.lock_questions'
    dao_q = 'backend.app.question_bank_v2.crud.crud_review.wrong_question_state_dao.get_by_question'
    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, item))),
        patch(lock_q, new=AsyncMock()),
        patch(dao_q, new=AsyncMock(return_value=state_newer)),
    ):
        with pytest.raises(errors.ConflictError, match='该题已有更新的回测或已暂停'):
            await PracticeService.confirm_memory_feedback(
                db=db, session_key='recall-sess', user_id=10, session_item_id=2, rating=4
            )

    state_suspended = SimpleNamespace(
        id=50,
        status='suspended',
        fsrs_data={'last_attempt_id': 1001},
    )

    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, item))),
        patch(lock_q, new=AsyncMock()),
        patch(dao_q, new=AsyncMock(return_value=state_suspended)),
    ):
        with pytest.raises(errors.ConflictError, match='该题已有更新的回测或已暂停'):
            await PracticeService.confirm_memory_feedback(
                db=db, session_key='recall-sess', user_id=10, session_item_id=2, rating=4
            )


@pytest.mark.asyncio
async def test_get_solution_unsubmitted_recall_forbidden() -> None:
    """get_solution 回测未提交禁止查看解析 (ForbiddenError)"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, mode='practice', delivery_config={'recall_message_id': 888})
    session_item = SimpleNamespace(id=2, question_id=101, display_config={'review_thought': 'test note'})

    resp_dao = 'backend.app.question_bank_v2.service.practice_service.practice_response_dao.get'
    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, session_item))),
        patch(resp_dao, new=AsyncMock(return_value=None)),
    ):
        with pytest.raises(errors.ForbiddenError, match='独立提交本题后才可查看答案与原复盘'):
            await PracticeService.get_solution(db=db, session_key='recall-sess', user_id=10, session_item_id=2)

    response_draft = SimpleNamespace(status='draft')
    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, session_item))),
        patch(resp_dao, new=AsyncMock(return_value=response_draft)),
    ):
        with pytest.raises(errors.ForbiddenError, match='独立提交本题后才可查看答案与原复盘'):
            await PracticeService.get_solution(db=db, session_key='recall-sess', user_id=10, session_item_id=2)


@pytest.mark.asyncio
async def test_get_solution_regular_practice_unchanged() -> None:
    """普通 practice 会话原规则不变：未提交在 practice 模式下允许直接查看解析（无 recall 时）"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, mode='practice', delivery_config={})
    session_item = SimpleNamespace(id=2, question_id=101, display_config={'custom_prop': 123})
    answer = SimpleNamespace(answer_data={'answer': 'A'}, grading_method='exact', grading_config={})
    explanation = SimpleNamespace(content='解析内容', explanation_type='official', is_default=True, status='published')

    resp_dao = 'backend.app.question_bank_v2.service.practice_service.practice_response_dao.get'
    ans_dao = 'backend.app.question_bank_v2.service.practice_service.question_answer_dao.get_by_question'
    exp_dao = 'backend.app.question_bank_v2.service.practice_service.question_explanation_dao.get_all'
    stats_svc = 'backend.app.question_bank_v2.service.practice_service.statistics_service.question_snapshot'

    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, session_item))),
        patch(resp_dao, new=AsyncMock(return_value=None)),
        patch(ans_dao, new=AsyncMock(return_value=answer)),
        patch(exp_dao, new=AsyncMock(return_value=[explanation])),
        patch(stats_svc, new=AsyncMock(return_value={})),
    ):
        res: GetPracticeSolutionDetail = await PracticeService.get_solution(
            db=db, session_key='reg-sess', user_id=10, session_item_id=2
        )

    assert res.question_id == 101
    assert res.answer_data == {'answer': 'A'}
    assert res.memory_feedback is None
    assert res.review_archive is None


@pytest.mark.asyncio
async def test_get_solution_recall_submitted_includes_archive_and_memory_without_before() -> None:
    """回测提交后查看解析：带 review_archive 和 memory_feedback，且 memory_feedback 严格过滤不暴露 before 快照"""
    db = AsyncMock()
    session = SimpleNamespace(id=1, mode='practice', delivery_config={'recall_message_id': 888})
    session_item = SimpleNamespace(id=2, question_id=101, display_config={'review_thought': '当时看错了题干'})
    response = SimpleNamespace(status='submitted')
    answer = SimpleNamespace(answer_data={'answer': 'B'}, grading_method='exact', grading_config={})
    explanation = SimpleNamespace(content='标准解析', explanation_type='official', is_default=True, status='published')

    attempt = SimpleNamespace(
        id=1001,
        grading_result={
            '_memory': {
                'rating': 3,
                'due': '2026-11-05T12:00:00+00:00',
                'confirmed': False,
                'before': {'secret_fsrs': 123},
                'other_internal': 'hide_me',
            }
        },
    )
    db.scalar.return_value = attempt

    resp_dao = 'backend.app.question_bank_v2.service.practice_service.practice_response_dao.get'
    ans_dao = 'backend.app.question_bank_v2.service.practice_service.question_answer_dao.get_by_question'
    exp_dao = 'backend.app.question_bank_v2.service.practice_service.question_explanation_dao.get_all'
    stats_svc = 'backend.app.question_bank_v2.service.practice_service.statistics_service.question_snapshot'

    with (
        patch.object(PracticeService, '_get_owned_item', new=AsyncMock(return_value=(session, session_item))),
        patch(resp_dao, new=AsyncMock(return_value=response)),
        patch(ans_dao, new=AsyncMock(return_value=answer)),
        patch(exp_dao, new=AsyncMock(return_value=[explanation])),
        patch(stats_svc, new=AsyncMock(return_value={})),
    ):
        res: GetPracticeSolutionDetail = await PracticeService.get_solution(
            db=db, session_key='recall-sess', user_id=10, session_item_id=2
        )

    assert res.question_id == 101
    assert res.review_archive == {'review_thought': '当时看错了题干'}
    assert res.memory_feedback == {
        'rating': 3,
        'due': '2026-11-05T12:00:00+00:00',
        'confirmed': False,
    }
    assert 'before' not in res.memory_feedback
