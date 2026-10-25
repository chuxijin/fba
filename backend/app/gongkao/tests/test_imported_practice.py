import asyncio

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import pytest

from pydantic import ValidationError
from sqlalchemy import BigInteger, Column, MetaData, Table, UniqueConstraint, create_engine, event, func, select
from sqlalchemy.orm import Session

from backend.app.gongkao.model.practice_log import GongkaoPracticeLog, GongkaoPracticeModule
from backend.app.gongkao.schema.practice_log import ImportPracticeReportParam, UpdatePracticeLogParam
from backend.app.gongkao.service.practice_log_service import PracticeLogService
from backend.app.gongkao.tests.test_practice_report import MemorySession
from backend.app.question_bank_v2.crud.crud_practice import practice_response_dao, practice_session_dao
from backend.app.question_bank_v2.model.asset import QbAsset, QbQuestionAsset
from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.material import QbMaterial, QbMaterialRevision, QbQuestionMaterial
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer, QbQuestionExplanation
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.schema.practice import SavePracticeResponseParam, SubmitPracticeItemParam
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.common.exception import errors
from backend.utils.timezone import timezone

TABLE_MODELS = (
    GongkaoPracticeLog,
    GongkaoPracticeModule,
    QbQuestion,
    QbQuestionAnswer,
    QbQuestionExplanation,
    QbAsset,
    QbQuestionAsset,
    QbMaterial,
    QbMaterialRevision,
    QbQuestionMaterial,
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
    QbBankRevision,
    QbBankItem,
    QbBankSection,
    QbWrongQuestionState,
)


@pytest.fixture
def db() -> Any:
    """真实表定义、外键和唯一约束在独立 SQLite 中执行；外围账号/题库仅提供身份。"""
    engine = create_engine('sqlite://')
    event.listen(engine, 'connect', lambda connection, _record: connection.execute('PRAGMA foreign_keys=ON'))
    metadata = MetaData()
    for model in TABLE_MODELS:
        model.__table__.to_metadata(metadata)
    references: dict[str, set[str]] = {}
    for table in list(metadata.tables.values()):
        for fk in table.foreign_keys:
            table_name, column_name = fk.target_fullname.rsplit('.', 1)
            if table_name not in metadata.tables:
                references.setdefault(table_name, set()).add(column_name)
    for name, columns in references.items():
        Table(
            name,
            metadata,
            *(Column(column, BigInteger, primary_key=column == 'id') for column in columns),
            UniqueConstraint(*sorted(columns)),
        )
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(metadata.tables['sys_user'].insert(), [{'id': 7}, {'id': 8}])
    with Session(engine, expire_on_commit=False) as session:
        yield MemorySession(session)
    engine.dispose()


def payload(**updates: Any) -> dict[str, Any]:
    topics = [
        {'module_name': '行程问题', 'total_questions': 2, 'correct_count': 1, 'duration_seconds': 130},
        {'module_name': '工程问题', 'total_questions': 1, 'correct_count': 0, 'unanswered_count': 1},
    ]
    questions = [
        {
            'source_question_key': f'question-{index}',
            'position': index,
            'module_path': ['数量关系', '数学运算', '工程问题' if index == 3 else '行程问题'],
            'stem': f'<p>第 {index} 题 <img src="https://example.com/formula.png" width="40" /></p>',
            'options': [
                {'option_code': 'A', 'content': '10', 'sort_order': 0},
                {'option_code': 'B', 'content': '20', 'sort_order': 1},
            ],
            'answer': {'answer_data': {'correct': 'B' if index == 2 else 'A'}},
            'explanations': [{'content': f'<p>解析 {index}</p>', 'is_default': True}],
            'materials': [{'link_key': 'passage-1', 'title': '共同材料', 'content': '<p>甲乙两地相距……</p>'}],
            'status': ['correct', 'wrong', 'unanswered'][index - 1],
            'response_data': 'A' if index != 3 else None,
            'duration_seconds': [0, 130, None][index - 1],
        }
        for index in (1, 2, 3)
    ]
    return {
        'source_key': '1_1_archive',
        'source_url': 'https://spa.fenbi.com/ti/exam/solution/1_1_archive',
        'material_title': '完整报告',
        'practiced_at': '2026-10-19',
        'total_questions': 3,
        'correct_count': 1,
        'unanswered_count': 1,
        'duration_seconds': 130,
        'score': 55.5,
        'full_score': 100,
        'modules': [
            {
                'module_name': '数量关系',
                'total_questions': 3,
                'correct_count': 1,
                'unanswered_count': 1,
                'duration_seconds': 130,
                'children': [
                    {
                        'module_name': '数学运算',
                        'total_questions': 3,
                        'correct_count': 1,
                        'unanswered_count': 1,
                        'duration_seconds': 130,
                        'children': topics,
                    }
                ],
            }
        ],
        'questions': [questions[2], questions[0], questions[1]],
        **updates,
    }


