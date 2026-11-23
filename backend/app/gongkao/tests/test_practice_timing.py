"""计时策略的离线、最小闭环验证；仅内存 SQLite 与隔离 Mock。"""

import asyncio
import importlib.util

from copy import deepcopy
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.orm import Session

from backend.app.gongkao.crud.crud_practice_log import practice_module_dao
from backend.app.gongkao.model.practice_log import GongkaoPracticeLog
from backend.app.gongkao.schema.practice_log import UpdatePracticeLogParam
from backend.app.gongkao.service.practice_log_service import PracticeLogService
from backend.app.gongkao.tests.test_practice_report import db, report
from backend.app.question_bank_v2.crud.crud_external_wrong import EXTERNAL_WRONG_KEY
from backend.app.question_bank_v2.crud.crud_practice import question_attempt_dao
from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbQuestionAttempt
from backend.app.question_bank_v2.service.external_practice_import_service import ExternalPracticeImportService
from backend.app.question_bank_v2.service import external_wrong_service as wrong_module
from backend.app.question_bank_v2.tests.test_external_source_timing import (
    NOW,
    AsyncSQLiteDB,
    _seed_attempt,
    _seed_question,
    _seed_session,
)
from backend.app.question_bank_v2.utils.external_practice import EXTERNAL_PRACTICE_ORIGIN


@pytest.mark.parametrize('actual', [None, 0, 7200])
def test_import_keeps_source_but_excludes_all_unmeasured_levels(db, actual):
    async def run():
        imported = await PracticeLogService.import_report(
            db=db, user_id=7, obj=report(exclude_source_timing=True, manual_duration_seconds=actual)
        )
        record = imported.record
        assert record.duration_seconds == 478
        assert record.effective_duration_seconds == actual
        assert record.modules[0].duration_seconds == 478
        assert record.modules[0].effective_duration_seconds is None
        assert all(child.effective_duration_seconds is None for child in record.modules[0].children)
        comparisons = await PracticeLogService.get_comparisons(db=db, user_id=7)
        points = {s['level']: s['points'][0] for s in comparisons['series']}
        assert points['subject']['duration_seconds'] == actual
        assert points['module']['duration_seconds'] is None
        assert points['submodule']['duration_seconds'] is None
        assert all(p['correct_count'] >= 0 and p['accuracy'] is not None for p in points.values())
        assert (await practice_module_dao.get_module_trends(db, user_id=7))[0]['duration_seconds'] is None

    asyncio.run(run())


def test_actual_module_time_is_only_used_at_its_own_level(db):
    payload = report(exclude_source_timing=True)
    payload.modules[0].manual_duration_seconds = 600
    payload.modules[0].children[0].manual_duration_seconds = 0

    async def run():
        first = await PracticeLogService.import_report(db=db, user_id=7, obj=payload)
        assert first.record.effective_duration_seconds is None
        assert first.record.modules[0].effective_duration_seconds == 600
        assert first.record.modules[0].children[0].effective_duration_seconds == 0
        assert first.record.modules[0].children[1].effective_duration_seconds is None
        assert (await practice_module_dao.get_module_trends(db, user_id=7))[0]['duration_seconds'] == 600

    asyncio.run(run())


def test_history_edit_omitted_policy_reimport_and_restoration(db):
    async def run():
        first = await PracticeLogService.import_report(db=db, user_id=7, obj=report())
        edited = await PracticeLogService.update(
            db=db,
            user_id=7,
            pk=first.record.id,
            obj=UpdatePracticeLogParam(
                exclude_source_timing=True, manual_duration_seconds=7200, practiced_at=date(2026, 10, 18)
            ),
        )
        assert edited.duration_seconds == 478 and edited.effective_duration_seconds == 7200
        title_only = await PracticeLogService.update(
            db=db, user_id=7, pk=first.record.id, obj=UpdatePracticeLogParam(material_title='纸上实际作答')
        )
        assert title_only.exclude_source_timing is True
        retry = await PracticeLogService.import_report(db=db, user_id=7, obj=report(exclude_source_timing=False))
        assert retry.created is False
        assert retry.record.effective_duration_seconds == 7200
        assert retry.record.practiced_at == date(2026, 10, 18)
        restored = await PracticeLogService.update(
            db=db, user_id=7, pk=first.record.id, obj=UpdatePracticeLogParam(exclude_source_timing=False)
        )
        assert restored.effective_duration_seconds == 478
        assert restored.modules[0].effective_duration_seconds == 478
        assert restored.modules[0].children[0].effective_duration_seconds == 33

    asyncio.run(run())


def test_sync_policy_preserves_source_snapshot_and_actual_date(db, monkeypatch):
    async def run():
        first = await PracticeLogService.import_report(db=db, user_id=7, obj=report())
        snapshot = {
            'origin': EXTERNAL_PRACTICE_ORIGIN,
            'practice_log_id': first.record.id,
            'practiced_at': '2026-10-19',
            'platform': 'fenbi',
            'source_key': report().source_key,
            'summary': report().model_dump(mode='json', exclude={'questions'}),
            'reference_policy': 1,
        }
        session = SimpleNamespace(source_snapshot=deepcopy(snapshot), title_snapshot=first.record.material_title)
        from backend.app.question_bank_v2.service import external_practice_import_service as module
        monkeypatch.setattr(module.external_practice_dao, 'get_session', AsyncMock(return_value=session))
        await PracticeLogService.update(
            db=db,
            user_id=7,
            pk=first.record.id,
            obj=UpdatePracticeLogParam(exclude_source_timing=True, manual_duration_seconds=7200),
        )
        assert session.source_snapshot['exclude_source_timing'] is True
        assert session.source_snapshot['summary']['duration_seconds'] == 478
        assert session.source_snapshot['summary']['modules'] == snapshot['summary']['modules']
        assert session.source_snapshot['summary']['manual_duration_seconds'] == 7200
        assert session.source_snapshot['reference_policy'] == 1

    asyncio.run(run())


