"""仅验证新增趋势事实/契约及两处掌握写入，不连接外部数据库。"""

import importlib.util
import json

from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa

from alembic.migration import MigrationContext
from alembic.operations import Operations

from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.crud.crud_wrong_trend import wrong_trend_dao
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.model.wrong_trend import QbWrongMasteryEvent, QbWrongTrendCoverage
from backend.app.question_bank_v2.schema.review import UpdateWrongStateParam
from backend.app.question_bank_v2.service.review_schedule_service import ReviewScheduleService, review_schedule_service
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.app.question_bank_v2.service.wrong_trend_service import WrongTrendService
from backend.app.question_bank_v2.tests.test_wrong_domain_scope_sqlite import CrossDomainBrowseDB
from backend.common.exception import errors
from backend.utils.timezone import timezone


class LocalDB:
    def __init__(self) -> None:
        self.fixture = CrossDomainBrowseDB()
        raw = self.fixture.connection
        raw.executescript("""
            CREATE TABLE qbank_v2_question_attempt (
                id INTEGER, user_id INTEGER, question_id INTEGER, is_correct BOOLEAN,
                response_data TEXT, submitted_time TEXT, deleted INTEGER DEFAULT 0
            );
            CREATE TABLE qbank_v2_wrong_mastery_event (
                id INTEGER, user_id INTEGER, question_id INTEGER, wrong_state_id INTEGER,
                occurred_time TEXT, deleted INTEGER DEFAULT 0
            );
            CREATE TABLE qbank_v2_wrong_trend_coverage (
                id INTEGER, started_time TEXT, deleted INTEGER DEFAULT 0
            );
        """)
        raw.commit()
        self.engine = sa.create_engine('sqlite://', creator=lambda: raw)
        self.connection = self.engine.connect()

    def get_bind(self) -> sa.Engine:
        return self.engine

    async def execute(self, statement: Any) -> Any:
        return self.connection.execute(statement)

    async def scalar(self, statement: Any) -> Any:
        return self.connection.scalar(statement)

    def attempt(
        self,
        question: int,
        when: str,
        *,
        user: int = 77,
        correct: bool = False,
        mode: str | None = None,
        deleted: int = 0,
    ) -> None:
        self.connection.execute(
            sa.text('INSERT INTO qbank_v2_question_attempt VALUES (1,:user,:question,:correct,:data,:when,:deleted)'),
            {
                'user': user,
                'question': question,
                'correct': correct,
                'data': json.dumps({'mode': mode}),
                'when': when,
                'deleted': deleted,
            },
        )

    def review(
        self,
        question: int,
        state: int,
        when: str,
        *,
        kind: str = 'review',
        user: int = 77,
        legacy: bool = False,
        deleted: int = 0,
    ) -> None:
        self.connection.execute(
            sa.text(
                'INSERT INTO qbank_v2_question_review VALUES (1,:user,:question,:state,:kind,:data,:when,:deleted)'
            ),
            {
                'user': user,
                'question': question,
                'state': state,
                'kind': kind,
                'data': json.dumps({'external_wrong': {'legacy_initial': legacy}}),
                'when': when,
                'deleted': deleted,
            },
        )

    def mastered(self, question: int, state: int, when: str, *, user: int = 77) -> None:
        self.connection.execute(
            sa.text('INSERT INTO qbank_v2_wrong_mastery_event VALUES (1,:user,:question,:state,:when,0)'),
            {'user': user, 'question': question, 'state': state, 'when': when},
        )

    def close(self) -> None:
        self.connection.close()
        self.engine.dispose()


@pytest.fixture
def db() -> Iterator[LocalDB]:
    local = LocalDB()
    yield local
    local.close()


async def counts(db: LocalDB, domain: list[int] | None = None) -> dict[str, dict[str, int | None]]:
    start = datetime(2026, 11, 17, tzinfo=timezone.tz_info)
    return await wrong_trend_dao.daily_counts(
        db,
        user_id=77,
        start=start,
        end=start + timedelta(days=2),
        today_start=start + timedelta(days=1),
        today_end=start + timedelta(days=2),
        domain_category_ids=domain,
    )


