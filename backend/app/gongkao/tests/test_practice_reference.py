import asyncio

from copy import deepcopy
from datetime import date, timedelta
from typing import Any

import pytest

from pydantic import ValidationError
from sqlalchemy import select

from backend.app.gongkao.schema.practice_log import ImportPracticeReportParam
from backend.app.gongkao.service.practice_log_service import PracticeLogService
from backend.app.gongkao.service.practice_reference_service import (
    PracticeReferenceService,
    analyze_reference_rows,
    compare_windows,
    reference_probability,
)
from backend.app.gongkao.tests.test_imported_practice import import_report, payload
from backend.app.question_bank_v2.model.practice import QbPracticeSession
from backend.app.question_bank_v2.schema.platform_reference import PlatformQuestionReference

CAPTURED = '2026-11-18T09:18:40.810Z'
pytest_plugins = ('backend.app.gongkao.tests.test_imported_practice',)


def with_reference(data: dict[str, Any] | None = None) -> dict[str, Any]:
    value = deepcopy(data or payload())
    value['platform_reference'] = {
        'captured_at': CAPTURED,
        'difficulty_raw': 5,
        'average_score': 60.3,
        'beat_rate_percent': 88.3,
        'total_user_raw': 0,
    }
    for q in value['questions'] or []:
        q['platform_reference'] = {
            'captured_at': CAPTURED,
            'correct_ratio_percent': [0, 34.380708965711065, 100][q['position'] - 1],
            'total_count_raw': 227712,
            'wrong_count_raw': 0,
        }
    return value


def row(
    day: str,
    key: str,
    status: str = 'correct',
    p: Any = 50,
    module: str = '数量关系',
    content_hash: str | None = 'same',
) -> dict[str, Any]:
    return {
        'date': date.fromisoformat(day),
        'record_id': int(day[-2:]),
        'source_question_key': key,
        'content_hash': content_hash,
        'status': status,
        'module_path': [module],
        'question_type': 'single_choice',
        'platform_reference': {'version': 'fenbi-global-v1', 'captured_at': CAPTURED, 'correct_ratio_percent': p},
    }


def test_new_snapshots_keep_zero_precision_and_freeze_on_repeat(db: Any) -> None:
    async def run() -> None:
        data = with_reference()
        result = await import_report(db, data)
        detail = await PracticeLogService.get_question_details(db=db, user_id=7, pk=result.record.id)
        assert detail.source_summary['platform_reference']['difficulty_raw'] == 5
        assert detail.source_summary['platform_reference']['captured_at'] == '2026-11-18T09:18:40.810000+00:00'
        assert detail.source_summary['platform_reference']['total_user_raw'] == 0
        assert [q.platform_reference.correct_ratio_percent for q in detail.items] == [0, 34.380708965711065, 100]
        changed = with_reference()
        changed['platform_reference']['average_score'] = 99
        for q in changed['questions']:
            q['platform_reference']['correct_ratio_percent'] = 99
        retry = await import_report(db, changed)
        assert retry.practice.supplemented_questions == 0
        after = await PracticeLogService.get_question_details(db=db, user_id=7, pk=result.record.id)
        assert after.source_summary == detail.source_summary
        assert [q.platform_reference for q in after.items] == [q.platform_reference for q in detail.items]

    asyncio.run(run())


@pytest.mark.parametrize('summary_only', [False, True])
def test_legacy_reports_never_backfill_even_when_first_archiving_questions(db: Any, *, summary_only: bool) -> None:
    async def run() -> None:
        original = payload()
        if summary_only:
            original['questions'] = None
        first = await import_report(db, original)
        if not summary_only:
            session = db.session.scalars(select(QbPracticeSession)).one()
            snapshot = dict(session.source_snapshot)
            snapshot.pop('reference_policy')
            session.source_snapshot = snapshot
            await db.flush()
        await import_report(db, with_reference())
        detail = await PracticeLogService.get_question_details(db=db, user_id=7, pk=first.record.id)
        assert detail.source_summary.get('platform_reference') is None
        assert all(q.platform_reference is None for q in detail.items)

    asyncio.run(run())


def test_sql_query_uses_actual_snapshots_user_subject_mode_and_deleted_scope(db: Any) -> None:
    async def run() -> None:
        await import_report(db, with_reference())
        await import_report(db, with_reference(), user_id=8)
        kwargs = {
            'db': db,
            'user_id': 7,
            'subject_name': '行测',
            'material_type': 'exam',
            'start_date': date(2026, 10, 19),
            'end_date': date(2026, 10, 20),
        }
        data = await PracticeReferenceService.get_trends(**kwargs)
        assert data.record_count == data.eligible_records == 1
        assert data.points[0].total_questions == 3
        assert data.points[0].comparable_questions == 3
        assert data.points[1].raw_accuracy_percent is None
        assert data.points[0].platform_accuracy_percent == round((0 + 34.380708965711065 + 100) / 3, 4)
        for changes in ({'user_id': 999}, {'subject_name': '申论'}, {'material_type': 'special'}):
            empty = await PracticeReferenceService.get_trends(**{**kwargs, **changes})
            assert empty.record_count == 0
        data = await PracticeReferenceService.get_trends(**{**kwargs, 'module_name': '其他'})
        assert all(p.total_questions == 0 for p in data.points)

    asyncio.run(run())


