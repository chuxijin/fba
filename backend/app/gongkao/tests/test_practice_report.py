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
from backend.app.question_bank_v2.model.practice import QbPracticeSession


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
    QbPracticeSession.__table__.create(engine)
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


def test_fifth_level_is_rejected() -> None:
    payload = report().model_dump()
    payload['modules'][0]['children'][0]['children'] = [
        {'module_name': '不支持的下一级', 'total_questions': 1, 'correct_count': 0, 'children': []}
    ]
    with pytest.raises(ValidationError):
        ImportPracticeReportParam.model_validate(payload)


def quantity_report(*, with_topics: bool = True) -> ImportPracticeReportParam:
    topics = [
        {'module_name': '行程问题', 'total_questions': 4, 'correct_count': 3, 'duration_seconds': 400},
        {'module_name': '工程问题', 'total_questions': 3, 'correct_count': 3, 'duration_seconds': 200},
        {'module_name': '概率问题', 'total_questions': 3, 'correct_count': 3, 'duration_seconds': None},
        # 知识点可能重叠，不能以细项之和覆盖父级统计。
        {'module_name': '应用题', 'total_questions': 6, 'correct_count': 5, 'duration_seconds': 500},
    ]
    math = {
        'module_name': '数学运算',
        'total_questions': 10,
        'correct_count': 9,
        'duration_seconds': 932,
        'children': topics if with_topics else [],
    }
    return report(
        total_questions=10,
        correct_count=9,
        duration_seconds=932,
        modules=[
            {
                'module_name': '数量关系',
                'total_questions': 10,
                'correct_count': 9,
                'duration_seconds': 932,
                'children': [math],
            }
        ],
    )


def test_quantity_topics_persist_round_trip_and_compare_by_full_path(db: MemorySession) -> None:
    async def run() -> None:
        result = await PracticeLogService.import_report(db=db, user_id=7, obj=quantity_report())
        record = await PracticeLogService.get(db=db, user_id=7, pk=result.record.id)
        root = record.modules[0]
        math = root.children[0]
        assert root.total_questions == math.total_questions == 10
        assert root.duration_seconds == math.duration_seconds == 932
        assert [m.module_name for m in math.children] == ['行程问题', '工程问题', '概率问题', '应用题']
        persisted = db.session.scalars(select(GongkaoPracticeModule)).all()
        assert len({m.seq_no for m in persisted}) == 6
        assert all(m.parent_id == math.id for m in persisted if m.module_name.endswith('问题'))
        data = await PracticeLogService.get_comparisons(db=db, user_id=7)
        series = {tuple(s['path']): s for s in data['series']}
        travel = series['行测', '数量关系', '数学运算', '行程问题']
        assert travel['level'] == 'topic'
        assert travel['points'][0]['accuracy'] == 75
        assert travel['points'][0]['avg_seconds'] == 100
        assert series['行测', '数量关系', '数学运算', '概率问题']['points'][0]['avg_seconds'] is None
        assert series['行测', '数量关系']['points'][0]['total_questions'] == 10
        # 手动保存也必须保留第四级，而非读取后静默丢失。
        updated = await PracticeLogService.update(
            db=db,
            user_id=7,
            pk=record.id,
            obj=UpdatePracticeLogParam(modules=quantity_report().model_dump()['modules']),
        )
        assert len(updated.modules[0].children[0].children) == 4

    asyncio.run(run())


def test_reimport_supplements_missing_math_topics_without_overwriting_edits(db: MemorySession) -> None:
    async def run() -> None:
        first = await PracticeLogService.import_report(db=db, user_id=7, obj=quantity_report(with_topics=False))
        await PracticeLogService.update(
            db=db,
            user_id=7,
            pk=first.record.id,
            obj=UpdatePracticeLogParam(material_title='校正标题', practiced_at=date(2026, 10, 18)),
        )
        enriched = await PracticeLogService.import_report(db=db, user_id=7, obj=quantity_report())
        assert enriched.created is False
        assert enriched.enriched is True
        assert enriched.record.id == first.record.id
        assert enriched.record.material_title == '校正标题'
        assert enriched.record.practiced_at == date(2026, 10, 18)
        assert enriched.record.time_source == 'manual'
        assert len(enriched.record.modules[0].children[0].children) == 4
        retry = await PracticeLogService.import_report(db=db, user_id=7, obj=quantity_report())
        assert retry.enriched is False
        assert len(db.session.scalars(select(GongkaoPracticeModule)).all()) == 6
        assert len(db.session.scalars(select(GongkaoPracticeLog)).all()) == 1

    asyncio.run(run())


@pytest.mark.parametrize('edited_node', ['root', 'math', 'topics'])
def test_reimport_does_not_replace_edited_statistics_or_existing_topics(db: MemorySession, edited_node: str) -> None:
    async def run() -> None:
        source = quantity_report(with_topics=False)
        first = await PracticeLogService.import_report(db=db, user_id=7, obj=source)
        modules = source.model_dump()['modules']
        if edited_node == 'topics':
            modules[0]['children'][0]['children'] = [
                {'module_name': '我的自定义题型', 'total_questions': 1, 'correct_count': 1}
            ]
        else:
            node = modules[0] if edited_node == 'root' else modules[0]['children'][0]
            node['correct_count'] = 8
        await PracticeLogService.update(
            db=db, user_id=7, pk=first.record.id, obj=UpdatePracticeLogParam(modules=modules)
        )
        result = await PracticeLogService.import_report(db=db, user_id=7, obj=quantity_report())
        assert result.enriched is False
        math = result.record.modules[0].children[0]
        assert [m.module_name for m in math.children] == (['我的自定义题型'] if edited_node == 'topics' else [])
        if edited_node != 'topics':
            assert (result.record.modules[0] if edited_node == 'root' else math).correct_count == 8

    asyncio.run(run())
