from collections.abc import Iterator
from copy import deepcopy
from datetime import timedelta
from typing import Any

import pytest

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.question_bank_v2.crud.crud_practice import practice_session_item_dao
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.app.question_bank_v2.tests.test_recall_notifications import (
    _SyncSessionAsAsync,
    _init_sqlite_engine,
    _make_question,
    _make_state,
)
from backend.utils.timezone import timezone


def test_whole_recall_paper_groups_chapters_and_numbers_without_mutating_facts() -> None:
    items = [
        {'question_id': 1, 'position': 0, 'section_name': '常识判断', 'section_id': 10},
        {'question_id': 2, 'position': 3, 'section_name': '言语理解'},
        {'question_id': 3, 'position': 5, 'section_name': ' 常识判断 ', 'section_id': 20, 'response_data': 'A'},
        {'question_id': 4, 'position': 7, 'section_name': None},
        {'question_id': 5, 'position': 9, 'section_name': '言语理解'},
        {'question_id': 6, 'position': 11, 'section_name': ''},
    ]
    original = deepcopy(items)
    ordered = practice_service._order_recall_items(list(reversed(items)))
    assert [item['question_id'] for item in ordered] == [1, 3, 2, 5, 4, 6]
    assert [item['section_name'] for item in ordered] == ['常识判断'] * 2 + ['言语理解'] * 2 + [''] * 2
    assert [item['position'] for item in ordered] == list(range(6))
    assert ordered[1]['section_id'] == 20
    assert ordered[1]['response_data'] == 'A'
    assert items == original
    assert practice_service._order_recall_items(ordered) == ordered
    assert practice_service._order_recall_items([]) == []


def test_192_question_paper_keeps_all_questions_once_and_in_chapter_order() -> None:
    names = ['常识判断', '言语理解', '数量关系', '资料分析']
    items = [{'question_id': index + 1, 'position': index, 'section_name': names[index % 4]} for index in range(192)]
    ordered = practice_service._order_recall_items(items)
    assert len(ordered) == 192
    assert {item['question_id'] for item in ordered} == set(range(1, 193))
    assert [item['position'] for item in ordered] == list(range(192))
    for chapter, name in enumerate(names):
        group = ordered[chapter * 48 : (chapter + 1) * 48]
        assert {item['section_name'] for item in group} == {name}
        assert [item['question_id'] for item in group] == list(range(chapter + 1, 193, 4))


