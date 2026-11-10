"""真实 SQLite：每次错误/用时、报告幂等、旧软删题与安全撤销。"""

from collections.abc import Iterator
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import event, func, select

from backend.app.gongkao.schema.practice_log import ImportPracticeReportParam
from backend.app.question_bank_v2.crud.crud_external_practice import external_practice_dao
from backend.app.question_bank_v2.crud.crud_external_wrong import EXTERNAL_WRONG_KEY
from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.schema.review import CreateExternalWrongQuestionParam
from backend.app.question_bank_v2.service import external_practice_import_service as import_module
from backend.app.question_bank_v2.service import wrong_review_service as module
from backend.app.question_bank_v2.service.external_practice_import_service import ExternalPracticeImportService
from backend.app.question_bank_v2.service.external_wrong_service import external_wrong_service
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.app.question_bank_v2.tests.test_external_source_timing import (
    CORE,
    NOW,
    USER_ID,
    AsyncSQLiteDB,
    _practice_param,
    _seed_attempt,
    _seed_question,
    _seed_session,
    _seed_wrong_state,
    _stub_detail_reads,
)
from backend.app.question_bank_v2.utils.external_practice import EXTERNAL_PRACTICE_ORIGIN


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[AsyncSQLiteDB]:
    database = AsyncSQLiteDB()

    def assign_ids(session: Any, *_args: Any) -> None:
        for model in (QbWrongQuestionState, QbQuestionReview):
            next_id = session.scalar(select(func.coalesce(func.max(model.id), 0)))
            for obj in session.new:
                if isinstance(obj, model) and obj.id is None:
                    next_id += 1
                    obj.id = next_id

    event.listen(database.session, 'before_flush', assign_ids)
    monkeypatch.setattr(module, 'lock_practice_user', AsyncMock())
    monkeypatch.setattr(WrongReviewService, '_resolve_recorded_domain_id', AsyncMock(return_value=None))
    monkeypatch.setattr(WrongReviewService, '_fill_missing_content', AsyncMock())
    monkeypatch.setattr(WrongReviewService, '_module_path_metadata', AsyncMock(return_value={}))
    monkeypatch.setattr(WrongReviewService, '_validate_links', AsyncMock())
    monkeypatch.setattr(WrongReviewService, '_validate_assets', AsyncMock())
    monkeypatch.setattr(WrongReviewService, '_merge_knowledge_points', AsyncMock())
    monkeypatch.setattr(WrongReviewService, '_cleanup_orphan_materials', AsyncMock(return_value=0))
    _stub_detail_reads(monkeypatch)
    yield database
    database.close()


def seed_state(db: AsyncSQLiteDB, *, first_report: str = '1_1_a', source: str = '第一卷') -> QbWrongQuestionState:
    _seed_question(db)
    _seed_wrong_state(db, external_key=f'fenbi:{first_report}:123', source_question_key='123')
    state = db.session.get(QbWrongQuestionState, 1)
    state.entry_metadata = {**state.entry_metadata, 'source': source}
    state.last_wrong_response = 'B'
    state.first_wrong_time = state.last_wrong_time = NOW
    state.fsrs_data = {'stability': 7}
    db.commit()
    return state


def param(
    report: str, *, answer: str = 'B', duration: int | None = 14, known_date: bool = True
) -> CreateExternalWrongQuestionParam:
    return CreateExternalWrongQuestionParam(
        idempotency_key=f'ext-fenbi:{report}:123',
        entry_source='import',
        stem=CORE['stem'],
        options=CORE['options'],
        answer={'answer_data': {'correct': 'A'}},
        wrong_response=answer,
        source_system='fenbi',
        external_key=f'fenbi:{report}:123',
        entry_metadata={'source': '第一卷' if report == '1_1_a' else '第二卷', 'source_question_key': '123'},
        wrong_occurrence={
            'source_key': report,
            'duration_seconds': duration,
            'submitted_time': NOW + timedelta(days=1 if report != '1_1_a' else 0) if known_date else None,
        },
    )


async def capture(db: AsyncSQLiteDB, report: str, batch: str, **kwargs: Any) -> Any:
    return await WrongReviewService.capture_external_batch(
        db=db,
        user_id=USER_ID,
        items=[param(report, **kwargs)],
        import_batch_id=batch,
    )


