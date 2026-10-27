import json

from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, get_args
from unittest.mock import AsyncMock

import pytest

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlakeyset import select_page
from sqlalchemy import Connection, Engine, create_engine
from sqlalchemy.pool import StaticPool

from backend.app.question_bank_v2.api.v1 import review as review_api
from backend.app.question_bank_v2.crud.crud_practice import question_attempt_dao
from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao
from backend.app.question_bank_v2.schema.review import (
    GetWrongQuestionListItem,
    GetWrongQuestionOutlineItem,
    GetWrongQuestionSummaryItem,
    WrongQuestionFilters,
)
from backend.app.question_bank_v2.service import wrong_review_service as review_module
from backend.app.question_bank_v2.service.wrong_review_service import WrongReviewService
from backend.app.question_bank_v2.tests.test_review_service import CaptureHarness, DummyDB
from backend.app.question_bank_v2.tests.test_wrong_browse import BrowseDB
from backend.common.response.response_schema import response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.utils.serializers import MsgSpecJSONResponse


class ReadDB:
    """执行真实 SQL，并记录读取次数；数据库只存在于内存。"""

    def __init__(self, connection: Connection) -> None:
        self.connection = connection
        self.statements: list[Any] = []

    def get_bind(self) -> Engine:
        return self.connection.engine

    async def execute(self, stmt: Any) -> Any:
        self.statements.append(stmt)
        return self.connection.execute(stmt)


@pytest.fixture
def read_db() -> Iterator[ReadDB]:
    fixture = BrowseDB(check_same_thread=False)
    fixture.connection.commit()
    engine = create_engine('sqlite://', creator=lambda: fixture.connection, poolclass=StaticPool)
    with engine.connect() as connection:
        # sqlakeyset 按 SQLAlchemy DateTime 绑定值比较；种子也采用 SQLite 方言的微秒格式。
        connection.exec_driver_sql("""
            UPDATE qbank_v2_wrong_question_state
            SET last_wrong_time = last_wrong_time || '.000000',
                last_reviewed_time = last_reviewed_time || '.000000',
                resolved_time = resolved_time || '.000000'
        """)
        connection.exec_driver_sql("""
            CREATE TABLE qbank_v2_question_attempt (
                id INTEGER, user_id INTEGER, question_id INTEGER, is_correct INTEGER,
                deleted INTEGER, submitted_time TEXT, response_data TEXT,
                attempt_no INTEGER, duration_ms INTEGER
            )
        """)
        yield ReadDB(connection)
    engine.dispose()


@pytest.mark.parametrize('mode', ['pending', 'reviewed', 'mastered'])
def test_light_views_keep_scope_order_and_real_cursor_pagination(read_db: ReadDB, mode: str) -> None:
    filters = WrongQuestionFilters(
        status='resolved' if mode == 'mastered' else 'active',
        review_state=None if mode == 'mastered' else mode,
    )
    expected: list[int] = []
    for view, schema in (
        ('full', GetWrongQuestionListItem),
        ('summary', GetWrongQuestionSummaryItem),
        ('outline', GetWrongQuestionOutlineItem),
    ):
        stmt = wrong_question_state_dao.get_list_select(
            user_id=7, filters=filters, domain_category_ids=[1400], view=view
        )
        rows: list[dict[str, Any]] = []
        bookmark = None
        seen_bookmarks = set()
        while True:
            page = select_page(read_db.connection, stmt, per_page=2, page=bookmark)
            rows.extend(schema.model_validate(row._mapping).model_dump() for row in page)
            if not page.paging.has_next:
                break
            bookmark = page.paging.bookmark_next
            assert bookmark not in seen_bookmarks, '分页游标不能停滞或循环'
            seen_bookmarks.add(bookmark)
        ids = [row['id'] for row in rows]
        if view == 'full':
            expected = ids
            assert set(ids) == {'pending': {1, 3, 7}, 'reviewed': {2, 3, 4, 8, 14}, 'mastered': {5, 6}}[mode]
        else:
            assert ids == expected
            assert 'qbank_v2_user_question_mastery' not in str(stmt)
        if view == 'outline':
            assert 'qbank_v2_question.stem' not in str(stmt)
            assert all(set(row) == {'id', 'section_name', 'module_group'} for row in rows)
        if view == 'summary':
            assert all(
                set(row)
                == {
                    'id',
                    'section_name',
                    'module_group',
                    'stem_preview',
                    'status',
                    'wrong_count',
                    'review_count',
                }
                for row in rows
            )