@pytest.fixture
def paper_db() -> Iterator[tuple[Session, _SyncSessionAsAsync, Any]]:
    engine = _init_sqlite_engine()
    with Session(engine) as session:
        now = timezone.now()
        paper = QbPracticeSession(
            session_key='recall-message-order',
            user_id=1,
            status='in_progress',
            total_items=8,
            answered_items=1,
            delivery_config={'recall_message_id': 42, 'recall_due_before': now.isoformat()},
        )
        paper.id = 10
        session.add(paper)
        names = ['常识判断', '言语理解', '常识判断', '数量关系', '常识判断', None, '言语理解', '数量关系']
        for qid, name in enumerate(names, start=1):
            question = _make_question(qid, f'order-{qid}', f'题干{qid}')
            state = _make_state(qid, 1, qid, next_practice_time=now - timedelta(days=1))
            state.entry_metadata = {'section_name': name}
            if qid == 7:
                state.status = 'suspended'
            if qid == 8:
                state.review_count = 0
            if qid == 3:
                # 已答题虽然推进排期，仍须保留在本卷；读取不能改写记忆状态。
                state.next_practice_time = now + timedelta(days=3)
                state.fsrs_data = {'last_attempt_id': 30}
            item = QbPracticeSessionItem(session_id=10, question_id=qid, position=(qid - 1) * 2)
            item.id = 100 + qid
            session.add_all([question, state, item])
        response = QbPracticeSessionResponse(
            session_id=10,
            session_item_id=103,
            response_data='A',
            status='submitted',
            is_correct=True,
            duration_ms=1500,
        )
        response.id = 20
        attempt = QbQuestionAttempt(
            user_id=1,
            question_id=3,
            session_id=10,
            session_item_id=103,
            attempt_no=1,
            response_data='A',
            is_correct=True,
            grading_status='graded',
            submitted_time=now - timedelta(minutes=5),
        )
        attempt.id = 30
        session.add_all([response, attempt])
        session.commit()
        yield session, _SyncSessionAsAsync(session), now
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('closed', [False, True])
async def test_existing_recall_delivery_and_report_share_sequence_without_rewriting_database(
    paper_db: tuple[Session, _SyncSessionAsAsync, Any], *, closed: bool
) -> None:
    session, db, _ = paper_db
    paper = session.get(QbPracticeSession, 10)
    assert paper is not None
    if closed:
        paper.status = 'graded'
        session.commit()
    raw = await practice_session_item_dao.get_all(db, 10)
    detail = await practice_service.get(db=db, session_key=paper.session_key, user_id=1)
    report = await practice_service.get_report(db=db, session_key=paper.session_key, user_id=1)
    expected_ids = [1, 3, 5, 2, 4, 6]
    assert [item.question_id for item in detail.items] == expected_ids
    assert [item.question_id for item in report.items] == expected_ids
    assert [item.position for item in detail.items] == list(range(6))
    assert [item.position for item in report.items] == list(range(6))
    assert detail.total_items == report.total_items == 6
    assert detail.answered_items == report.answered_items == 1
    assert detail.items[1].id == report.items[1].session_item_id == 103
    assert detail.items[1].response_data == 'A'
    assert report.items[1].status == 'correct'
    assert report.items[1].duration_ms == 1500
    assert await practice_session_item_dao.get_all(db, 10) == raw
    attempt = session.get(QbQuestionAttempt, 30)
    assert attempt is not None and attempt.response_data == 'A' and attempt.session_item_id == 103
    # 读序列没有产生提交／评分／排期写入。
    assert len(session.scalars(select(QbQuestionAttempt)).all()) == 1
    assert not session.dirty


@pytest.mark.asyncio
async def test_cross_day_append_regroups_whole_delivery_while_preserving_existing_response(
    paper_db: tuple[Session, _SyncSessionAsAsync, Any],
) -> None:
    session, db, now = paper_db
    question = _make_question(9, 'order-9', '新到期题')
    state = _make_state(9, 1, 9, next_practice_time=now - timedelta(hours=1))
    state.entry_metadata = {'section_name': '常识判断'}
    item = QbPracticeSessionItem(session_id=10, question_id=9, position=16)
    item.id = 109
    session.add_all([question, state, item])
    session.commit()
    detail = await practice_service.get(db=db, session_key='recall-message-order', user_id=1)
    assert [item.question_id for item in detail.items] == [1, 3, 5, 9, 2, 4, 6]
    assert [item.position for item in detail.items] == list(range(7))
    assert detail.items[1].response_data == 'A'
    assert session.get(QbPracticeSessionItem, 103).position == 4
    assert session.get(QbPracticeSessionItem, 109).position == 16
    # 重复读取不再拆章节，也不重复补题。
    again = await practice_service.get(db=db, session_key='recall-message-order', user_id=1)
    assert [(item.id, item.position) for item in again.items] == [(item.id, item.position) for item in detail.items]
    assert session.get(type(state), 3).fsrs_data == {'last_attempt_id': 30}


@pytest.mark.asyncio
async def test_non_recall_paper_keeps_original_chapter_order_and_positions(
    paper_db: tuple[Session, _SyncSessionAsAsync, Any],
) -> None:
    session, db, _ = paper_db
    paper = session.get(QbPracticeSession, 10)
    assert paper is not None
    paper.delivery_config = {}
    session.commit()
    detail = await practice_service.get(db=db, session_key=paper.session_key, user_id=1)
    report = await practice_service.get_report(db=db, session_key=paper.session_key, user_id=1)
    assert [item.question_id for item in detail.items] == list(range(1, 9))
    assert [item.position for item in detail.items] == list(range(0, 16, 2))
    assert [item.position for item in report.items] == list(range(0, 16, 2))
