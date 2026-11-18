import asyncio

from copy import deepcopy
from datetime import date
from typing import Any

import pytest

from sqlalchemy import inspect, select

from backend.app.gongkao.crud.crud_practice_log import practice_log_dao, practice_module_dao
from backend.app.gongkao.schema.practice_log import UpdatePracticeLogParam
from backend.app.gongkao.service.practice_log_service import PracticeLogService
from backend.app.gongkao.service.practice_reference_service import PracticeReferenceService
from backend.app.gongkao.tests.test_imported_practice import TABLE_MODELS, count, import_report, payload
from backend.app.gongkao.tests.test_practice_reference import CAPTURED, with_reference
from backend.app.question_bank_v2.crud.crud_external_practice import external_practice_dao
from backend.app.question_bank_v2.model.practice import QbPracticeSession, QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.service.external_wrong_service import external_wrong_service

pytest_plugins = ('backend.app.gongkao.tests.test_imported_practice',)
LATER = '2026-11-19T08:00:00+00:00'


def later(data: dict | None = None) -> dict:
    value = with_reference(data)
    value['platform_reference']['captured_at'] = LATER
    for question in value['questions'] or []:
        question['platform_reference']['captured_at'] = LATER
    return value


def frozen_rows(db: Any) -> dict:
    # 统计元数据只允许改会话source_snapshot和题项display_config；其余所有表字段逐一保留。
    rows = {}
    for model in TABLE_MODELS:
        fields = [c.key for c in inspect(model).columns
                  if c.key not in ({'source_snapshot', 'updated_time'} if model is QbPracticeSession
                                   else {'display_config', 'updated_time'} if model is QbPracticeSessionItem else set())]
        rows[model.__name__] = [deepcopy({name: getattr(row, name) for name in fields})
                               for row in db.session.scalars(select(model).order_by(model.id))]
    return rows


def test_statistics_only_never_calls_content_response_module_or_wrong_writers(db: Any, monkeypatch: Any) -> None:
    async def run() -> None:
        first = await import_report(db)
        before = frozen_rows(db)
        snapshots = [deepcopy(row.display_config) for row in db.session.scalars(select(QbPracticeSessionItem))]

        async def forbidden(*args: Any, **kwargs: Any) -> None:
            pytest.fail('重导不得写题目、作答、题型或错题记录')

        for name in ('ensure_question', 'supplement_content', 'save_response', 'create_item'):
            monkeypatch.setattr(external_practice_dao, name, forbidden)
        monkeypatch.setattr(external_wrong_service, 'sync_report_question', forbidden)
        monkeypatch.setattr(practice_module_dao, 'batch_create', forbidden)
        incoming = later()
        for q in incoming['questions']:
            if q['status'] != 'unanswered':
                q['response_data'] = 'B'
                q['status'] = 'correct' if q['position'] == 2 else 'wrong'
            q['duration_seconds'] = 40
            q['score'] = 0
            q['max_score'] = 0
            q['explanations'][0]['content'] = '后续解析不写回'
        incoming.update(material_title='不能覆盖', practiced_at='2026-11-19', duration_seconds=999)
        incoming['correct_count'] = incoming['modules'][0]['correct_count'] = 1
        result = await import_report(db, incoming)
        assert result.reference_supplement.questions_updated == 3
        assert result.practice is None and result.record.id == first.record.id
        assert frozen_rows(db) == before
        for old, row in zip(snapshots, db.session.scalars(select(QbPracticeSessionItem))):
            now = deepcopy(row.display_config['external_practice'])
            now['platform_reference'] = old['external_practice']['platform_reference']
            assert now == old['external_practice']

    asyncio.run(run())


