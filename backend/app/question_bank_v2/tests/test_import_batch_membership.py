"""真实内存 SQLite：跨卷复用、批次分页及撤销不丢原错题。"""

from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from backend.app.question_bank_v2.crud.crud_import_batch import wrong_import_batch_dao
from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.schema.review import (
    BatchImportItemResult,
    CreateExternalWrongQuestionParam,
    WrongQuestionFilters,
)
from backend.app.question_bank_v2.service import wrong_review_service as module
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.common.exception import errors
from backend.common.model import Base


class MemoryDB:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.next_id = 1

    async def execute(self, stmt: Any) -> Any:
        return self.session.execute(stmt)

    async def scalars(self, stmt: Any) -> Any:
        return self.session.scalars(stmt)

    def get_bind(self) -> Any:
        return self.session.get_bind()

    def add(self, obj: Any) -> None:
        # 生产 BigInteger 主键由数据库生成，SQLite 的 BIGINT 不具备 INTEGER 自增语义。
        if obj.id is None:
            obj.id = self.next_id
            self.next_id += 1
        self.session.add(obj)

    async def flush(self) -> None:
        self.session.flush()

    @asynccontextmanager
    async def begin_nested(self) -> Any:
        with self.session.begin_nested():
            yield


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Iterator[MemoryDB]:
    engine = create_engine('sqlite://')
    names = [
        'qbank_v2_question',
        'qbank_v2_wrong_question_state',
        'qbank_v2_question_review',
        'qbank_v2_bank',
        'qbank_v2_bank_revision',
        'qbank_v2_bank_section',
        'qbank_v2_bank_item',
        'qbank_v2_bank_category',
        'qbank_v2_user_question_mastery',
        'qbank_v2_practice_session',
        'qbank_v2_practice_session_item',
        'qbank_v2_question_attempt',
    ]
    Base.metadata.create_all(engine, tables=[Base.metadata.tables[name] for name in names])
    monkeypatch.setattr(module, 'lock_practice_user', AsyncMock())
    monkeypatch.setattr(WrongReviewService, '_resolve_recorded_domain_id', AsyncMock(return_value=None))
    monkeypatch.setattr(WrongReviewService, '_cleanup_orphan_materials', AsyncMock(return_value=0))
    with Session(engine) as session:
        yield MemoryDB(session)
    engine.dispose()


async def state(
    db: MemoryDB, *, owner: int = 7, batch: str = 'old-batch', source: str = '国考第九季'
) -> QbWrongQuestionState:
    question = QbQuestion(
        code=f'q-{owner}-{len(db.session.identity_map)}-{source}',
        stem='题干',
        owner_id=owner,
        visibility='private',
        created_by=owner,
    )
    db.add(question)
    await db.flush()
    wrong = QbWrongQuestionState(
        user_id=owner,
        question_id=question.id,
        entry_source='import',
        entry_metadata={'import_batch_id': batch, 'source': source, 'section_name': '原章节'},
        review_count=3,
        wrong_count=5,
        last_wrong_response='B',
        fsrs_data={'stability': 7},
        created_by=owner,
    )
    wrong.created_time = datetime(2026, 10, 29, tzinfo=UTC)
    db.add(wrong)
    await db.flush()
    return wrong


async def link(db: MemoryDB, wrong: QbWrongQuestionState, batch: str = 'new-batch', section: str = '新章节') -> None:
    await wrong_import_batch_dao.link(
        db,
        user_id=wrong.user_id,
        batch_id=batch,
        state_id=wrong.id,
        question_id=wrong.question_id,
        metadata={'source': '省考第一季', 'section_name': section},
        reused=True,
    )