def test_light_payload_sizes_are_bounded_for_long_stems(read_db: ReadDB) -> None:
    long_stem = '<p>材料题：' + '需要保留在详情中的完整题干。' * 400 + '</p>'
    read_db.connection.exec_driver_sql('UPDATE qbank_v2_question SET stem = ?', (long_stem,))
    sizes = {}
    for view, schema in (
        ('full', GetWrongQuestionListItem),
        ('summary', GetWrongQuestionSummaryItem),
        ('outline', GetWrongQuestionOutlineItem),
    ):
        stmt = wrong_question_state_dao.get_list_select(
            user_id=7, filters=WrongQuestionFilters(review_state='reviewed'), domain_category_ids=[1400], view=view
        )
        items = [
            schema.model_validate(row).model_dump(mode='json') for row in read_db.connection.execute(stmt).mappings()
        ]
        if view == 'summary':
            assert all(len(row['stem_preview']) <= 161 and '<p>' not in row['stem_preview'] for row in items)
        payload = {'items': items, 'next_cursor': None, 'has_more': False}
        sizes[view] = len(MsgSpecJSONResponse(response_base.success(data=payload).model_dump(mode='json')).body)
    assert sizes['summary'] < sizes['full'] * 0.05
    assert sizes['outline'] < sizes['full'] * 0.01
    print(f'相同 5 道长题干的未压缩 JSON 响应字节数：{sizes}')


async def test_wrong_history_reads_all_valid_attempts_with_duration(read_db: ReadDB) -> None:
    rows = [
        (1, 7, 101, 0, 0, '2026-10-25 12:00:00', json.dumps('A'), 1, 12000),
        (2, 7, 101, 0, 0, '2026-10-26 12:00:00', json.dumps('B'), 2, None),
        (3, 7, 101, 0, 0, '2026-10-27 12:00:00', json.dumps({'mode': 'memorize', 'viewed': True}), 3, 9000),
        (4, 8, 101, 0, 0, '2026-10-27 12:00:00', json.dumps('other-user'), 1, 1000),
        (5, 7, 101, 0, 5, '2026-10-27 12:00:00', json.dumps('deleted'), 4, 1000),
        (6, 7, 101, 1, 0, '2026-10-27 12:00:00', json.dumps('correct'), 5, 1000),
    ]
    read_db.connection.exec_driver_sql('INSERT INTO qbank_v2_question_attempt VALUES (?,?,?,?,?,?,?,?,?)', rows)
    history = await question_attempt_dao.get_wrong_answer_history(read_db, user_id=7, question_id=101)
    assert [row['response_data'] for row in history] == ['B', 'A']
    assert history[0]['attempt_no'] == 2
    assert history[0]['duration_ms'] is None
    assert history[1]['duration_ms'] == 12000
    assert len(read_db.statements) == 1
    assert len(read_db.statements[0].selected_columns) == 4


@pytest.mark.parametrize(
    'response',
    [
        'B',
        None,
        {'mode': 'memorize', 'viewed': False},
        {'mode': 'memorize', 'viewed': 'true'},
        {'mode': 'memorize', 'viewed': 1},
    ],
)
async def test_wrong_history_excludes_only_json_true_memorize_marker(read_db: ReadDB, response: Any) -> None:
    rows = [
        (1, 7, 101, 0, 0, '2026-10-25 12:00:00', json.dumps('A'), 1, 12000),
        (2, 7, 101, 0, 0, '2026-10-26 12:00:00', json.dumps(response), 2, 15000),
        (3, 7, 101, 0, 0, '2026-10-27 12:00:00', json.dumps({'mode': 'memorize', 'viewed': True}), 3, 9000),
    ]
    read_db.connection.exec_driver_sql('INSERT INTO qbank_v2_question_attempt VALUES (?,?,?,?,?,?,?,?,?)', rows)
    history = await question_attempt_dao.get_wrong_answer_history(read_db, user_id=7, question_id=101)
    assert [row['response_data'] for row in history] == [response, 'A']
    assert history[0]['duration_ms'] == 15000