def test_fill_null_fields_preserves_zero_capture_provenance_and_first_import_trend(db: Any) -> None:
    async def run() -> None:
        original = with_reference()
        original['platform_reference']['average_score'] = None
        for q in original['questions']:
            if q['position'] == 2:
                q['platform_reference']['correct_ratio_percent'] = None
            if q['position'] == 1:
                q['platform_reference']['total_count_raw'] = None
        first = await import_report(db, original)
        kwargs = dict(db=db, user_id=7, subject_name='行测', material_type='exam',
                      start_date=date(2026, 10, 19), end_date=date(2026, 10, 19))
        before = await PracticeReferenceService.get_trends(**kwargs)
        assert before.points[0].comparable_questions == 2
        incoming = later()
        incoming['platform_reference']['total_user_raw'] = 999
        for q in incoming['questions']:
            if q['position'] == 1:
                q['platform_reference'].update(correct_ratio_percent=99, total_count_raw=0, wrong_count_raw=99)
        result = await import_report(db, incoming)
        assert result.reference_supplement.report_fields_added == 1
        assert result.reference_supplement.questions_updated == 2
        detail = await PracticeLogService.get_question_details(db=db, user_id=7, pk=first.record.id)
        assert detail.items[0].platform_reference.correct_ratio_percent == 0
        assert detail.items[0].platform_reference.total_count_raw == 0
        assert detail.items[0].platform_reference.wrong_count_raw == 0
        assert detail.items[1].platform_reference.correct_ratio_percent is not None
        assert detail.source_summary['platform_reference']['total_user_raw'] == 0
        assert detail.source_summary['platform_reference_field_captured_at'] == {'average_score': LATER}
        assert detail.items[0].platform_reference_field_captured_at == {'total_count_raw': LATER}
        assert detail.items[1].platform_reference.captured_at.isoformat().startswith('2026-11-18')
        after = await PracticeReferenceService.get_trends(**kwargs)
        assert after.model_dump() == before.model_dump(), '补字段不改变首次参照或提高覆盖'
        snapshot = deepcopy(db.session.scalars(select(QbPracticeSession)).one().source_snapshot)
        configs = [deepcopy(row.display_config) for row in db.session.scalars(select(QbPracticeSessionItem))]
        retry = await import_report(db, incoming)
        assert not retry.enriched and retry.reference_supplement.questions_updated == 0
        assert db.session.scalars(select(QbPracticeSession)).one().source_snapshot == snapshot
        assert [row.display_config for row in db.session.scalars(select(QbPracticeSessionItem))] == configs

    asyncio.run(run())


@pytest.mark.parametrize('change', ['key', 'position', 'stem', 'options', 'answer', 'materials', 'path'])
def test_mismatched_question_is_skipped_while_other_statistics_are_filled(db: Any, change: str) -> None:
    async def run() -> None:
        first = await import_report(db)
        incoming = later()
        q = next(q for q in incoming['questions'] if q['position'] == 1)
        if change == 'key':
            q['source_question_key'] = 'another-key'
        elif change == 'position':
            next(other for other in incoming['questions'] if other['position'] == 2)['position'] = 1
            q['position'] = 2
        elif change == 'stem':
            q['stem'] = '修订题干'
        elif change == 'options':
            q['options'][0]['content'] = '修订选项'
        elif change == 'answer':
            q['answer']['answer_data']['correct'] = 'B'
        elif change == 'materials':
            for other in incoming['questions']:
                other['materials'][0]['content'] = '修订共同材料'
        elif change == 'path':
            q['module_path'] = ['数量关系', '数学运算', '工程问题']
        result = await import_report(db, incoming)
        expected = 3 if change == 'materials' else 2 if change == 'position' else 1
        assert result.reference_supplement.questions_skipped == expected
        assert result.reference_supplement.questions_updated == 3 - expected
        assert result.reference_supplement.warnings
        assert count(db, QbPracticeSessionItem) == 3 and count(db, QbQuestionAttempt) == 2
        detail = await PracticeLogService.get_question_details(db=db, user_id=7, pk=first.record.id)
        assert detail.items[0].stem == payload()['questions'][1]['stem']
        assert detail.items[0].platform_reference is None

    asyncio.run(run())