async def test_old_and_new_collections_each_keep_shared_question_once(db: MemoryDB) -> None:
    wrong = await state(db)
    before = (
        dict(wrong.entry_metadata),
        wrong.review_count,
        wrong.wrong_count,
        dict(wrong.fsrs_data),
        wrong.last_wrong_response,
    )
    await link(db, wrong)
    await link(db, wrong)
    assert db.session.scalar(select(func.count()).select_from(QbQuestionReview)) == 1
    assert (
        wrong.entry_metadata,
        wrong.review_count,
        wrong.wrong_count,
        wrong.fsrs_data,
        wrong.last_wrong_response,
    ) == before
    for batch, section in [('old-batch', '原章节'), ('new-batch', '新章节')]:
        filters = WrongQuestionFilters(import_batch_id=batch)
        rows = (
            await db.execute(wrong_question_state_dao.get_list_select(user_id=7, filters=filters, view='outline'))
        ).all()
        assert [(row.id, row.section_name) for row in rows] == [(wrong.id, section)]
        total, sections = await wrong_question_state_dao.get_section_counts(db, user_id=7, filters=filters)
        assert total == 1 and sections == [{'section_name': section, 'total': 1}]
    collections = await wrong_question_state_dao.get_collection_counts(db, user_id=7, status='active')
    assert {row['collection_id']: row['total'] for row in collections} == {'old-batch': 1, 'new-batch': 1}


async def test_reused_only_batches_with_equal_time_paginate_without_loss(db: MemoryDB) -> None:
    wrong = await state(db)
    for batch in ['batch-001', 'batch-002', 'batch-003']:
        await link(db, wrong, batch)
    for event in db.session.scalars(select(QbQuestionReview)):
        event.reviewed_time = datetime(2026, 11, 9, tzinfo=UTC)
    await db.flush()
    batches = []
    cursor = None
    for _ in range(5):
        page = await WrongReviewService.get_import_batches_page(db=db, user_id=7, size=1, cursor=cursor)
        batches.extend(item.import_batch_id for item in page.items)
        if not page.has_more:
            break
        assert page.next_cursor != cursor
        cursor = page.next_cursor
    assert batches == ['batch-003', 'batch-002', 'batch-001', 'old-batch']


async def test_undo_reused_batch_preserves_original_state_and_reviews(db: MemoryDB) -> None:
    wrong = await state(db)
    review = QbQuestionReview(
        user_id=7,
        question_id=wrong.question_id,
        wrong_state_id=wrong.id,
        idempotency_key='real-review',
        summary='原复盘',
        created_by=7,
    )
    db.add(review)
    await link(db, wrong)
    result = await WrongReviewService.undo_import_batch(db=db, user_id=7, import_batch_id='new-batch')
    assert (result.deleted_states, result.deleted_questions, result.deleted_reviews, result.detached_states) == (
        0,
        0,
        0,
        1,
    )
    assert wrong.deleted == 0 and review.deleted == 0 and wrong.review_count == 3
    page = await WrongReviewService.get_import_batches_page(db=db, user_id=7)
    assert [item.import_batch_id for item in page.items] == ['old-batch']
    with pytest.raises(errors.NotFoundError):
        await WrongReviewService.undo_import_batch(db=db, user_id=7, import_batch_id='new-batch')


async def test_undo_original_shared_batch_does_not_resurrect_legacy_membership(db: MemoryDB) -> None:
    wrong = await state(db)
    await link(db, wrong)
    result = await WrongReviewService.undo_import_batch(db=db, user_id=7, import_batch_id='old-batch')
    assert result.detached_states == 1 and wrong.deleted == 0
    page = await WrongReviewService.get_import_batches_page(db=db, user_id=7)
    assert [item.import_batch_id for item in page.items] == ['new-batch']
    assert wrong.entry_metadata['import_batch_id'] == 'old-batch'


async def test_undo_exclusive_new_state_removes_it_only(db: MemoryDB) -> None:
    wrong = await state(db, batch='new-batch')
    await link(db, wrong)
    result = await WrongReviewService.undo_import_batch(db=db, user_id=7, import_batch_id='new-batch')
    assert result.deleted_states == 1 and result.deleted_questions == 1 and result.detached_states == 0
    assert wrong.deleted == wrong.id


