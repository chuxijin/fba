from copy import deepcopy
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError

from backend.app.question_bank_v2.schema.annotation import AnnotationContext, SaveAnnotationsParam, TextAnnotation
from backend.app.question_bank_v2.schema.practice import SubmitPracticeItemParam
from backend.app.question_bank_v2.service import annotation_service as module
from backend.app.question_bank_v2.service import practice_service as practice_module
from backend.app.question_bank_v2.utils.annotation_policy import persistent_annotations_enabled
from backend.common.exception import errors


def mark(**values: Any) -> dict[str, Any]:
    return {
        'id': 'mark_example',
        'target': 'stem',
        'segment': 0,
        'start': 0,
        'end': 2,
        'quote': '至少',
        'text_hash': '12345678',
        'note': '不是恰好',
        **values,
    }


class DB:
    async def flush(self) -> None:
        pass


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> tuple[DB, SimpleNamespace, SimpleNamespace]:
    document = SimpleNamespace(annotations=[TextAnnotation(**mark()).model_dump()], save_version=1)
    attempt = SimpleNamespace(
        id=91,
        annotations=deepcopy(document.annotations),
        session=SimpleNamespace(mode='practice', source_type='bank', delivery_config={}),
    )
    monkeypatch.setattr(module.user_content_service, '_resolve_question_context', AsyncMock())
    monkeypatch.setattr(
        module.practice_session_dao,
        'get_owned_item',
        AsyncMock(return_value=(SimpleNamespace(status='in_progress'), SimpleNamespace(id=81, question_id=77))),
    )
    monkeypatch.setattr(module.question_annotation_dao, 'get_document', AsyncMock(return_value=document))
    monkeypatch.setattr(module.question_annotation_dao, 'latest_document', AsyncMock(return_value=document))
    monkeypatch.setattr(module.question_annotation_dao, 'latest_attempt', AsyncMock(return_value=attempt))
    monkeypatch.setattr(module.question_annotation_dao, 'material_contexts', AsyncMock(return_value={(12, 13)}))
    return DB(), document, attempt


def test_annotation_range_and_material_validation() -> None:
    assert TextAnnotation(**mark()).quote == '至少'
    assert TextAnnotation(**mark(quote='😀', end=2)).end == 2
    for bad in (mark(end=1), mark(end=0), mark(target='material'), mark(target='stem', material_id=12)):
        with pytest.raises(ValidationError):
            TextAnnotation(**bad)
    with pytest.raises(ValidationError):
        AnnotationContext(session_key='abcdefgh')