def records(db: AsyncSQLiteDB) -> list[QbQuestionReview]:
    return list(
        db.session.scalars(
            select(QbQuestionReview).where(
                QbQuestionReview.review_data[EXTERNAL_WRONG_KEY]['source_key'].as_string().is_not(None),
                QbQuestionReview.deleted == 0,
            )
        )
    )


async def test_same_report_new_batches_do_not_increase_wrong_count(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    first = await capture(db, '1_1_a', 'batch-first')
    second = await capture(db, '1_1_a', 'batch-retry')
    assert first.succeeded == second.succeeded == 1
    assert state.wrong_count == 1 and state.review_count == 1
    assert len(records(db)) == 1
    assert db.session.scalar(select(func.count()).select_from(QbQuestionAttempt)) == 0
    assert db.session.scalar(select(func.count()).select_from(QbPracticeSession)) == 0


async def test_first_capture_creates_one_error_not_two(db: AsyncSQLiteDB, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_question(db)
    db.commit()
    monkeypatch.setattr(WrongReviewService, '_write_question_content', AsyncMock())
    monkeypatch.setattr(module.review_schedule_service, 'ensure_mastery', AsyncMock())
    result = await capture(db, '1_1_a', 'batch-a')
    assert result.succeeded == result.created == 1
    state = db.session.get(QbWrongQuestionState, result.items[0].wrong_state_id)
    assert state.wrong_count == 1 and state.review_count == 0
    assert state.source_attempt_id is None
    assert len(records(db)) == 1


@pytest.mark.parametrize('duration', [None, 0, 27])
async def test_another_report_adds_error_and_uses_its_own_duration(db: AsyncSQLiteDB, duration: int | None) -> None:
    state = seed_state(db)
    await capture(db, '1_1_a', 'batch-a')
    result = await capture(db, '1_1_b', 'batch-b', duration=duration)
    assert result.succeeded == 1 and result.reused == 1 and result.created == 0
    assert state.wrong_count == 2 and state.review_count == 1 and state.fsrs_data == {'stability': 7}
    assert state.entry_metadata['source'] == '第一卷'
    assert state.entry_metadata['external_key'] == 'fenbi:1_1_a:123'
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)
    expected = duration * 1000 if duration is not None else None
    assert detail.last_wrong_duration_ms == expected
    assert [row.source_key for row in detail.wrong_answer_history] == ['1_1_b', '1_1_a']
    assert [row.duration_ms for row in detail.wrong_answer_history] == [expected, 14000]
    assert len(records(db)) == 2 and db.session.scalar(select(func.count()).select_from(QbQuestion)) == 1


async def test_missing_actual_date_stays_unknown_not_import_time(db: AsyncSQLiteDB) -> None:
    seed_state(db)
    await capture(db, '1_1_a', 'batch-a')
    await capture(db, '1_1_b', 'batch-b', duration=None, known_date=False)
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)
    assert detail.wrong_answer_history[0].source_key == '1_1_b'
    assert detail.wrong_answer_history[0].submitted_time is None
    assert detail.last_wrong_duration_ms is None