async def test_batch_memberships_are_user_isolated(db: MemoryDB) -> None:
    wrong = await state(db, owner=8)
    await link(db, wrong)
    page = await WrongReviewService.get_import_batches_page(db=db, user_id=7)
    assert page.items == []
    with pytest.raises(errors.NotFoundError):
        await WrongReviewService.undo_import_batch(db=db, user_id=7, import_batch_id='new-batch')
    assert wrong.deleted == 0


async def test_import_29_with_11_reused_associates_all_29(db: MemoryDB, monkeypatch: pytest.MonkeyPatch) -> None:
    states = [
        await state(db, batch='old-batch' if index < 11 else 'new-batch', source=f'旧来源{index}')
        for index in range(29)
    ]

    async def capture(**kwargs: Any) -> BatchImportItemResult:
        index = int(kwargs['obj'].external_key)
        wrong = states[index]
        await db.flush()
        return BatchImportItemResult(
            external_key=str(index), question_id=wrong.question_id, wrong_state_id=wrong.id, reused=index < 11
        )

    monkeypatch.setattr(WrongReviewService, '_capture_external', capture)
    params = [
            CreateExternalWrongQuestionParam(
                entry_source='import',
            idempotency_key=f'item-{index:08}',
            stem='题干',
            answer={'answer_data': {'correct': 'A'}},
            source_system='fenbi',
            external_key=str(index),
            entry_metadata={'source': '省考第一季'},
        )
        for index in range(29)
    ]
    result = await WrongReviewService.capture_external_batch(
        db=db, user_id=7, items=params, import_batch_id='new-batch'
    )
    assert (result.succeeded, result.created, result.reused, result.failed) == (29, 18, 11, 0)
    page = await WrongReviewService.get_import_batches_page(db=db, user_id=7)
    assert {item.import_batch_id: item.total for item in page.items} == {'old-batch': 11, 'new-batch': 29}
    undo = await WrongReviewService.undo_import_batch(db=db, user_id=7, import_batch_id='new-batch')
    assert (undo.deleted_states, undo.detached_states) == (18, 11)
    assert (
        db.session.scalar(
            select(func.count()).select_from(QbWrongQuestionState).where(QbWrongQuestionState.deleted == 0)
        )
        == 11
    )


async def test_reused_capture_paths_report_reused(db: MemoryDB, monkeypatch: pytest.MonkeyPatch) -> None:
    wrong = await state(db)
    obj = CreateExternalWrongQuestionParam(
        entry_source='import',
        idempotency_key='test-key-0001',
        stem='题干',
        answer={'answer_data': {'correct': 'A'}},
        entry_metadata={'source': '省考第一季'},
    )
    monkeypatch.setattr(WrongReviewService, '_resolve_existing_state_id', AsyncMock(return_value=wrong.id))
    monkeypatch.setattr(WrongReviewService, '_fill_existing_state_content', AsyncMock(return_value=wrong))
    result = await WrongReviewService._capture_external(db=db, user_id=7, obj=obj, recorded_domain_id=None)
    assert result.reused is True and result.wrong_state_id == wrong.id


async def test_failed_item_rolls_back_its_batch_link(db: MemoryDB, monkeypatch: pytest.MonkeyPatch) -> None:
    wrong = await state(db)

    async def fail(**kwargs: Any) -> None:
        await link(db, wrong)
        raise ValueError('真实失败')

    monkeypatch.setattr(WrongReviewService, '_capture_external', fail)
    obj = CreateExternalWrongQuestionParam(
        entry_source='import',
        idempotency_key='failure-0001',
        stem='题干',
        answer={'answer_data': {'correct': 'A'}},
        entry_metadata={'source': '省考第一季'},
    )
    result = await WrongReviewService.capture_external_batch(db=db, user_id=7, items=[obj], import_batch_id='new-batch')
    assert (result.succeeded, result.created, result.reused, result.failed) == (0, 0, 0, 1)
    assert db.session.scalar(select(func.count()).select_from(QbQuestionReview)) == 0