async def test_real_daily_union_deduplicates_each_metric_and_local_midnight(db: LocalDB) -> None:
    midnight = '2026-11-18 00:00:00.000000'
    db.attempt(201, '2026-11-17 23:59:59.000000')
    db.attempt(201, midnight)
    db.attempt(201, '2026-11-18 12:00:00.000000')
    db.review(201, 101, midnight, kind='capture')  # 同日录入和答错仍只计一题
    db.review(201, 101, midnight)
    db.review(201, 101, '2026-11-18 13:00:00.000000')
    db.mastered(201, 101, midnight)
    db.mastered(201, 101, '2026-11-18 14:00:00.000000')
    db.attempt(202, midnight, correct=True)
    db.attempt(203, midnight, mode='memorize')
    db.attempt(204, midnight, deleted=1)
    db.review(210, 108, '2026-11-16 12:00:00.000000', kind='capture', legacy=True)
    db.review(202, 102, midnight, deleted=1)
    db.attempt(201, '2026-11-19 00:00:00.000000')  # 结束日之后
    result = await counts(db, [1400])
    assert result == {
        'wrong': {'2026-11-17': 1, '2026-11-18': 1},
        'reviewed': {'2026-11-18': 1},
        'mastered': {'2026-11-18': 1},
    }
    # 重新记错/暂停不改变已记录的掌握事实。
    db.connection.execute(
        sa.text("UPDATE qbank_v2_wrong_question_state SET status='suspended', resolved_time=NULL WHERE id=101")
    )
    assert (await counts(db, [1400]))['mastered'] == result['mastered']
    db.connection.execute(sa.text('UPDATE qbank_v2_wrong_question_state SET deleted=101 WHERE id=101'))
    assert await counts(db, [1400]) == {'wrong': {}, 'reviewed': {}, 'mastered': {}}


@pytest.mark.parametrize(('domain', 'total'), [([1400], 3), ([1], 3), (None, 6), ([], 0)])
async def test_scoped_counts_use_bank_recorded_domain_and_legacy_external_only(
    db: LocalDB, domain: list[int] | None, total: int
) -> None:
    when = '2026-11-18 12:00:00.000000'
    for state, question, user in [
        (101, 201, 77),
        (104, 205, 77),
        (107, 209, 77),
        (108, 210, 77),
        (109, 211, 77),
        (110, 212, 77),
        (112, 214, 7),
        (113, 215, 77),
    ]:
        db.attempt(question, when, user=user)
        db.review(question, state, when, user=user)
        db.mastered(question, state, when, user=user)
    result = await counts(db, domain)
    for metric in result:
        assert result[metric].get('2026-11-18', 0) == total