async def import_report(db: MemorySession, data: dict | None = None, user_id: int = 7) -> Any:
    return await PracticeLogService.import_report(
        db=db,
        user_id=user_id,
        obj=ImportPracticeReportParam.model_validate(data or payload()),
    )


def count(db: MemorySession, model: Any, *, active: bool = True) -> int:
    stmt = select(func.count()).select_from(model)
    if active:
        stmt = stmt.where(model.deleted == 0)
    return db.session.scalar(stmt)


def test_complete_import_reuses_tables_keeps_order_content_and_raw_scoring(db: MemorySession) -> None:
    async def run() -> None:
        result = await import_report(db)
        assert result.practice.detail_status == 'complete'
        assert result.practice.added_questions == 3
        assert count(db, QbQuestion) == 3
        assert count(db, QbQuestionAttempt) == 2, '未答题不伪造提交事实'
        assert count(db, QbPracticeSessionResponse) == 3
        assert count(db, QbMaterial) == 1
        assert count(db, QbQuestionMaterial) == 3
        assert count(db, QbWrongQuestionState) == 0, '归档整卷不等于加入错题本'
        detail = await PracticeLogService.get_question_details(db=db, user_id=7, pk=result.record.id)
        assert [q.position for q in detail.items] == [1, 2, 3]
        assert [q.duration_seconds for q in detail.items] == [0, 130, None]
        assert detail.items[1].response_data == 'A'
        assert detail.items[1].answer.answer_data['correct'] == 'B'
        assert detail.items[2].attempt_id is None
        assert '<img ' in detail.items[0].stem
        session = await PracticeService.get(db=db, user_id=7, session_key=detail.session_key)
        assert session.bank_id is None
        assert session.started_time is None
        assert session.practiced_at == date(2026, 10, 19)
        assert len(session.materials) == 1
        assert [q.duration_ms for q in session.items] == [0, 130000, None]
        assert all(q.max_score is None for q in session.items)
        assert all('answer' not in q.display_config for q in session.items)
        report = await PracticeService.get_report(db=db, user_id=7, session_key=detail.session_key)
        assert report.score == Decimal('55.5') and report.total_score == Decimal(100)
        assert report.accuracy_basis == 'all_questions'
        assert report.accuracy_rate == Decimal(1) / Decimal(3)
        assert report.unanswered_items == 1
        assert report.started_time is None and report.submitted_time is None
        solutions = await PracticeService.get_session_solutions(db=db, user_id=7, session_key=detail.session_key)
        assert len(solutions) == 3
        assert solutions[0].explanations[0].content == '<p>解析 1</p>'
        solution = await PracticeService.get_solution(
            db=db,
            user_id=7,
            session_key=detail.session_key,
            session_item_id=detail.items[2].session_item_id,
        )
        assert solution.answer_data == {'correct': 'A'}, '未答题也可以在历史归档中查看解析'

    asyncio.run(run())