def test_actual_meta_units_do_not_use_anomalous_counts_as_weights() -> None:
    a = row('2026-11-01', 'a', p=51.73736595255701)
    a['platform_reference'].update(total_count_raw=288051, wrong_count_raw=0)
    b = row('2026-11-01', 'b', status='wrong', p=34.380708965711065)
    b['platform_reference'].update(total_count_raw=1, wrong_count_raw=0)
    points, _, _ = analyze_reference_rows([a, b], start_date=a['date'], end_date=a['date'])
    assert points[0]['platform_accuracy_percent'] == round((51.73736595255701 + 34.380708965711065) / 2, 4)
    assert points[0]['reference_gap_pp'] == round(50 - (51.73736595255701 + 34.380708965711065) / 2, 4)


def test_duplicates_conflicts_revisions_missing_identity_and_low_coverage_are_conservative() -> None:
    rows = [
        row('2026-11-01', 'a'),
        row('2026-11-01', 'a'),
        row('2026-11-01', 'b'),
        row('2026-11-01', 'b', 'wrong'),
        row('2026-11-01', 'c', content_hash=None),
    ]
    points, comparison, _ = analyze_reference_rows(rows, start_date=date(2026, 11, 1), end_date=date(2026, 11, 2))
    assert points[0]['duplicate_attempts'] == 2
    assert points[0]['conflicting_questions'] == 1
    assert points[0]['reference_coverage_percent'] == round(100 / 3, 4)
    assert points[0]['reference_gap_pp'] is None
    assert points[1]['reference_gap_pp'] is None
    assert comparison.status == 'insufficient'
    revised = [row('2026-11-01', 'a'), row('2026-11-01', 'a', content_hash='revised')]
    p, _, _ = analyze_reference_rows(revised, start_date=date(2026, 11, 1), end_date=date(2026, 11, 1))
    assert p[0]['comparable_questions'] == 2


@pytest.mark.parametrize('bad', [None, True, '51', -1, 101, float('nan'), float('inf')])
def test_invalid_reference_never_becomes_zero(bad: Any) -> None:
    assert reference_probability(row('2026-11-01', 'a', p=bad)) is None


@pytest.mark.parametrize('bad', [-1, 101, float('nan')])
def test_schema_rejects_invalid_statistics(bad: Any) -> None:
    with pytest.raises(ValidationError):
        PlatformQuestionReference(captured_at=CAPTURED, correct_ratio_percent=bad)
    with pytest.raises(ValidationError):
        PlatformQuestionReference(captured_at='2026-11-18T09:18:40', correct_ratio_percent=50)


def comparison_rows(*, improvement: bool = False) -> list[dict[str, Any]]:
    rows = []
    for current, first in ((False, date(2026, 10, 1)), (True, date(2026, 11, 1))):
        for day in range(10):
            for i in range(20):
                # 前后模块构成大幅变化，同模块内表现不变时固定权重差应为0。
                easy = i < (4 if current else 16)
                r = row(
                    (first + timedelta(days=day)).isoformat(),
                    f'{current}:{day}:{i}',
                    status='correct' if easy or (improvement and current) else 'wrong',
                    p=80 if easy else 20,
                    module='易模块' if easy else '难模块',
                )
                r.update(
                    identity=(r['source_question_key'], 'same'),
                    p=(80 if easy else 20) / 100,
                    y=int(r['status'] == 'correct'),
                )
                rows.append(r)
    return rows


def test_fixed_composition_removes_simpson_effect_and_bootstrap_is_reproducible() -> None:
    rows = comparison_rows()
    result = compare_windows(rows, date(2026, 11, 18))
    assert result.change_pp == 0
    assert result.status == 'uncertain'
    assert result.previous_support_percent == result.current_support_percent == 100
    assert result.model_dump() == compare_windows(rows, date(2026, 11, 18)).model_dump()
    improved = compare_windows(comparison_rows(improvement=True), date(2026, 11, 18))
    assert improved.change_pp > 0 and improved.interval_low_pp > 0
    assert improved.status == 'reference_up'


def test_nonoverlapping_windows_and_cross_day_repeats_do_not_make_progress() -> None:
    rows = comparison_rows(improvement=True)
    for r in rows:
        if r['date'].month == 11:
            r['module_path'] = ['新模块']
    assert compare_windows(rows, date(2026, 11, 18)).status == 'insufficient'
    repeated = [row('2026-10-10', 'same'), row('2026-11-10', 'same')]
    points, result, _ = analyze_reference_rows(repeated, start_date=date(2026, 10, 1), end_date=date(2026, 11, 18))
    assert result.previous_questions == 1 and result.current_questions == 0
    assert points[40]['observed_repeat_questions'] == 1


def test_platform_summary_without_questions_cannot_be_silently_dropped() -> None:
    with pytest.raises(ValidationError, match='随逐题'):
        ImportPracticeReportParam.model_validate(with_reference(payload(questions=None)))