async def test_same_report_can_supplement_unknown_but_not_overwrite_known_duration(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    await capture(db, '1_1_a', 'batch-a', duration=None)
    await capture(db, '1_1_a', 'batch-b', duration=0)
    conflict = await capture(db, '1_1_a', 'batch-c', duration=15)
    assert conflict.failed == 1 and '用时' in conflict.failures[0].reason
    assert state.wrong_count == 1 and len(records(db)) == 1
    assert records(db)[0].review_data[EXTERNAL_WRONG_KEY]['duration_ms'] == 0


async def test_same_report_conflicting_answer_rolls_back_no_new_membership(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    await capture(db, '1_1_a', 'batch-a')
    obj = param('1_1_a')
    obj.wrong_response = ['B', 'A']
    result = await WrongReviewService.capture_external_batch(
        db=db, user_id=USER_ID, items=[obj], import_batch_id='batch-failed'
    )
    assert result.failed == 1 and '答案' in result.failures[0].reason
    assert state.wrong_count == 1 and len(records(db)) == 1
    page = await WrongReviewService.get_import_batches_page(db=db, user_id=USER_ID)
    assert {row.import_batch_id for row in page.items} == {'batch-a', 'batch-1234'}


async def test_deleted_original_question_restores_real_timing_without_resurrecting_it(db: AsyncSQLiteDB) -> None:
    seed_state(db)
    _seed_question(db, question_id=2, deleted=2)
    _seed_session(db)
    _seed_attempt(
        db,
        attempt_id=101,
        question_id=2,
        duration_ms=14000,
        response_data='B',
        session_id=10,
        session_item_id=1,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    db.commit()
    # 写入匹配仍不复用已删除题，详情读取才允许检查历史来源。
    active = await external_practice_dao.find_source_questions(
        db, user_id=USER_ID, platform='fenbi', source_question_key='123', core=CORE
    )
    assert [row.id for row in active] == [1]
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)
    assert detail.last_wrong_duration_ms == 14000 and detail.wrong_answer_history[0].attempt_id == 101
    assert db.session.get(QbQuestion, 2).deleted == 2
    assert db.session.get(QbQuestionAttempt, 101).question_id == 2


@pytest.mark.parametrize('reference', ['attempt', 'session_item', 'external_error'])
async def test_undo_does_not_delete_question_referenced_by_practice_or_error(db: AsyncSQLiteDB, reference: str) -> None:
    state = seed_state(db)
    if reference == 'attempt':
        _seed_attempt(db, attempt_id=101, duration_ms=14000)
    elif reference == 'session_item':
        db.session.execute(
            QbPracticeSessionItem.__table__.insert().values(
                id=101, session_id=10, question_id=1, position=0, display_config={}, created_time=NOW
            )
        )
    else:
        await capture(db, '1_1_a', 'batch-delete')
    state.entry_metadata = {**state.entry_metadata, 'import_batch_id': 'batch-delete'}
    db.commit()
    result = await WrongReviewService.undo_import_batch(db=db, user_id=USER_ID, import_batch_id='batch-delete')
    assert result.deleted_questions == 0
    assert db.session.get(QbQuestion, 1).deleted == 0
    assert state.deleted == state.id
    assert module.WrongReviewService._cleanup_orphan_materials.call_args.kwargs['question_ids'] == []
    if reference == 'external_error':
        assert len(records(db)) == 1


def add_archived_error(
    db: AsyncSQLiteDB, *, report: str = '1_1_a', session_id: int = 10, qid: int = 1, duration: int | None = 14
) -> None:
    _seed_session(db, session_id=session_id)
    session = db.session.get(QbPracticeSession, session_id)
    session.title_snapshot = '第一卷' if report == '1_1_a' else '第二卷'
    session.source_snapshot = {**session.source_snapshot, 'source_key': report}
    _seed_attempt(
        db,
        attempt_id=session_id * 10,
        question_id=qid,
        duration_ms=duration * 1000 if duration is not None else None,
        response_data='B',
        submitted_time=NOW + timedelta(days=1 if report != '1_1_a' else 0),
        session_id=session_id,
        session_item_id=session_id,
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '123'},
    )
    db.commit()


@pytest.mark.parametrize('record_first', [True, False])
async def test_two_import_orders_count_once_and_prefer_real_attempt(db: AsyncSQLiteDB, *, record_first: bool) -> None:
    state = seed_state(db)
    if record_first:
        add_archived_error(db)
    await capture(db, '1_1_a', 'batch-a')
    if not record_first:
        add_archived_error(db)
        await external_wrong_service.sync_report_question(
            db, user_id=USER_ID, platform='fenbi', data=_practice_param(duration_seconds=14)
        )
    assert state.wrong_count == 1 and len(records(db)) == 1
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)
    assert len(detail.wrong_answer_history) == 1
    assert detail.wrong_answer_history[0].attempt_id == 100 and detail.last_wrong_duration_ms == 14000
    assert db.session.scalar(select(func.count()).select_from(QbQuestionAttempt)) == 1