async def test_wrong_history_is_empty_without_valid_attempt(read_db: ReadDB) -> None:
    assert await question_attempt_dao.get_wrong_answer_history(read_db, user_id=7, question_id=101) == []


@pytest.mark.parametrize(('review_count', 'threshold'), [(0, 3), (1, 1)])
async def test_detail_only_reads_preference_when_threshold_depends_on_it(
    read_db: ReadDB, monkeypatch: pytest.MonkeyPatch, review_count: int, threshold: int
) -> None:
    stmt = wrong_question_state_dao.get_list_select(user_id=7, filters=WrongQuestionFilters())
    row = dict(read_db.connection.execute(stmt).mappings().first())
    row['review_count'] = review_count
    preference = AsyncMock(return_value=SimpleNamespace(mastery_threshold=3))
    monkeypatch.setattr(wrong_question_state_dao, 'get_detail_row', AsyncMock(return_value=row))
    monkeypatch.setattr(question_attempt_dao, 'get_wrong_answer_history', AsyncMock(return_value=[]))
    monkeypatch.setattr(review_module.question_material_dao, 'get_all', AsyncMock(return_value=[]))
    monkeypatch.setattr(review_module.preference_service, 'get', preference)

    detail = await WrongReviewService.get_detail(db=read_db, user_id=7, wrong_state_id=row['id'])
    assert detail.resolve_threshold == threshold
    assert preference.await_count == (0 if review_count else 1)


async def test_detail_exposes_wrong_history_and_latest_duration(
    read_db: ReadDB, monkeypatch: pytest.MonkeyPatch
) -> None:
    stmt = wrong_question_state_dao.get_list_select(user_id=7, filters=WrongQuestionFilters())
    row = dict(read_db.connection.execute(stmt).mappings().first())
    row['review_count'] = 1
    history = [
        {
            'response_data': 'B',
            'attempt_no': 2,
            'submitted_time': datetime(2026, 10, 26, 4, 0, tzinfo=UTC),
            'duration_ms': 15000,
        },
        {
            'response_data': 'A',
            'attempt_no': 1,
            'submitted_time': datetime(2026, 10, 25, 4, 0, tzinfo=UTC),
            'duration_ms': 12000,
        },
    ]
    monkeypatch.setattr(wrong_question_state_dao, 'get_detail_row', AsyncMock(return_value=row))
    monkeypatch.setattr(question_attempt_dao, 'get_wrong_answer_history', AsyncMock(return_value=history))
    monkeypatch.setattr(review_module.question_material_dao, 'get_all', AsyncMock(return_value=[]))

    detail = await WrongReviewService.get_detail(db=read_db, user_id=7, wrong_state_id=row['id'])
    assert detail.last_wrong_response == 'B'
    assert detail.last_wrong_duration_ms == 15000
    assert [item.answer for item in detail.wrong_answer_history] == ['B', 'A']
    assert detail.wrong_answer_history[0].duration_ms == 15000
    assert detail.wrong_answer_history[1].attempt_no == 1


class BatchDB(DummyDB):
    @asynccontextmanager
    async def begin_nested(self) -> Any:
        yield