async def test_service_keeps_today_independent_and_old_mastery_unknown(
    db: LocalDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = datetime(2026, 11, 18, 12, tzinfo=timezone.tz_info)
    monkeypatch.setattr(timezone, 'now', lambda: now)
    monkeypatch.setattr(WrongReviewService, 'resolve_domain_scope', AsyncMock(return_value=[1400]))
    db.connection.execute(
        sa.text("INSERT INTO qbank_v2_wrong_trend_coverage VALUES (1,'2026-11-17 10:00:00.000000',0)")
    )
    db.attempt(201, '2026-11-18 00:00:00.000000')
    db.mastered(201, 101, '2026-11-18 00:00:00.000000')
    result = await WrongTrendService.get_trend(
        db=db, user_id=77, start_date=date(2026, 11, 16), end_date=date(2026, 11, 17)
    )
    assert result.today.wrong == result.today.mastered == 1
    assert result.mastery_known_from == date(2026, 11, 18)
    assert [point.mastered for point in result.points] == [None, None]
    assert [point.wrong for point in result.points] == [0, 0]
    result = await WrongTrendService.get_trend(db=db, user_id=77, days=30)
    assert len(result.points) == 30
    assert result.points[-1] == result.today
    db.connection.execute(sa.text('DELETE FROM qbank_v2_wrong_trend_coverage'))
    result = await WrongTrendService.get_trend(db=db, user_id=77)
    assert result.today.mastered is None and result.mastery_known_from is None


async def test_legacy_initial_capture_marks_incomplete_wrong_day_unknown(db: LocalDB) -> None:
    db.review(210, 108, '2026-11-17 12:00:00.000000', kind='capture', legacy=True)
    db.attempt(201, '2026-11-17 13:00:00.000000')
    assert (await counts(db, [1400]))['wrong']['2026-11-17'] is None


async def test_later_recapture_cannot_make_missing_initial_day_a_known_zero(db: LocalDB) -> None:
    db.connection.execute(
        sa.text("UPDATE qbank_v2_wrong_question_state SET created_time='2026-11-17 12:00:00.000000' WHERE id=108")
    )
    db.review(210, 108, '2026-11-18 12:00:00.000000', kind='capture')
    result = await counts(db, [1400])
    assert result['wrong']['2026-11-17'] is None
    assert result['wrong']['2026-11-18'] == 1


@pytest.mark.parametrize(
    ('start', 'end'),
    [
        (date(2026, 11, 19), date(2026, 11, 18)),
        (date(2026, 11, 18), date(2026, 11, 19)),
        (date(2025, 11, 16), date(2026, 11, 18)),
    ],
)
async def test_invalid_range_rejected_before_database(start: date, end: date, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(timezone, 'now', lambda: datetime(2026, 11, 18, tzinfo=timezone.tz_info))
    with pytest.raises(errors.RequestError):
        await WrongTrendService.get_trend(db=MagicMock(), user_id=77, start_date=start, end_date=end)


def state() -> QbWrongQuestionState:
    item = QbWrongQuestionState(user_id=77, question_id=201, created_by=77, correct_streak=2)
    item.id = 101
    return item


async def test_automatic_mastery_records_once_and_retains_ledger_after_rewrong(monkeypatch: pytest.MonkeyPatch) -> None:
    item = state()
    db = MagicMock()
    recorded = []
    db.add.side_effect = recorded.append
    monkeypatch.setattr(wrong_question_state_dao, 'get_by_question', AsyncMock(return_value=item))
    monkeypatch.setattr(ReviewScheduleService, '_advance_schedule', lambda **_: None)
    attempt = SimpleNamespace(
        id=1,
        user_id=77,
        question_id=201,
        submitted_time=timezone.now(),
        is_correct=True,
        response_data={},
        duration_ms=1000,
    )
    session_item = SimpleNamespace(bank_item_id=None, display_config={})
    mastery = SimpleNamespace(state='learning')

    async def apply() -> None:
        await ReviewScheduleService._sync_wrong_state(
            db=db, attempt=attempt, session_item=session_item, mastery=mastery, resolve_threshold=3
        )

    await apply()
    await apply()
    assert len(recorded) == 1 and recorded[0].source_attempt_id == 1
    assert item.status == 'resolved'
    attempt.id, attempt.is_correct = 2, False
    await apply()
    assert item.resolved_time is None and item.status == 'active'
    assert len(recorded) == 1
    attempt.id, attempt.is_correct = 3, True
    item.correct_streak = 2
    await apply()
    assert len(recorded) == 2 and recorded[1].source_attempt_id == 3


@pytest.mark.parametrize('guard', ['memorize', 'newer', 'suspended'])
async def test_automatic_guards_do_not_manufacture_mastery_events(monkeypatch: pytest.MonkeyPatch, guard: str) -> None:
    item = state()
    now = timezone.now()
    if guard == 'newer':
        item.fsrs_data = {'last_review': (now + timedelta(days=1)).isoformat()}
    if guard == 'suspended':
        item.status = 'suspended'
    monkeypatch.setattr(wrong_question_state_dao, 'get_by_question', AsyncMock(return_value=item))
    db = MagicMock()
    attempt = SimpleNamespace(
        id=1,
        user_id=77,
        question_id=201,
        submitted_time=now,
        is_correct=True,
        response_data={'mode': 'memorize'} if guard == 'memorize' else {},
        duration_ms=0,
    )
    await ReviewScheduleService._sync_wrong_state(
        db=db,
        attempt=attempt,
        session_item=SimpleNamespace(bank_item_id=None, display_config={}),
        mastery=SimpleNamespace(state='learning'),
        resolve_threshold=3,
    )
    db.add.assert_not_called()


async def test_manual_resolve_repeat_suspend_and_reopen_only_count_real_new_mastery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.question_bank_v2.service import wrong_review_service as module

    item = state()
    mastery = SimpleNamespace(state='learning')
    monkeypatch.setattr(module, 'lock_practice_user', AsyncMock())
    monkeypatch.setattr(wrong_question_state_dao, 'get', AsyncMock(return_value=item))
    monkeypatch.setattr(review_schedule_service, 'ensure_mastery', AsyncMock(return_value=mastery))
    monkeypatch.setattr(WrongReviewService, '_get_wrong_item', AsyncMock(return_value={}))
    db = MagicMock()
    db.flush = AsyncMock()

    async def action(value: str) -> None:
        await WrongReviewService.update_state(
            db=db, user_id=77, wrong_state_id=101, obj=UpdateWrongStateParam(action=value)
        )

    await action('resolve')
    first_time = item.resolved_time
    await action('resolve')
    await action('suspend')
    await action('resolve')
    assert db.add.call_count == 1 and item.resolved_time == first_time
    await action('reopen')
    await action('resolve')
    assert db.add.call_count == 2
    assert db.add.call_args.args[0].source == 'manual'


def test_migration_matches_model_and_does_not_backfill_existing_mastered_rows() -> None:
    path = Path(__file__).parents[3] / 'alembic/versions/2026-11-18-16_00_00-d6e7f8a9b0c1_wrong_trend_events.py'
    # tests -> question_bank_v2 -> app -> backend
    spec = importlib.util.spec_from_file_location('trend_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine('sqlite://')
    with engine.begin() as connection:
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = sa.inspect(connection)
        for model in [QbWrongMasteryEvent, QbWrongTrendCoverage]:
            actual = {column['name'] for column in inspector.get_columns(model.__tablename__)}
            assert actual == set(model.__table__.columns.keys())
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM qbank_v2_wrong_mastery_event')) == 0
        assert connection.scalar(sa.text('SELECT COUNT(*) FROM qbank_v2_wrong_trend_coverage')) == 1
        migration.downgrade()
        assert 'qbank_v2_wrong_mastery_event' not in sa.inspect(connection).get_table_names()
    engine.dispose()


def test_trend_route_registered_before_id_route_and_has_auth() -> None:
    from backend.app.question_bank_v2.api.v1.review import router

    routes = [route.path for route in router.routes]
    assert routes.index('/trend') < routes.index('/{wrong_state_id}')
    assert router.dependencies