async def test_archived_again_error_updates_count_without_auto_adding_other_wrong_questions(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    add_archived_error(db)
    add_archived_error(db, report='1_1_b', session_id=11, duration=None)
    for _ in range(2):
        await external_wrong_service.sync_report_question(
            db, user_id=USER_ID, platform='fenbi', data=_practice_param(duration_seconds=None)
        )
    assert state.wrong_count == 2 and len(records(db)) == 2
    assert db.session.scalar(select(func.count()).select_from(QbWrongQuestionState)) == 1
    assert state.source_attempt_id == 110


async def test_initial_legacy_error_of_another_paper_is_not_absorbed_by_new_report(db: AsyncSQLiteDB) -> None:
    state = seed_state(db, first_report='legacy', source='国考第九季')
    add_archived_error(db, report='1_1_b')
    await external_wrong_service.sync_report_question(
        db, user_id=USER_ID, platform='fenbi', data=_practice_param(duration_seconds=14)
    )
    assert state.wrong_count == 2


async def test_recreated_question_does_not_link_foreign_question_attempt_fk(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    _seed_question(db, question_id=2, deleted=2)
    add_archived_error(db, qid=2)
    await external_wrong_service.sync_report_question(
        db, user_id=USER_ID, platform='fenbi', data=_practice_param(duration_seconds=14)
    )
    assert state.wrong_count == 1 and state.source_attempt_id is None
    assert records(db)[0].source_attempt_id is None
    assert records(db)[0].review_data[EXTERNAL_WRONG_KEY]['attempt_id'] == 100


async def test_event_history_is_isolated_from_another_user(db: AsyncSQLiteDB) -> None:
    seed_state(db)
    await capture(db, '1_1_a', 'batch-a')
    history = await external_wrong_service.merge_history(db, user_id=8, question_ids=[1], history=[])
    assert history == []


def test_correct_answer_and_empty_report_are_not_real_error_occurrences() -> None:
    with pytest.raises(ValueError, match='答对'):
        param('1_1_a', answer='A')
    with pytest.raises(ValueError, match='报告'):
        param(' ')


async def test_same_title_different_report_is_not_absorbed_as_legacy_initial_error(db: AsyncSQLiteDB) -> None:
    state = seed_state(db, first_report='legacy', source='第一卷')
    add_archived_error(db, report='1_1_b')
    session = db.session.get(QbPracticeSession, 10)
    session.title_snapshot = '第一卷'
    db.session.get(QbQuestionAttempt, 100).created_time = NOW + timedelta(days=2)
    db.commit()
    await external_wrong_service.sync_report_question(
        db, user_id=USER_ID, platform='fenbi', data=_practice_param(duration_seconds=14)
    )
    assert state.wrong_count == 2


async def test_reimporting_older_report_does_not_reset_latest_error_time(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    await capture(db, '1_1_a', 'batch-a')
    await capture(db, '1_1_b', 'batch-b', duration=0)
    await capture(db, '1_1_a', 'batch-a-retry')
    assert state.wrong_count == 2 and state.last_wrong_time == NOW + timedelta(days=1)
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)
    assert detail.last_wrong_duration_ms == 0


async def test_same_report_has_separate_errors_for_different_source_question_keys(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    add_archived_error(db)
    _seed_attempt(
        db,
        attempt_id=101,
        duration_ms=16000,
        response_data='B',
        session_id=10,
        session_item_id=11,
        submitted_time=NOW + timedelta(minutes=5),
        grading_result={'origin': EXTERNAL_PRACTICE_ORIGIN, 'source_question_key': '456'},
    )
    db.commit()
    await external_wrong_service.sync_report_question(
        db, user_id=USER_ID, platform='fenbi', data=_practice_param(duration_seconds=14)
    )
    assert state.wrong_count == 2 and len(records(db)) == 2
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)
    assert [row.source_question_key for row in detail.wrong_answer_history] == ['456', '123']


async def test_recreated_state_recovers_retained_external_error_history(
    db: AsyncSQLiteDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = seed_state(db)
    await capture(db, '1_1_a', 'batch-a')
    await WrongReviewService._soft_delete_wrong_states(
        db=db, user_id=USER_ID, state_rows=[(state.id, state.question_id)]
    )
    monkeypatch.setattr(WrongReviewService, '_write_question_content', AsyncMock())
    monkeypatch.setattr(module.review_schedule_service, 'ensure_mastery', AsyncMock())
    monkeypatch.setattr(module.preference_service, 'get', AsyncMock(return_value=SimpleNamespace(mastery_threshold=3)))
    result = await capture(db, '1_1_b', 'batch-b')
    assert result.succeeded == 1
    new_state = db.session.get(QbWrongQuestionState, result.items[0].wrong_state_id)
    assert new_state.wrong_count == 2
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=new_state.id)
    assert len(detail.wrong_answer_history) == 2


async def test_external_error_does_not_replace_native_first_source(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    state.entry_source = 'attempt'
    state.entry_metadata = {'source': '原练习'}
    db.commit()
    result = await capture(db, '1_1_b', 'batch-b')
    assert result.succeeded == 1 and state.wrong_count == 2 and state.entry_source == 'attempt'
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=state.id)
    assert detail.wrong_answer_history[0].source_key == '1_1_b'


async def test_only_same_report_same_answer_can_supply_missing_duration(db: AsyncSQLiteDB) -> None:
    seed_state(db)
    await capture(db, '1_1_a', 'batch-a', duration=14)
    add_archived_error(db, duration=None)
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)
    assert len(detail.wrong_answer_history) == 1 and detail.last_wrong_duration_ms == 14000
    add_archived_error(db, report='1_1_b', session_id=11, duration=None)
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=1)
    assert detail.last_wrong_duration_ms is None


