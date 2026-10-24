import asyncio

from contextlib import asynccontextmanager
from datetime import date
from typing import Any

import pytest

from pydantic import ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from backend.app.gongkao.model.practice_log import GongkaoPracticeLog, GongkaoPracticeModule
from backend.app.gongkao.schema.practice_log import ImportPracticeReportParam, UpdatePracticeLogParam
from backend.app.gongkao.service.practice_log_service import PracticeLogService


def report(**updates: Any) -> ImportPracticeReportParam:
    data = {
        'source_key': '1_1_3u7uapv',
        'source_url': 'https://spa.fenbi.com/ti/exam/solution/1_1_3u7uapv?routecs=xingce',
        'material_title': '粉笔三级报告回归',
        'practiced_at': '2026-10-19',
        'total_questions': 20,
        'correct_count': 8,
        'duration_seconds': 478,
        'unanswered_count': 0,
        'source_updated_at': '2026-10-19T02:57:14.726Z',
        'time_source': 'history_updated',
        'score': 40,
        'full_score': 100,
        'modules': [
            {
                'module_name': '政治理论',
                'total_questions': 20,
                'correct_count': 8,
                'duration_seconds': 478,
                'children': [
                    {'module_name': '马克思主义', 'total_questions': 2, 'correct_count': 1, 'duration_seconds': 33},
                    {'module_name': '新思想', 'total_questions': 18, 'correct_count': 7, 'duration_seconds': 445},
                    {'module_name': '时事政治', 'total_questions': 18, 'correct_count': 7, 'duration_seconds': 445},
                ],
            }
        ],
        **updates,
    }
    return ImportPracticeReportParam.model_validate(data)


class MemorySession:
    """用 SQLite 实际执行 ORM SQL，仅将同步驱动适配为异步测试接口"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.next_id = 1

    def add(self, obj: Any) -> None:
        # SQLite 的 BIGINT 主键没有 PostgreSQL sequence 行为。
        if getattr(obj, 'id', None) is None:
            obj.id = self.next_id
            self.next_id += 1
        self.session.add(obj)

    async def flush(self) -> None:
        self.session.flush()

    async def execute(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self.session.execute(statement, *args, **kwargs)

    async def scalars(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self.session.scalars(statement, *args, **kwargs)

    async def scalar(self, statement: Any, *args: Any, **kwargs: Any) -> Any:
        return self.session.scalar(statement, *args, **kwargs)

    @asynccontextmanager
    async def begin_nested(self) -> Any:
        with self.session.begin_nested():
            yield


@pytest.fixture
def db() -> Any:
    engine = create_engine('sqlite://')
    event.listen(engine, 'connect', lambda connection, _record: connection.execute('PRAGMA foreign_keys=ON'))
    GongkaoPracticeLog.__table__.create(engine)
    GongkaoPracticeModule.__table__.create(engine)
    with Session(engine, expire_on_commit=False) as session:
        yield MemorySession(session)
    engine.dispose()


def test_import_persists_overlapping_children_without_inflating_totals(db: MemorySession) -> None:
    result = asyncio.run(PracticeLogService.import_report(db=db, user_id=7, obj=report()))
    assert result.created is True
    assert result.record.total_questions == 20
    assert result.record.duration_seconds == 478
    assert len(result.record.modules) == 1
    children = result.record.modules[0].children
    assert [m.total_questions for m in children] == [2, 18, 18]
    assert len({m.seq_no for m in [result.record.modules[0], *children]}) == 4
    persisted = db.session.scalars(select(GongkaoPracticeModule)).all()
    assert all(m.parent_id == result.record.modules[0].id for m in persisted if m.parent_id is not None)


def test_duplicate_import_preserves_user_edits_and_is_scoped_to_user(db: MemorySession) -> None:
    async def run() -> None:
        first = await PracticeLogService.import_report(db=db, user_id=7, obj=report())
        edited = await PracticeLogService.update(
            db=db,
            user_id=7,
            pk=first.record.id,
            obj=UpdatePracticeLogParam(material_title='我修改的标题', practiced_at=date(2026, 10, 18)),
        )
        assert edited.time_source == 'manual'
        retry = await PracticeLogService.import_report(db=db, user_id=7, obj=report())
        assert retry.created is False
        assert retry.record.material_title == '我修改的标题'
        assert retry.record.practiced_at == date(2026, 10, 18)
        other = await PracticeLogService.import_report(db=db, user_id=8, obj=report())
        assert other.created is True
        assert other.record.id != first.record.id

    asyncio.run(run())


def test_comparisons_preserve_multiple_attempts_on_one_day_and_parent_path(db: MemorySession) -> None:
    async def run() -> None:
        await PracticeLogService.import_report(db=db, user_id=7, obj=report())
        await PracticeLogService.import_report(
            db=db,
            user_id=7,
            obj=report(
                source_key='1_1_second',
                source_url='https://spa.fenbi.com/ti/exam/solution/1_1_second',
            ),
        )
        await PracticeLogService.import_report(db=db, user_id=8, obj=report())
        data = await PracticeLogService.get_comparisons(db=db, user_id=7)
        assert data['record_count'] == 2
        series = {tuple(s['path']): s for s in data['series']}
        root = series['行测',]['points']
        assert len(root) == 2
        assert root[0]['record_id'] != root[1]['record_id']
        assert root[0]['practiced_at'] == root[1]['practiced_at']
        assert all(p['total_questions'] == 20 and p['duration_seconds'] == 478 for p in root)
        assert len(series['行测', '政治理论', '新思想']['points']) == 2
        assert series['行测', '政治理论']['level'] == 'module'
        assert (await PracticeLogService.get_comparisons(db=db, user_id=7, start_date=date(2026, 10, 20)))[
            'series'
        ] == []

    asyncio.run(run())


@pytest.mark.parametrize(
    'changes',
    [
        {'correct_count': 21},
        {'source_url': 'https://example.com/report'},
        {'source_updated_at': '2026-10-19T10:57:14'},
        {'total_questions': 21},
    ],
)
def test_invalid_reports_are_rejected(changes: dict) -> None:
    with pytest.raises(ValidationError):
        report(**changes)


def test_fourth_level_is_rejected() -> None:
    payload = report().model_dump()
    payload['modules'][0]['children'][0]['children'] = []
    with pytest.raises(ValidationError):
        ImportPracticeReportParam.model_validate(payload)