@pytest.mark.asyncio
async def test_review_edits_preserve_original_attempt_snapshot(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, document, attempt = harness
    result = await module.annotation_service.save(
        db=db,
        user_id=7,
        question_id=77,
        obj=SaveAnnotationsParam(
            context_key='review:91', save_version=1, source='wrong', annotations=[mark(note='复盘时补充')]
        ),
    )
    assert result.annotations[0].note == '复盘时补充'
    assert result.save_version == 2
    assert result.original_annotations[0].note == '不是恰好'
    assert attempt.annotations[0]['note'] == '不是恰好'
    assert document.annotations[0]['note'] == '复盘时补充'


@pytest.mark.asyncio
async def test_stale_different_edits_conflict_but_identical_retry_is_idempotent(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, _, _ = harness
    result = await module.annotation_service.save(
        db=db,
        user_id=7,
        question_id=77,
        obj=SaveAnnotationsParam(context_key='review:91', save_version=0, annotations=[mark()]),
    )
    assert result.save_version == 1
    with pytest.raises(errors.ConflictError):
        await module.annotation_service.save(
            db=db,
            user_id=7,
            question_id=77,
            obj=SaveAnnotationsParam(context_key='review:91', save_version=0, annotations=[mark(note='不同内容')]),
        )


@pytest.mark.asyncio
async def test_session_context_cannot_access_another_question_or_closed_session(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, _, _ = harness
    with pytest.raises(errors.NotFoundError):
        await module.annotation_service.get(
            db=db, user_id=7, question_id=78, obj=AnnotationContext(session_key='abcdefgh', session_item_id=81)
        )
    module.practice_session_dao.get_owned_item.return_value = None
    with pytest.raises(errors.NotFoundError):
        await module.annotation_service.get(
            db=db, user_id=8, question_id=77, obj=AnnotationContext(session_key='abcdefgh', session_item_id=81)
        )
    module.practice_session_dao.get_owned_item.return_value = (
        SimpleNamespace(status='graded'),
        SimpleNamespace(id=81, question_id=77),
    )
    with pytest.raises(errors.ConflictError):
        await module.annotation_service.save(
            db=db,
            user_id=7,
            question_id=77,
            obj=SaveAnnotationsParam(context_key='item:81', session_key='abcdefgh', session_item_id=81),
        )


@pytest.mark.asyncio
async def test_material_from_another_question_is_rejected(harness: tuple[DB, SimpleNamespace, SimpleNamespace]) -> None:
    db, _, _ = harness
    with pytest.raises(errors.RequestError):
        await module.annotation_service.save(
            db=db,
            user_id=7,
            question_id=77,
            obj=SaveAnnotationsParam(
                context_key='review:91',
                save_version=1,
                annotations=[mark(target='material', material_id=99, material_revision_id=100)],
            ),
        )


@pytest.mark.asyncio
async def test_new_wrong_attempt_invalidates_old_review_context(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, _, _ = harness
    with pytest.raises(errors.ConflictError):
        await module.annotation_service.save(
            db=db,
            user_id=7,
            question_id=77,
            obj=SaveAnnotationsParam(context_key='review:90', save_version=1, annotations=[]),
        )


@pytest.mark.parametrize('source_type', ['bank', 'wrong'])
@pytest.mark.asyncio
async def test_answer_submission_copies_annotation_snapshot(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace], monkeypatch: pytest.MonkeyPatch, source_type: str
) -> None:
    db, document, _ = harness
    session = SimpleNamespace(
        id=71,
        mode='exam',
        source_type=source_type,
        status='in_progress',
        answered_items=0,
        correct_items=0,
        score=Decimal(0),
    )
    item = SimpleNamespace(id=81, question_id=77, max_score=Decimal(1))
    monkeypatch.setattr(practice_module.PracticeService, '_get_owned_item', AsyncMock(return_value=(session, item)))
    monkeypatch.setattr(practice_module.PracticeService, '_ensure_session_open', AsyncMock())
    monkeypatch.setattr(
        practice_module.question_answer_dao,
        'get_by_question',
        AsyncMock(return_value=SimpleNamespace(answer_data={'correct': 'A'}, grading_method='rule', grading_config={})),
    )
    monkeypatch.setattr(
        practice_module.question_dao, 'get', AsyncMock(return_value=SimpleNamespace(question_type='single_choice'))
    )
    monkeypatch.setattr(practice_module.practice_response_dao, 'get', AsyncMock(return_value=None))

    async def create_response(_db: DB, data: dict[str, Any]) -> SimpleNamespace:
        await _db.flush()
        return SimpleNamespace(**data)

    monkeypatch.setattr(practice_module.practice_response_dao, 'create', create_response)
    grade = SimpleNamespace(
        grading_status='graded', is_correct=True, score=Decimal(1), grading_method='rule', details={}
    )
    monkeypatch.setattr(practice_module.practice_grading_service, 'grade', lambda **_kwargs: grade)
    monkeypatch.setattr(practice_module.question_attempt_dao, 'get_next_attempt_no', AsyncMock(return_value=1))
    saved: dict[str, Any] = {}

    async def create_attempt(_db: DB, data: dict[str, Any]) -> SimpleNamespace:
        saved.update(data)
        await _db.flush()
        return SimpleNamespace(id=91, **data)

    monkeypatch.setattr(practice_module.question_attempt_dao, 'create', create_attempt)
    await practice_module.practice_service.submit_item(
        db=db, session_key='abcdefgh', user_id=7, session_item_id=81, obj=SubmitPracticeItemParam(response_data='A')
    )
    document.annotations[0]['note'] = '后来改动'
    if source_type == 'bank':
        assert saved['annotations'][0]['note'] == '不是恰好'
    else:
        assert saved['annotations'] == []
        module.question_annotation_dao.get_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_unsubmitted_formal_annotations_survive_hidden_session(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, document, _ = harness
    module.practice_session_dao.get_owned_item.return_value = None
    module.question_annotation_dao.get_document.return_value = None
    module.question_annotation_dao.latest_attempt.return_value = None
    result = await module.annotation_service.get(
        db=db, user_id=7, question_id=77, obj=AnnotationContext(source='wrong')
    )
    assert result.owner_key == 'user:7'
    assert result.context_key == 'review:0'
    assert result.annotations[0].note == document.annotations[0]['note']
    assert result.original_annotations == []
    assert result.save_version == 0
    module.practice_session_dao.get_owned_item.assert_not_awaited()


@pytest.mark.asyncio
async def test_new_practice_keeps_old_marks_as_optional_history(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, _, _ = harness
    module.question_annotation_dao.get_document.return_value = None
    result = await module.annotation_service.get(
        db=db, user_id=7, question_id=77, obj=AnnotationContext(session_key='new-session', session_item_id=81)
    )
    assert result.annotations == []
    assert result.original_annotations[0].note == '不是恰好'
    module.question_annotation_dao.latest_document.assert_awaited_once_with(
        db, user_id=7, question_id=77, exclude_context_key='item:81'
    )


@pytest.mark.asyncio
async def test_exam_does_not_return_history(harness: tuple[DB, SimpleNamespace, SimpleNamespace]) -> None:
    db, _, _ = harness
    module.practice_session_dao.get_owned_item.return_value = (
        SimpleNamespace(mode='exam', status='in_progress'),
        SimpleNamespace(id=81, question_id=77),
    )
    module.question_annotation_dao.get_document.return_value = None
    result = await module.annotation_service.get(
        db=db, user_id=7, question_id=77, obj=AnnotationContext(session_key='exam-session', session_item_id=81)
    )
    assert result.annotations == []
    assert result.original_annotations == []
    module.question_annotation_dao.latest_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_latest_empty_marks_do_not_resurrect_old_snapshots(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, _, _ = harness
    module.question_annotation_dao.latest_document.return_value = SimpleNamespace(annotations=[])
    result = await module.annotation_service.get(
        db=db, user_id=7, question_id=77, obj=AnnotationContext(source='wrong')
    )
    assert result.annotations == []
    assert result.original_annotations[0].note == '不是恰好'


@pytest.mark.asyncio
async def test_delayed_save_cannot_write_to_another_logged_in_account(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, _, _ = harness
    with pytest.raises(errors.ConflictError):
        await module.annotation_service.save(
            db=db,
            user_id=8,
            question_id=77,
            obj=SaveAnnotationsParam(owner_key='user:7', context_key='review:0', annotations=[mark()]),
        )
    module.question_annotation_dao.get_document.assert_not_awaited()


@pytest.mark.parametrize(
    ('mode', 'source', 'config', 'enabled'),
    [
        ('practice', 'bank', {}, True),
        ('exam', 'bank', {}, True),
        ('mock', 'bank', {}, True),
        ('adaptive', 'knowledge_point', {}, True),
        ('memorize', 'bank', {}, False),
        ('practice', 'wrong', {}, False),
        ('practice', 'favorite', {}, False),
        ('practice', 'note', {}, False),
        ('practice', 'custom', {'annotations_enabled': False}, False),
        ('practice', 'custom', {}, True),
    ],
)
def test_annotation_saving_scope(mode: str, source: str, config: dict[str, Any], *, enabled: bool) -> None:
    assert (
        persistent_annotations_enabled(SimpleNamespace(mode=mode, source_type=source, delivery_config=config))
        is enabled
    )


@pytest.mark.asyncio
async def test_wrong_drill_neither_reads_nor_saves_annotations(
    harness: tuple[DB, SimpleNamespace, SimpleNamespace],
) -> None:
    db, _, _ = harness
    module.practice_session_dao.get_owned_item.return_value = (
        SimpleNamespace(mode='practice', source_type='wrong', status='in_progress'),
        SimpleNamespace(id=81, question_id=77),
    )
    result = await module.annotation_service.get(
        db=db, user_id=7, question_id=77, obj=AnnotationContext(session_key='wrong-session', session_item_id=81)
    )
    assert result.enabled is False
    assert result.annotations == []
    assert result.original_annotations == []
    with pytest.raises(errors.ForbiddenError):
        await module.annotation_service.save(
            db=db,
            user_id=7,
            question_id=77,
            obj=SaveAnnotationsParam(
                context_key='item:81', session_key='wrong-session', session_item_id=81, annotations=[mark()]
            ),
        )
    module.question_annotation_dao.get_document.assert_not_awaited()
    module.question_annotation_dao.latest_document.assert_not_awaited()


@pytest.mark.asyncio
async def test_history_filters_temporary_sources_without_excluding_hidden_formal_sessions() -> None:
    from sqlalchemy.dialects import postgresql

    from backend.app.question_bank_v2.crud.crud_annotation import question_annotation_dao

    result = SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    await question_annotation_dao.latest_document(db, user_id=7, question_id=77)
    compiled = db.execute.call_args.args[0].compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert 'qbank_v2_practice_session.deleted' not in sql
    assert 'qbank_v2_practice_session.source_type NOT IN' in sql
    assert compiled.params['user_id_1'] == 7
    assert compiled.params['question_id_1'] == 77