async def test_again_wrong_after_resolution_reopens_without_resetting_reviews_or_memory(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    state.status = 'resolved'
    state.resolved_time = NOW + timedelta(hours=1)
    state.last_reviewed_time = NOW
    state.correct_streak = 3
    db.commit()
    await capture(db, '1_1_b', 'batch-b')
    assert state.status == 'active' and state.correct_streak == 0
    assert state.review_count == 1 and state.fsrs_data == {'stability': 7}


async def test_unchanged_full_report_import_repairs_recreated_wrong_state_once(
    db: AsyncSQLiteDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = seed_state(db)
    _seed_question(db, question_id=2, deleted=2)
    add_archived_error(db, qid=2)
    data = _practice_param(duration_seconds=14)
    modules = [
        {
            'module_name': data.module_path[0],
            'total_questions': 1,
            'correct_count': 0,
            'duration_seconds': 14,
        }
    ]
    obj = ImportPracticeReportParam(
        source_key='1_1_a',
        source_url='https://spa.fenbi.com/ti/exam/solution/1_1_a',
        material_type='exam',
        material_title='第一卷',
        total_questions=1,
        correct_count=0,
        unanswered_count=0,
        duration_seconds=14,
        practiced_at=NOW.date(),
        modules=modules,
        questions=[data],
    )
    session = db.session.get(QbPracticeSession, 10)
    session.source_snapshot = {**session.source_snapshot, 'summary': obj.model_dump(mode='json', exclude={'questions'})}
    item = QbPracticeSessionItem(
        session_id=10, question_id=2, position=0, display_config={'external_practice': data.model_dump(mode='json')}
    )
    item.id = 10
    db.add(item)
    db.commit()
    monkeypatch.setattr(import_module, 'lock_practice_user', AsyncMock())
    log = SimpleNamespace(id=10, user_id=USER_ID, source_platform='fenbi', source_key='1_1_a', practiced_at=NOW.date())
    for _ in range(2):
        result = await ExternalPracticeImportService.import_questions(db=db, log=log, obj=obj)
        assert result.added_questions == result.supplemented_questions == 0
    assert state.wrong_count == 1 and len(records(db)) == 1
    assert db.session.scalar(select(func.count()).select_from(QbQuestionAttempt)) == 1


async def test_original_legacy_answer_is_preserved_before_latest_answer_overwrites_state(db: AsyncSQLiteDB) -> None:
    state = seed_state(db, first_report='legacy', source='国考第九季')
    original = {'selected': ['B'], 'note': '第一次错选快照'}
    state.last_wrong_response = original
    db.commit()
    await capture(db, '1_1_b', 'batch-b', duration=0)
    await capture(db, '1_1_b', 'batch-b-retry', duration=0)
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=state.id)
    assert state.wrong_count == 2 and state.last_wrong_response == 'B'
    assert detail.last_wrong_duration_ms == 0
    assert len(detail.wrong_answer_history) == 2
    initial = detail.wrong_answer_history[-1]
    assert initial.answer == original and initial.source == '国考第九季'
    assert initial.source_key is initial.submitted_time is initial.duration_ms is None


async def test_known_initial_report_snapshot_is_superseded_not_duplicated_when_archived(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    await capture(db, '1_1_b', 'batch-b')
    before = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=state.id)
    assert before.wrong_answer_history[-1].source_key == '1_1_a'
    assert before.wrong_answer_history[-1].submitted_time is None
    add_archived_error(db)
    await external_wrong_service.sync_report_question(
        db, user_id=USER_ID, platform='fenbi', data=_practice_param(duration_seconds=14)
    )
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=state.id)
    assert state.wrong_count == 2 and len(detail.wrong_answer_history) == 2
    assert detail.wrong_answer_history[-1].attempt_id == 100