@pytest.mark.parametrize('domain_id', [1400, None])
async def test_batch_capture_never_loads_details_and_resolves_domain_once(
    monkeypatch: pytest.MonkeyPatch, domain_id: int | None
) -> None:
    harness = CaptureHarness()
    harness.patch(monkeypatch)
    resolver = AsyncMock(return_value=domain_id)
    detail = AsyncMock(side_effect=AssertionError('批量导入不应装配详情'))
    monkeypatch.setattr(WrongReviewService, '_resolve_recorded_domain_id', resolver)
    monkeypatch.setattr(WrongReviewService, 'get_detail', detail)

    def create_question(_db: Any, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(id=int(kwargs['stem'].rsplit(' ', 1)[-1]) + 11)

    def create_state(_db: Any, data: dict[str, Any]) -> SimpleNamespace:
        return SimpleNamespace(id=data['question_id'] + 100, **data)

    monkeypatch.setattr(review_module.question_dao, 'create', AsyncMock(side_effect=create_question))
    monkeypatch.setattr(review_module.wrong_question_state_dao, 'create', AsyncMock(side_effect=create_state))
    params = [
        harness.build_param().model_copy(update={'idempotency_key': f'batch-capture-{index}', 'stem': f'题目 {index}'})
        for index in range(50)
    ]

    result = await WrongReviewService.capture_external_batch(db=BatchDB(), user_id=7, items=params)

    assert (result.total, result.succeeded, result.failed) == (50, 50, 0)
    assert len(result.items) == 50
    assert [row.question_id for row in result.items] == list(range(11, 61))
    assert [row.wrong_state_id for row in result.items] == list(range(111, 161))
    assert len(harness.review_events) == 100
    assert resolver.await_count == 1
    assert detail.await_count == 0


async def test_failed_batch_item_does_not_publish_material_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    harness = CaptureHarness()
    harness.patch(monkeypatch)
    monkeypatch.setattr(WrongReviewService, 'get_detail', AsyncMock(side_effect=AssertionError('不应回读详情')))
    snapshots = []

    def attach_materials(*, materials: Any, cache: dict[str, tuple[int, int]], **_: Any) -> None:
        snapshots.append(dict(cache))
        key = materials[0].link_key
        cache[key] = (1, 10) if key == 'shared' else (2, 20)
        if key == 'rolled-back':
            raise ValueError('模拟单条失败')

    monkeypatch.setattr(WrongReviewService, '_attach_materials', AsyncMock(side_effect=attach_materials))
    params = [
        harness.build_param().model_copy(
            update={
                'idempotency_key': f'cache-{index:08}',
                'materials': [SimpleNamespace(link_key=key)],
            }
        )
        for index, key in enumerate(['shared', 'rolled-back', 'shared'])
    ]
    result = await WrongReviewService.capture_external_batch(db=BatchDB(), user_id=7, items=params)
    assert (result.succeeded, result.failed) == (2, 1)
    assert result.failures[0].index == 1
    assert snapshots == [{}, {'shared': (1, 10)}, {'shared': (1, 10)}]


@pytest.fixture
def api_client(monkeypatch: pytest.MonkeyPatch, read_db: ReadDB) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(review_api.router, prefix='/wrong-questions')

    def auth(request: Request) -> None:
        request.scope['user'] = SimpleNamespace(id=7)

    app.dependency_overrides[DependsJwtAuth.dependency] = auth
    app.dependency_overrides[get_args(CurrentSession)[1].dependency] = lambda: read_db
    monkeypatch.setattr(WrongReviewService, 'resolve_domain_scope', AsyncMock(return_value=[1400]))

    def paginate(db: ReadDB, stmt: Any, schema_cls: Any) -> dict[str, Any]:
        # 路由真实解析查询模型并验证响应；稳定分页在上面的 sqlakeyset 测试中执行。
        return {
            'items': [schema_cls.model_validate(row).model_dump() for row in db.connection.execute(stmt).mappings()],
            'next_cursor': None,
            'has_more': False,
        }

    monkeypatch.setattr(review_module, 'cursor_paging_data', AsyncMock(side_effect=paginate))
    with TestClient(app) as client:
        yield client


def test_section_list_orders_by_module_group_then_recent_time(read_db: ReadDB) -> None:
    paths = {
        3: ['数量关系', '数学运算', '工程问题'],
        4: ['数量关系', '数字推理'],
        14: ['数量关系', '数字推理', '多级数列'],
    }
    for state_id, module_path in paths.items():
        raw = read_db.connection.exec_driver_sql(
            'SELECT entry_metadata FROM qbank_v2_wrong_question_state WHERE id = ?', (state_id,)
        ).scalar_one()
        metadata = json.loads(raw)
        metadata['module_path'] = module_path
        read_db.connection.exec_driver_sql(
            'UPDATE qbank_v2_wrong_question_state SET entry_metadata = ? WHERE id = ?',
            (json.dumps(metadata), state_id),
        )

    stmt = wrong_question_state_dao.get_list_select(
        user_id=7,
        filters=WrongQuestionFilters(status='active'),
        domain_category_ids=[1400],
        section_name='数量关系',
        view='summary',
    )
    rows = read_db.connection.execute(stmt).mappings().all()
    # 二级分类相同的题必须连续，路径层级不同也不能被拆开；无路径题排最后。
    assert [row['id'] for row in rows] == [14, 4, 3, 1]
    assert [row['module_group'] for row in rows] == ['数字推理', '数字推理', '数学运算', None]

    # 游标分页不能把 JSON 数组放进排序键，否则会触发 unhashable 错误。
    page_rows = []
    bookmark = None
    while True:
        page = select_page(read_db.connection, stmt, per_page=2, page=bookmark)
        page_rows.extend(GetWrongQuestionSummaryItem.model_validate(row._mapping) for row in page)
        if not page.paging.has_next:
            break
        bookmark = page.paging.bookmark_next
    assert [row.id for row in page_rows] == [14, 4, 3, 1]


@pytest.mark.parametrize('view', ['full', 'summary', 'outline'])
def test_api_view_query_is_flat_and_scope_matches_sections(api_client: TestClient, view: str) -> None:
    params = {'review_state': 'pending', 'bank_id': 1, 'domain_category_id': 1400}
    response = api_client.get('/wrong-questions', params={**params, 'view': view, 'section_name': '数量关系'})
    assert response.status_code == 200
    body = response.json()
    assert body['code'] == 200
    assert [row['id'] for row in body['data']['items']] == [1]
    keys = set(body['data']['items'][0])
    if view == 'outline':
        assert keys == {'id', 'section_name', 'module_group'}
    elif view == 'summary':
        assert keys == {'id', 'section_name', 'module_group', 'stem_preview', 'status', 'wrong_count', 'review_count'}
    else:
        assert 'stem' in keys and 'first_wrong_time' in keys
    sections = api_client.get('/wrong-questions/sections', params=params)
    assert sections.status_code == 200
    assert sections.json()['data']['items'] == [{'section_name': '数量关系', 'total': 1}]


def test_summary_preserves_decoded_comparison_symbols_through_response_validation(
    api_client: TestClient, read_db: ReadDB
) -> None:
    read_db.connection.exec_driver_sql(
        'UPDATE qbank_v2_question SET stem = ? WHERE id = 101', ('<p>甲 &lt;乙&gt; 丙&nbsp;丁</p>',)
    )
    response = api_client.get('/wrong-questions', params={'view': 'summary', 'bank_id': 1, 'review_state': 'pending'})
    assert response.status_code == 200
    row = response.json()['data']['items'][0]
    assert row['stem_preview'] == '甲 <乙> 丙 丁'
    assert '_stem' not in row and 'stem' not in row


@pytest.mark.parametrize(
    'params', [{'view': 'unknown'}, {'bank_id': 0}, {'import_batch_id': 'short'}, {'section_name': '长' * 161}]
)
def test_shared_query_validation_still_rejects_invalid_filters(api_client: TestClient, params: dict[str, Any]) -> None:
    assert api_client.get('/wrong-questions', params=params).status_code == 422


@pytest.mark.parametrize('view', ['full', 'summary', 'outline'])
def test_api_time_filter_matches_collection_counts_and_sections(api_client: TestClient, view: str) -> None:
    params = {'review_state': 'pending', 'since': '2026-10-19T00:00:00Z', 'domain_category_id': 1400}
    response = api_client.get('/wrong-questions', params={**params, 'view': view, 'import_batch_id': 'batch-aaaa'})
    assert response.status_code == 200
    assert [row['id'] for row in response.json()['data']['items']] == [3]
    sections = api_client.get('/wrong-questions/sections', params=params)
    assert sections.status_code == 200
    assert sections.json()['data'] == {'total': 1, 'items': [{'section_name': '数量关系', 'total': 1}]}
    collections = api_client.get('/wrong-questions/collections', params={**params, 'mode': 'pending'})
    assert collections.status_code == 200
    assert collections.json()['data']['total'] == 1
    groups = [(row['collection_id'], row['pending']) for row in collections.json()['data']['items']]
    assert groups == [('batch-aaaa', 1)]


@pytest.mark.parametrize('endpoint', ['', '/sections', '/collections', '/pending-review'])
@pytest.mark.parametrize('since', ['yesterday', '2026-10-19T00:00:00', '2026-02-30T00:00:00Z'])
def test_api_rejects_invalid_or_timezone_less_time_filter(api_client: TestClient, endpoint: str, since: str) -> None:
    assert api_client.get(f'/wrong-questions{endpoint}', params={'since': since}).status_code == 422