def test_repeat_and_incremental_content_supplement_preserve_ids(db: MemorySession) -> None:
    async def run() -> None:
        full = payload()
        first_data = deepcopy(full)
        first_data['questions'] = [deepcopy(full['questions'][1])]
        first_data['questions'][0]['answer'] = None
        first_data['questions'][0]['explanations'] = []
        first = await import_report(db, first_data)
        assert first.practice.detail_status == 'partial'
        before = await PracticeLogService.get_question_details(db=db, user_id=7, pk=first.record.id)
        assert before.items[0].missing_content == ['answer', 'explanations']
        with pytest.raises(errors.RequestError, match='尚未导入齐全'):
            await PracticeService.get_report(db=db, user_id=7, session_key=first.practice.session_key)
        second = await import_report(db, full)
        assert not second.created and second.enriched
        assert second.practice.added_questions == 2 and second.practice.supplemented_questions == 1
        after = await PracticeLogService.get_question_details(db=db, user_id=7, pk=first.record.id)
        assert before.items[0].question_id == after.items[0].question_id
        assert before.items[0].attempt_id == after.items[0].attempt_id
        retry = await import_report(db, full)
        assert retry.practice.added_questions == retry.practice.supplemented_questions == 0
        assert not retry.enriched
        assert count(db, QbPracticeSession) == 1 and count(db, QbQuestionAttempt) == 2

    asyncio.run(run())


def test_conflicts_roll_back_the_whole_import_and_never_rewrite_attempts(db: MemorySession) -> None:
    async def run() -> None:
        initial = payload()
        initial['questions'] = [initial['questions'][1]]
        result = await import_report(db, initial)
        conflict = payload()
        conflict['questions'][1]['duration_seconds'] = 2
        with pytest.raises(errors.ConflictError, match='duration_seconds'):
            await import_report(db, conflict)
        assert count(db, QbQuestion) == 1 and count(db, QbPracticeSessionItem) == 1
        bad_totals = payload(source_key='1_1_bad', source_url='https://spa.fenbi.com/ti/exam/solution/1_1_bad')
        bad_totals['questions'][2]['status'] = 'correct'
        with pytest.raises(errors.RequestError, match='统计冲突'):
            await import_report(db, bad_totals)
        assert count(db, GongkaoPracticeLog) == 1
        detail = await PracticeLogService.get_question_details(db=db, user_id=7, pk=result.record.id)
        assert detail.items[0].duration_seconds == 0

    asyncio.run(run())


def test_imports_are_private_and_are_excluded_from_online_lists_and_checkin(db: MemorySession) -> None:
    async def run() -> None:
        first = await import_report(db)
        other = await import_report(db, user_id=8)
        assert first.practice.session_key != other.practice.session_key
        with pytest.raises(errors.NotFoundError):
            await PracticeLogService.get_question_details(db=db, user_id=8, pk=first.record.id)
        with pytest.raises(errors.NotFoundError):
            await PracticeService.get(db=db, user_id=8, session_key=first.practice.session_key)
        assert count(db, QbQuestion) == 6
        assert {q.visibility for q in db.session.scalars(select(QbQuestion))} == {'private'}
        stmt = PracticeService.get_list_select(user_id=7, status=None, mode=None, source_type=None, bank_id=None)
        assert list((await db.execute(stmt)).all()) == []
        today = await practice_response_dao.get_today_practice_summary(
            db,
            user_id=7,
            since=datetime(2020, 1, 1, tzinfo=timezone.tz_info),
        )
        assert today['practice_count'] == 0

    asyncio.run(run())