async def test_unresolved_initial_snapshot_survives_undo_and_counts_once_on_recreation(
    db: AsyncSQLiteDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = seed_state(db, first_report='legacy', source='国考第九季')
    await capture(db, '1_1_b', 'batch-b')
    await WrongReviewService._soft_delete_wrong_states(
        db=db, user_id=USER_ID, state_rows=[(state.id, state.question_id)]
    )
    monkeypatch.setattr(WrongReviewService, '_write_question_content', AsyncMock())
    monkeypatch.setattr(module.review_schedule_service, 'ensure_mastery', AsyncMock())
    monkeypatch.setattr(module.preference_service, 'get', AsyncMock(return_value=SimpleNamespace(mastery_threshold=3)))
    result = await capture(db, '1_1_c', 'batch-c')
    new_state = db.session.get(QbWrongQuestionState, result.items[0].wrong_state_id)
    await capture(db, '1_1_c', 'batch-c-retry')
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=new_state.id)
    assert new_state.wrong_count == 3 and len(detail.wrong_answer_history) == 3
    assert detail.wrong_answer_history[-1].source == '国考第九季'


async def test_new_report_does_not_fabricate_missing_initial_answer(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    state.last_wrong_response = None
    db.commit()
    await capture(db, '1_1_b', 'batch-b')
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=state.id)
    assert state.wrong_count == 2 and state.last_wrong_response == 'B'
    assert [item.source_key for item in detail.wrong_answer_history] == ['1_1_b']


async def test_retained_initial_report_matches_later_capture_without_double_counting(
    db: AsyncSQLiteDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = seed_state(db)
    await capture(db, '1_1_b', 'batch-b')
    await WrongReviewService._soft_delete_wrong_states(
        db=db, user_id=USER_ID, state_rows=[(state.id, state.question_id)]
    )
    monkeypatch.setattr(WrongReviewService, '_write_question_content', AsyncMock())
    monkeypatch.setattr(module.review_schedule_service, 'ensure_mastery', AsyncMock())
    monkeypatch.setattr(module.preference_service, 'get', AsyncMock(return_value=SimpleNamespace(mastery_threshold=3)))
    result = await capture(db, '1_1_c', 'batch-c')
    new_state = db.session.get(QbWrongQuestionState, result.items[0].wrong_state_id)
    assert new_state.wrong_count == 3
    await capture(db, '1_1_a', 'batch-a')
    await capture(db, '1_1_a', 'batch-a-retry')
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=new_state.id)
    assert new_state.wrong_count == 3 and len(detail.wrong_answer_history) == 3
    assert {item.source_key for item in detail.wrong_answer_history} == {'1_1_a', '1_1_b', '1_1_c'}
    assert all(item.submitted_time is not None for item in detail.wrong_answer_history)


async def test_unknown_date_does_not_reopen_resolved_state_or_borrow_initial_timing(db: AsyncSQLiteDB) -> None:
    state = seed_state(db)
    state.status = 'resolved'
    state.resolved_time = NOW
    state.correct_streak = 3
    db.commit()
    await capture(db, '1_1_b', 'batch-b', duration=None, known_date=False)
    detail = await WrongReviewService.get_detail(db=db, user_id=USER_ID, wrong_state_id=state.id)
    assert state.status == 'resolved' and state.resolved_time == NOW and state.correct_streak == 3
    assert state.wrong_count == 2 and detail.wrong_answer_history[0].source_key == '1_1_b'
    assert detail.wrong_answer_history[0].submitted_time is None and detail.last_wrong_duration_ms is None
    assert detail.wrong_answer_history[-1].source_key == '1_1_a'