@pytest.mark.parametrize('actual', [None, 0, 7200])
def test_external_session_report_does_not_infer_question_timing(monkeypatch, actual):
    summary = report(exclude_source_timing=True, manual_duration_seconds=actual).model_dump(mode='json')
    items = [
        SimpleNamespace(
            id=i,
            question_id=i,
            position=i,
            display_config={
                'external_practice': {
                    'module_path': ['政治理论'],
                    'status': 'correct' if i < 8 else 'wrong',
                    'duration_seconds': 20,
                    'score': 1,
                    'max_score': 1,
                }
            },
        )
        for i in range(20)
    ]
    from backend.app.question_bank_v2.service import external_practice_import_service as module

    monkeypatch.setattr(module.external_practice_dao, 'get_items', AsyncMock(return_value=items))
    session = {
        'id': 1,
        'session_key': 'external-test',
        'mode': 'exam',
        'source_type': 'custom',
        'title_snapshot': '纸上',
        'status': 'graded',
        'source_snapshot': {'summary': summary, 'exclude_source_timing': True, 'practiced_at': '2026-10-19'},
    }
    result = asyncio.run(ExternalPracticeImportService.session_report(db=AsyncMock(), session=session))
    assert result.total_duration_ms == (None if actual is None else actual * 1000)
    assert all(item.duration_ms is None for item in result.items)
    assert result.correct_items == 8 and result.wrong_items == 12


def test_attempt_history_masks_and_restores_without_writing_original():
    database = AsyncSQLiteDB()
    try:
        _seed_question(database)
        _seed_session(database)
        _seed_attempt(database, attempt_id=1, duration_ms=9000, session_id=10, session_item_id=100)
        _seed_attempt(database, attempt_id=2, duration_ms=0)
        database.session.execute(
            sa
            .update(QbPracticeSession)
            .where(QbPracticeSession.id == 10)
            .values(source_snapshot={'origin': EXTERNAL_PRACTICE_ORIGIN, 'exclude_source_timing': True})
        )

        async def read():
            return await question_attempt_dao.get_wrong_answer_history(database, user_id=7, question_id=1)

        assert [row['duration_ms'] for row in asyncio.run(read())] == [0, None]
        assert (
            database.session.scalar(sa.select(QbQuestionAttempt.duration_ms).where(QbQuestionAttempt.id == 1)) == 9000
        )
        database.session.execute(
            sa
            .update(QbPracticeSession)
            .where(QbPracticeSession.id == 10)
            .values(source_snapshot={'origin': EXTERNAL_PRACTICE_ORIGIN, 'exclude_source_timing': False})
        )
        assert [row['duration_ms'] for row in asyncio.run(read())] == [0, 9000]
    finally:
        database.close()


def test_capture_history_cannot_restore_excluded_source_time_without_session(db, monkeypatch):
    async def run():
        await PracticeLogService.import_report(db=db, user_id=7, obj=report(exclude_source_timing=True))
        data = {
            'platform': 'fenbi',
            'source_key': report().source_key,
            'source_question_key': 'q1',
            'duration_ms': 9000,
            'response_data': 'A',
            'submitted_time': NOW.isoformat(),
        }
        original = deepcopy(data)
        event = SimpleNamespace(review_data={EXTERNAL_WRONG_KEY: data}, reviewed_time=NOW)
        monkeypatch.setattr(wrong_module.external_wrong_dao, 'get_events', AsyncMock(return_value=[event]))
        rows = await wrong_module.ExternalWrongService.merge_history(db, user_id=7, question_ids=[1], history=[])
        assert rows[0]['duration_ms'] is None
        assert data == original
        other = await wrong_module.ExternalWrongService.merge_history(db, user_id=8, question_ids=[1], history=[])
        assert other[0]['duration_ms'] == 9000

    asyncio.run(run())


def test_additive_migration_keeps_old_values_and_defaults_to_not_excluded():
    path = Path(__file__).parents[3] / 'alembic/versions/2026-11-23-12_00_00-e7f8a9b0c1d2_practice_timing_policy.py'
    spec = importlib.util.spec_from_file_location('timing_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        connection.exec_driver_sql(
            'CREATE TABLE gongkao_practice_log (id INTEGER PRIMARY KEY, duration_seconds INTEGER)'
        )
        connection.exec_driver_sql(
            'CREATE TABLE gongkao_practice_module (id INTEGER PRIMARY KEY, duration_seconds INTEGER)'
        )
        connection.exec_driver_sql('INSERT INTO gongkao_practice_log VALUES (1, 900)')
        module.op = Operations(MigrationContext.configure(connection))
        module.upgrade()
        assert connection.exec_driver_sql(
            'SELECT duration_seconds, exclude_source_timing, manual_duration_seconds FROM gongkao_practice_log'
        ).one() == (900, 0, None)
        assert 'manual_duration_seconds' in {
            column['name'] for column in sa.inspect(connection).get_columns('gongkao_practice_module')
        }
    engine.dispose()