def test_imported_history_cannot_be_submitted_or_hidden_as_online_practice(db: MemorySession) -> None:
    async def run() -> None:
        result = await import_report(db)
        detail = await PracticeLogService.get_question_details(db=db, user_id=7, pk=result.record.id)
        for method, obj in (
            (PracticeService.save_response, SavePracticeResponseParam(response_data='B')),
            (PracticeService.submit_item, SubmitPracticeItemParam(response_data='B')),
        ):
            with pytest.raises(errors.ConflictError, match='只读'):
                await method(
                    db=db,
                    user_id=7,
                    session_key=detail.session_key,
                    session_item_id=detail.items[0].session_item_id,
                    obj=obj,
                )
        with pytest.raises(errors.ConflictError, match='只读'):
            await PracticeService.submit_session(db=db, user_id=7, session_key=detail.session_key)
        with pytest.raises(errors.ConflictError, match='导入练习记录'):
            await PracticeService.hide(db=db, user_id=7, session_key=detail.session_key)
        assert count(db, QbQuestionAttempt) == 2

    asyncio.run(run())


def test_history_uses_snapshots_and_log_edits_sync_only_display_metadata(db: MemorySession) -> None:
    async def run() -> None:
        result = await import_report(db)
        original = await PracticeLogService.get_question_details(db=db, user_id=7, pk=result.record.id)
        question = db.session.get(QbQuestion, original.items[0].question_id)
        question.stem = '后续题干编辑'
        db.session.scalars(
            select(QbQuestionExplanation).where(QbQuestionExplanation.question_id == question.id)
        ).first().content = '新的解析'
        await db.flush()
        await PracticeLogService.update(
            db=db,
            user_id=7,
            pk=result.record.id,
            obj=UpdatePracticeLogParam(
                material_title='我的复盘标题',
                practiced_at=date(2026, 10, 18),
            ),
        )
        session = await PracticeService.get(db=db, user_id=7, session_key=original.session_key)
        assert session.title_snapshot == '我的复盘标题'
        assert session.practiced_at == date(2026, 10, 18)
        assert session.items[0].stem == original.items[0].stem
        solutions = await PracticeService.get_session_solutions(db=db, user_id=7, session_key=original.session_key)
        assert solutions[0].explanations[0].content == '<p>解析 1</p>'
        assert session.source_snapshot['summary']['practiced_at'] == '2026-10-19'

    asyncio.run(run())


def test_delete_removes_only_associated_history_and_allows_fresh_reimport(db: MemorySession) -> None:
    async def run() -> None:
        first = await import_report(db)
        second = await import_report(
            db, payload(source_key='1_1_other', source_url='https://spa.fenbi.com/ti/exam/solution/1_1_other')
        )
        assert count(db, QbQuestion) == 3, '同用户跨报告复用来源题目'
        await PracticeLogService.delete(db=db, user_id=7, pk=first.record.id)
        assert count(db, QbPracticeSession) == 1
        assert count(db, QbQuestionAttempt) == 2
        assert count(db, QbQuestion) == 3
        assert await practice_session_dao.get_by_key(db, second.practice.session_key, user_id=7)
        again = await import_report(db)
        assert again.created
        assert count(db, QbPracticeSession) == 2

    asyncio.run(run())


@pytest.mark.parametrize(
    'change', ['duplicate_key', 'duplicate_position', 'deep_path', 'unknown_path', 'missing_response', 'bad_option']
)
def test_invalid_question_identity_or_structure_is_rejected(change: str) -> None:
    data = payload()
    if change == 'duplicate_key':
        data['questions'][0]['source_question_key'] = data['questions'][1]['source_question_key']
    elif change == 'duplicate_position':
        data['questions'][0]['position'] = data['questions'][1]['position']
    elif change == 'deep_path':
        data['questions'][0]['module_path'].append('不再向下细分')
    elif change == 'unknown_path':
        data['questions'][0]['module_path'] = ['不存在的模块']
    elif change == 'missing_response':
        data['questions'][1]['response_data'] = None
    elif change == 'bad_option':
        data['questions'][1]['response_data'] = 'D'
    with pytest.raises(ValidationError):
        ImportPracticeReportParam.model_validate(data)