def test_normalized_display_difference_can_match_without_changing_content(db: Any) -> None:
    async def run() -> None:
        first = await import_report(db)
        incoming = later()
        for q in incoming['questions']:
            q['stem'] = q['stem'].replace('width="40"', 'width="80"')
        result = await import_report(db, incoming)
        assert result.reference_supplement.questions_updated == 3
        detail = await PracticeLogService.get_question_details(db=db, user_id=7, pk=first.record.id)
        assert 'width="40"' in detail.items[0].stem

    asyncio.run(run())


def test_summary_only_reimport_without_report_statistics_does_not_create_archive(db: Any) -> None:
    async def run() -> None:
        await import_report(db, payload(questions=None))
        incoming = later()
        incoming['platform_reference'] = None
        result = await import_report(db, incoming)
        assert not result.enriched
        assert result.reference_supplement.questions_skipped == 3
        assert count(db, QbPracticeSession) == count(db, QbPracticeSessionItem) == 0

    asyncio.run(run())


def test_user_edits_and_report_identity_mismatch_remain_untouched(db: Any) -> None:
    async def run() -> None:
        first = await import_report(db)
        await PracticeLogService.update(db=db,user_id=7,pk=first.record.id,
                                       obj=UpdatePracticeLogParam(material_title='我的标题', practiced_at=date(2026, 10, 18)))
        before = frozen_rows(db)
        result = await import_report(db, later())
        assert result.enriched and frozen_rows(db) == before
        assert result.record.material_title == '我的标题' and result.record.practiced_at == date(2026, 10, 18)
        bad = later()
        bad['subject_name'] = '申论'
        skipped = await import_report(db, bad)
        assert not skipped.enriched and skipped.reference_supplement.questions_skipped == 3
        assert frozen_rows(db) == before

    asyncio.run(run())


def test_missing_first_statistics_never_become_trend_samples_when_backfilled(db: Any) -> None:
    async def run() -> None:
        first = await import_report(db)
        await import_report(db, later())
        data = await PracticeReferenceService.get_trends(db=db,user_id=7,subject_name='行测',material_type='exam',
                                                        start_date=date(2026,10,19),end_date=date(2026,10,19))
        assert data.eligible_records == 1 and data.points[0].comparable_questions == 0
        assert data.latest_report_reference is None
        assert (await PracticeLogService.get_question_details(db=db,user_id=7,pk=first.record.id)).items[0].platform_reference

    asyncio.run(run())


def test_unique_source_collision_uses_statistics_only_path(db: Any, monkeypatch: Any) -> None:
    async def run() -> None:
        first = await import_report(db)
        before = frozen_rows(db)
        original = practice_log_dao.get_by_source
        calls = 0

        async def simulate_race(*args: Any, **kwargs: Any) -> Any:
            nonlocal calls
            calls += 1
            return None if calls == 1 else await original(*args, **kwargs)

        monkeypatch.setattr(practice_log_dao, 'get_by_source', simulate_race)
        result = await import_report(db, later())
        assert not result.created and result.record.id == first.record.id
        assert result.reference_supplement.questions_updated == 3
        assert frozen_rows(db) == before

    asyncio.run(run())


def test_statistics_failure_rolls_back_all_metadata(db: Any, monkeypatch: Any) -> None:
    async def run() -> None:
        await import_report(db)
        session_before = deepcopy(db.session.scalars(select(QbPracticeSession)).one().source_snapshot)
        items_before = [deepcopy(row.display_config) for row in db.session.scalars(select(QbPracticeSessionItem))]

        async def fail_flush() -> None:
            raise RuntimeError('统计保存失败')

        monkeypatch.setattr(db, 'flush', fail_flush)
        with pytest.raises(RuntimeError, match='统计保存失败'):
            await import_report(db, later())
        assert db.session.scalars(select(QbPracticeSession)).one().source_snapshot == session_before
        assert [row.display_config for row in db.session.scalars(select(QbPracticeSessionItem))] == items_before

    asyncio.run(run())
