import json
import sqlite3

from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy.dialects import sqlite

from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.schema.review import WrongQuestionFilters
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.utils.timezone import timezone


class QueryResult:
    """保留服务使用的结果接口，实际筛选和聚合交给 SQLite 执行。"""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows

    def mappings(self) -> 'QueryResult':
        return self

    def all(self) -> list[dict[str, Any]]:
        return self.rows

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None

    def one(self) -> dict[str, Any]:
        assert len(self.rows) == 1
        return self.rows[0]

    def scalar_one(self) -> Any:
        return next(iter(self.one().values()))


class BrowseDB:
    """执行真实 DAO 查询的内存数据库，不连接开发或生产环境。"""

    def __init__(self, *, check_same_thread: bool = True) -> None:
        self.connection = sqlite3.connect(':memory:', check_same_thread=check_same_thread)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript("""
            CREATE TABLE qbank_v2_question (
                id INTEGER, stem TEXT, content_format TEXT, question_type TEXT, deleted INTEGER
            );
            CREATE TABLE qbank_v2_question_explanation (
                id INTEGER, question_id INTEGER, content TEXT, explanation_type TEXT,
                is_default INTEGER, status TEXT, created_by INTEGER, updated_by INTEGER,
                created_time TEXT, updated_time TEXT, deleted INTEGER, deleted_time TEXT
            );
            CREATE TABLE qbank_v2_bank (id INTEGER);
            CREATE TABLE qbank_v2_bank_revision (id INTEGER, bank_id INTEGER, name TEXT, deleted INTEGER);
            CREATE TABLE qbank_v2_bank_section (id INTEGER, name TEXT, deleted INTEGER);
            CREATE TABLE qbank_v2_bank_item (
                id INTEGER, bank_revision_id INTEGER, question_id INTEGER, section_id INTEGER, deleted INTEGER
            );
            CREATE TABLE qbank_v2_bank_category (id INTEGER, bank_id INTEGER, category_id INTEGER, deleted INTEGER);
            CREATE TABLE qbank_v2_user_question_mastery (
                user_id INTEGER, question_id INTEGER, state TEXT, deleted INTEGER
            );
            CREATE TABLE qbank_v2_wrong_question_state (
                id INTEGER, user_id INTEGER, question_id INTEGER, source_bank_item_id INTEGER,
                entry_source TEXT, entry_metadata TEXT, status TEXT, deleted INTEGER,
                wrong_count INTEGER DEFAULT 1, correct_streak INTEGER DEFAULT 0,
                first_wrong_time TEXT, last_wrong_time TEXT, last_practice_time TEXT,
                is_pinned INTEGER DEFAULT 0, review_count INTEGER, last_reviewed_time TEXT,
                practice_level INTEGER DEFAULT 0, last_rating INTEGER, next_practice_time TEXT, resolved_time TEXT,
                created_time TEXT
            );
            INSERT INTO qbank_v2_bank VALUES (1), (2);
            INSERT INTO qbank_v2_bank_revision VALUES (1,1,'试卷甲',0), (2,2,'试卷乙',0);
            INSERT INTO qbank_v2_bank_category VALUES (1,1,1400,0), (2,2,1400,0);
            INSERT INTO qbank_v2_bank_section VALUES (1,'数量关系',0), (2,'政治理论',0);
        """)
        batch_a, batch_b = 'batch-aaaa', 'batch-bbbb'
        # 已复盘和待复盘可重叠；已掌握包含从未复盘的题。
        rows = [
            (1, 'active', 'attempt', 11, 0, None, None, 1400),
            (2, 'active', 'attempt', 12, 1, None, None, 1400),
            (3, 'active', 'import', None, 1, batch_a, ' 数量关系 ', 1400),
            (4, 'active', 'import', None, 2, batch_b, '数量关系', 1400),
            (5, 'resolved', 'attempt', 15, 0, None, None, 1400),
            (6, 'resolved', 'import', None, 1, batch_a, '数量关系', 1400),
            (7, 'active', 'manual', None, 0, '', None, 1400),
            (8, 'active', 'attempt', None, 1, None, None, None),
            (9, 'active', 'import', None, 0, batch_a, '数量关系', 1400),
            (10, 'active', 'attempt', 20, 1, None, None, 1400),
            (11, 'suspended', 'import', None, 1, batch_a, '数量关系', 1400),
            (12, 'active', 'import', None, 1, 'batch-other', '数量关系', 2000),
            (13, 'active', 'import', None, 1, batch_a, '数量关系', 1400),
            # 题目原先在题库中，导入又保留了批次：浏览总数不能累加两个集合。
            (14, 'active', 'attempt', 24, 1, batch_a, '数量关系', 1400),
        ]
        for state_id, status, source, item_id, reviews, batch, section, domain in rows:
            question_id = 100 + state_id
            metadata = {'source': f'来源 {batch or state_id}'}
            if batch is not None:
                metadata['import_batch_id'] = batch
            if section is not None:
                metadata['section_name'] = section
            if domain is not None:
                metadata['domain_category_id'] = domain
            self.connection.execute(
                'INSERT INTO qbank_v2_question VALUES (?,?,?,?,?)',
                (question_id, f'题目 {state_id}', 'plain', 'single_choice', 1 if state_id == 9 else 0),
            )
            if item_id is not None:
                self.connection.execute(
                    'INSERT INTO qbank_v2_bank_item VALUES (?,?,?,?,0)',
                    (item_id, 2 if state_id == 5 else 1, question_id, 2 if state_id == 2 else 1),
                )
            self.connection.execute(
                """INSERT INTO qbank_v2_wrong_question_state
                   (id,user_id,question_id,source_bank_item_id,entry_source,entry_metadata,status,deleted,
                    review_count,last_wrong_time,last_reviewed_time,resolved_time)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    state_id,
                    8 if state_id == 13 else 7,
                    question_id,
                    item_id,
                    source,
                    json.dumps(metadata),
                    status,
                    state_id if state_id == 10 else 0,
                    reviews,
                    '2026-10-25 12:00:00' if state_id == 3 else '2026-10-01 12:00:00',
                    '2026-10-20 12:00:00' if reviews else None,
                    '2026-10-26 12:00:00' if status == 'resolved' else None,
                ),
            )
        # 同题在另一卷的新章节中出现，优先保留真正触发错题的来源章节。
        self.connection.execute('INSERT INTO qbank_v2_bank_item VALUES (999,2,101,2,0)')

    async def execute(self, stmt: Any) -> QueryResult:
        sql = str(stmt.compile(dialect=sqlite.dialect(), compile_kwargs={'literal_binds': True}))
        rows = [dict(row) for row in self.connection.execute(sql).fetchall()]
        for row in rows:
            for key, value in row.items():
                if key.endswith('_time') and value:
                    row[key] = datetime.fromisoformat(value).replace(tzinfo=UTC)
        return QueryResult(rows)


@pytest.fixture
def db() -> Iterator[BrowseDB]:
    database = BrowseDB()
    yield database
    database.connection.close()


@pytest.mark.parametrize(
    ('mode', 'expected_ids'), [('pending', {1, 3, 7}), ('reviewed', {2, 3, 4, 8, 14}), ('mastered', {5, 6})]
)
async def test_collections_chapters_and_questions_have_same_scope(
    db: BrowseDB, monkeypatch: pytest.MonkeyPatch, mode: str, expected_ids: set[int]
) -> None:
    monkeypatch.setattr(WrongReviewService, 'resolve_domain_scope', AsyncMock(return_value=[1400]))
    status = 'resolved' if mode == 'mastered' else 'active'
    review_state = None if mode == 'mastered' else mode
    params = {
        'user_id': 7,
        'filters': WrongQuestionFilters(status=status, review_state=review_state),
        'domain_category_ids': [1400],
    }
    question_rows = (await db.execute(wrong_question_state_dao.get_list_select(**params))).all()
    assert {row['id'] for row in question_rows} == expected_ids
    total, chapters = await wrong_question_state_dao.get_section_counts(db, **params)
    assert total == len(expected_ids)
    assert sum(row['total'] for row in chapters) == total
    for chapter in chapters:
        matching = (
            await db.execute(wrong_question_state_dao.get_list_select(**params, section_name=chapter['section_name']))
        ).all()
        assert len(matching) == chapter['total']

    page = await WrongReviewService.get_collections_page(db=db, user_id=7, mode=mode, size=1)
    assert page.total == total
    assert len(page.items) == 1
    groups = list(page.items)
    while page.has_more:
        page = await WrongReviewService.get_collections_page(
            db=db, user_id=7, mode=mode, size=1, cursor=page.next_cursor
        )
        assert page.total == total
        groups.extend(page.items)
    covered: set[int] = set()
    for group in groups:
        filters: dict[str, Any] = {}
        if group.collection_type == 'bank':
            filters['bank_id'] = int(group.collection_id)
        elif group.collection_type == 'import':
            filters['import_batch_id'] = group.collection_id
        elif group.collection_type == 'single':
            filters['external_unbatched'] = True
        else:
            filters['unassigned'] = True
        matching = (
            await db.execute(
                wrong_question_state_dao.get_list_select(**{
                    **params,
                    'filters': params['filters'].model_copy(update=filters),
                })
            )
        ).all()
        assert len(matching) == getattr(group, mode if mode != 'mastered' else 'mastered')
        covered.update(row['id'] for row in matching)
    assert covered == expected_ids


async def test_cross_collection_chapter_uses_saved_source_and_keeps_unclassified(db: BrowseDB) -> None:
    total, chapters = await wrong_question_state_dao.get_section_counts(
        db, user_id=7, filters=WrongQuestionFilters(review_state='pending'), domain_category_ids=[1400]
    )
    assert total == 3
    assert {row['section_name']: row['total'] for row in chapters} == {'数量关系': 2, '__unsectioned__': 1}


async def test_dashboard_browse_counter_does_not_include_mastered_or_deleted_questions(db: BrowseDB) -> None:
    statistics = await wrong_question_state_dao.get_statistics(
        db, user_id=7, now=datetime(2026, 10, 26, tzinfo=UTC), domain_category_ids=[1400]
    )
    assert statistics['active_reviewed_count'] == 5
    assert statistics['pending_review_count'] == 3
    assert statistics['resolved_count'] == 2
    assert statistics['reviewed_count'] > statistics['active_reviewed_count']


@pytest.mark.parametrize(
    ('since', 'expected_ids'),
    [(None, {1, 3, 7}), ('2026-10-19T00:00:00Z', {3}), ('2026-09-26T00:00:00Z', {1, 3, 7})],
)
async def test_time_window_keeps_collections_sections_and_questions_consistent(
    db: BrowseDB, monkeypatch: pytest.MonkeyPatch, since: str | None, expected_ids: set[int]
) -> None:
    """滚动时间窗口与领域、待复盘状态组合过滤，分组题量不累加重叠集合。"""
    monkeypatch.setattr(WrongReviewService, 'resolve_domain_scope', AsyncMock(return_value=[1400]))
    filters = WrongQuestionFilters(review_state='pending', since=since)
    params = {'user_id': 7, 'filters': filters, 'domain_category_ids': [1400]}
    for view in ['full', 'summary', 'outline']:
        rows = (await db.execute(wrong_question_state_dao.get_list_select(**params, view=view))).all()
        assert {row['id'] for row in rows} == expected_ids
    total, sections = await wrong_question_state_dao.get_section_counts(db, **params)
    assert total == len(expected_ids)
    assert sum(row['total'] for row in sections) == total
    page = await WrongReviewService.get_collections_page(db=db, user_id=7, since=filters.since)
    assert page.total == total
    for group in page.items:
        extra: dict[str, Any] = {}
        if group.collection_type == 'bank':
            extra['bank_id'] = int(group.collection_id)
        elif group.collection_type == 'import':
            extra['import_batch_id'] = group.collection_id
        elif group.collection_type == 'single':
            extra['external_unbatched'] = True
        else:
            extra['unassigned'] = True
        rows = (
            await db.execute(
                wrong_question_state_dao.get_list_select(**{**params, 'filters': filters.model_copy(update=extra)})
            )
        ).all()
        assert len(rows) == group.pending


async def test_time_window_includes_boundary_relapse_and_recorded_time_fallback(db: BrowseDB) -> None:
    """边界包含等于下界的记录，近期再错以最新时间为准，旧录入可回退到创建时间。"""
    db.connection.executescript("""
        UPDATE qbank_v2_wrong_question_state SET last_wrong_time = '2026-10-19 12:00:00.000000' WHERE id = 1;
        UPDATE qbank_v2_wrong_question_state
        SET last_wrong_time = NULL, first_wrong_time = NULL, created_time = '2026-10-24 12:00:00.000000' WHERE id = 7;
        UPDATE qbank_v2_wrong_question_state
        SET last_wrong_time = '2026-10-19 11:59:59', first_wrong_time = '2026-10-25 12:00:00' WHERE id = 4;
    """)
    filters = WrongQuestionFilters(review_state='pending', since=datetime(2026, 10, 19, 12, tzinfo=timezone.tz_info))
    rows = (
        await db.execute(
            wrong_question_state_dao.get_list_select(user_id=7, filters=filters, domain_category_ids=[1400])
        )
    ).all()
    assert {row['id'] for row in rows} == {1, 3, 7}
    batch_rows = (
        await db.execute(
            wrong_question_state_dao.get_list_select(
                user_id=7,
                filters=filters.model_copy(update={'import_batch_id': 'batch-aaaa'}),
                section_name='数量关系',
                domain_category_ids=[1400],
            )
        )
    ).all()
    assert [row['id'] for row in batch_rows] == [3]
