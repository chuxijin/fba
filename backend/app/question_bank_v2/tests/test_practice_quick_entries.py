"""快速入口组卷：模块配额、高频易错策略与幂等快照回归。"""

import asyncio

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError
from sqlalchemy import create_engine

from backend.app.question_bank_v2.crud.crud_practice import practice_session_item_dao
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam, PracticeModuleQuota
from backend.app.question_bank_v2.service import practice_service as module
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.common.exception import errors


class MemorySession:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    async def execute(self, statement: Any) -> Any:
        return self.connection.execute(statement)


@pytest.fixture
def db() -> Iterator[MemorySession]:
    """高频易错 SQL 需要统计表、发布编排与公开题事实"""
    engine = create_engine('sqlite://')
    with engine.connect() as connection:
        tables = {
            'question': (
                'id INTEGER, default_score NUMERIC, status TEXT, deleted INTEGER, visibility TEXT, '
                'owner_id INTEGER, question_type TEXT'
            ),
            'question_knowledge_point': 'question_id INTEGER, knowledge_point_id INTEGER, deleted INTEGER',
            'wrong_question_state': 'user_id INTEGER, question_id INTEGER, deleted INTEGER, last_wrong_response JSON',
            'question_review': (
                'id INTEGER, user_id INTEGER, question_id INTEGER, summary TEXT, review_data JSON, '
                'reviewed_time DATETIME, event_type TEXT, deleted INTEGER'
            ),
            'question_review_tag': 'review_id INTEGER, tag_id INTEGER, deleted INTEGER',
            'review_tag': 'id INTEGER, name TEXT, deleted INTEGER',
            'question_review_knowledge_point': 'review_id INTEGER, knowledge_point_id INTEGER, deleted INTEGER',
            'knowledge_point': 'id INTEGER, name TEXT, deleted INTEGER',
            'question_attempt': (
                'id INTEGER, question_id INTEGER, user_id INTEGER, attempt_no INTEGER, response_data JSON, '
                'submitted_time DATETIME, duration_ms INTEGER, is_correct BOOLEAN, deleted INTEGER'
            ),
            'bank_item': (
                'id INTEGER, bank_revision_id INTEGER, question_id INTEGER, exam_year INTEGER, '
                'is_active BOOLEAN, deleted INTEGER'
            ),
            'bank_revision': 'id INTEGER, bank_id INTEGER, status TEXT, deleted INTEGER, name TEXT, description TEXT',
            'bank': (
                'id INTEGER, name TEXT, code TEXT, description TEXT, current_revision_id INTEGER, '
                'status TEXT, deleted INTEGER'
            ),
            'question_statistics': 'question_id INTEGER, graded_count INTEGER, correct_rate NUMERIC, deleted INTEGER',
        }
        for name, columns in tables.items():
            connection.exec_driver_sql(f'CREATE TABLE qbank_v2_{name} ({columns})')

        for question_id in range(1, 12):
            visibility = 'private' if question_id == 4 else 'public'
            status = 'archived' if question_id == 11 else 'active'
            owner_id = '8' if question_id == 4 else 'NULL'
            connection.exec_driver_sql(
                'INSERT INTO qbank_v2_question '
                f"VALUES ({question_id}, 2, '{status}', 0, '{visibility}', {owner_id}, 'single_choice')"
            )

        for question_id in (1, 2, 3, 4, 5, 6, 7, 8, 10, 11):
            connection.exec_driver_sql(f'INSERT INTO qbank_v2_question_knowledge_point VALUES ({question_id}, 201, 0)')
        # 同一题重复挂载知识点时仍只能投递一次
        connection.exec_driver_sql('INSERT INTO qbank_v2_question_knowledge_point VALUES (1, 202, 0)')
        connection.exec_driver_sql('INSERT INTO qbank_v2_question_knowledge_point VALUES (9, 301, 0)')

        connection.exec_driver_sql(
            "INSERT INTO qbank_v2_bank VALUES (1,'平台题库','pt','平台',11,'active',0),"
            "(2,'另一题库','ot','另一',21,'active',0)"
        )
        connection.exec_driver_sql(
            "INSERT INTO qbank_v2_bank_revision VALUES (11,1,'published',0,'平台题库','平台'),"
            "(12,1,'retired',0,'平台旧版','平台'),(21,2,'published',0,'另一题库','另一')"
        )
        bank_item_id = 1
        # 当前发布编排：q5 无任何编排，q7 只挂在退役版本
        for question_id in (1, 2, 3, 4, 6, 8, 9, 10, 11):
            connection.exec_driver_sql(
                f'INSERT INTO qbank_v2_bank_item VALUES ({bank_item_id}, 11, {question_id}, 2026, 1, 0)'
            )
            bank_item_id += 1
        connection.exec_driver_sql(f'INSERT INTO qbank_v2_bank_item VALUES ({bank_item_id}, 12, 7, 2026, 1, 0)')

        # graded_count 至少 20、correct_rate <= 0.6、统计未删除、当前发布编排、公开题
        statistics = (
            (1, 20, 0.5, 0),
            (2, 19, 0.5, 0),
            (3, 20, 0.7, 0),
            (4, 20, 0.5, 0),
            (5, 20, 0.5, 0),
            (6, 20, 0.6, 0),
            (7, 20, 0.4, 0),
            (8, 30, 0.5, 0),
            (9, 25, 0.3, 0),
            (10, 20, 0.5, 1),
            (11, 20, 0.5, 0),
        )
        for question_id, graded_count, correct_rate, deleted in statistics:
            connection.exec_driver_sql(
                'INSERT INTO qbank_v2_question_statistics VALUES (?,?,?,?)',
                (question_id, graded_count, correct_rate, deleted),
            )
        yield MemorySession(connection)
    engine.dispose()


def high_error_candidates(db: MemorySession, **kwargs: Any) -> list[int]:
    options = {
        'user_id': 7,
        'source_type': 'custom',
        'bank_id': None,
        'section_ids': [],
        'favorite_folder_id': None,
        'question_ids': [],
        'knowledge_point_ids': [201],
        'question_types': [],
        'year_start': None,
        'year_end': None,
        'shuffle': False,
        'limit': 20,
        'high_error': True,
        **kwargs,
    }
    rows = asyncio.run(practice_session_item_dao.get_user_candidates(db, **options))
    return [row.question_id for row in rows]


def test_module_quota_total_must_equal_limit() -> None:
    with pytest.raises(ValidationError, match='模块题量之和必须等于总题数'):
        CreatePracticeSessionParam(
            source_type='custom',
            module_quotas=[
                PracticeModuleQuota(knowledge_point_id=201, count=2),
                PracticeModuleQuota(knowledge_point_id=301, count=1),
            ],
            limit=4,
        )


def test_module_quota_total_cannot_exceed_five_hundred() -> None:
    with pytest.raises(ValidationError, match='模块题量之和必须等于总题数'):
        CreatePracticeSessionParam(
            source_type='custom',
            module_quotas=[
                PracticeModuleQuota(knowledge_point_id=201, count=300),
                PracticeModuleQuota(knowledge_point_id=301, count=300),
            ],
            limit=500,
        )


def test_module_quota_rejects_duplicate_modules() -> None:
    with pytest.raises(ValidationError, match='模块不能重复'):
        CreatePracticeSessionParam(
            source_type='custom',
            module_quotas=[
                PracticeModuleQuota(knowledge_point_id=201, count=1),
                PracticeModuleQuota(knowledge_point_id=201, count=1),
            ],
            limit=2,
        )


@pytest.mark.parametrize(
    'overrides',
    [
        {'source_type': 'bank', 'bank_id': 1},
        {'question_ids': [1]},
        {'include_knowledge_descendants': False},
        {'selection_strategy': 'high_error'},
    ],
)
def test_module_quota_only_applies_to_plain_custom_composition(overrides: dict[str, Any]) -> None:
    params = {
        'source_type': 'custom',
        'module_quotas': [PracticeModuleQuota(knowledge_point_id=201, count=1)],
        'limit': 1,
        **overrides,
    }
    with pytest.raises(ValidationError):
        CreatePracticeSessionParam(**params)


def test_module_quota_must_match_selected_knowledge_points() -> None:
    with pytest.raises(ValidationError, match='模块配额必须与所选知识点一致'):
        CreatePracticeSessionParam(
            source_type='custom',
            knowledge_point_ids=[201, 301],
            module_quotas=[PracticeModuleQuota(knowledge_point_id=201, count=1)],
            limit=1,
        )


@pytest.mark.parametrize(
    'kwargs',
    [
        {'knowledge_point_id': 0, 'count': 1},
        {'knowledge_point_id': 201, 'count': 0},
        {'knowledge_point_id': 201, 'count': 501},
    ],
)
def test_module_quota_field_bounds(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        PracticeModuleQuota(**kwargs)


def test_module_quota_normalizes_knowledge_points_and_keeps_module_order() -> None:
    obj = CreatePracticeSessionParam(
        source_type='custom',
        knowledge_point_ids=[301, 201],
        module_quotas=[
            PracticeModuleQuota(knowledge_point_id=201, count=1),
            PracticeModuleQuota(knowledge_point_id=301, count=2),
        ],
        limit=3,
    )
    assert obj.knowledge_point_ids == [201, 301]
    assert [quota.knowledge_point_id for quota in obj.module_quotas] == [201, 301]


@pytest.mark.parametrize(
    'overrides',
    [
        {'knowledge_point_ids': []},
        {'knowledge_point_ids': [201], 'question_ids': [1]},
        {'knowledge_point_ids': [201], 'source_type': 'bank', 'bank_id': 1},
    ],
)
def test_high_error_requires_plain_custom_knowledge_scope(overrides: dict[str, Any]) -> None:
    params = {'source_type': 'custom', 'selection_strategy': 'high_error', 'limit': 20, **overrides}
    with pytest.raises(ValidationError):
        CreatePracticeSessionParam(**params)


def _module_objects() -> list[PracticeModuleQuota]:
    return [
        PracticeModuleQuota(knowledge_point_id=201, count=2),
        PracticeModuleQuota(knowledge_point_id=301, count=1),
    ]


def _module_obj() -> CreatePracticeSessionParam:
    return CreatePracticeSessionParam(source_type='custom', module_quotas=_module_objects(), limit=3)


def _patch_module_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve_points(**_kwargs: Any) -> set[int]:
        return {201, 202}

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))


def test_module_candidates_keep_module_order_and_exact_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def resolve_points(**kwargs: Any) -> set[int]:
        return {201, 202} if kwargs['point_ids'] == [201] else {301}

    def get_candidates(_db: Any, **kwargs: Any) -> list[Any]:
        calls.append(kwargs)
        if kwargs['knowledge_point_ids'] == [201, 202]:
            return [SimpleNamespace(question_id=11), SimpleNamespace(question_id=12)]
        return [SimpleNamespace(question_id=21)]

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))
    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))

    rows = asyncio.run(PracticeService._module_candidates(db=None, user_id=7, obj=_module_obj()))

    assert [row.question_id for row in rows] == [11, 12, 21]
    assert [call['limit'] for call in calls] == [2, 1]
    assert calls[0]['source_type'] == 'custom'
    assert calls[0]['question_ids'] == []


def test_module_candidates_exclude_previously_selected_questions(monkeypatch: pytest.MonkeyPatch) -> None:
    forwarded: list[list[int]] = []

    def resolve_points(**kwargs: Any) -> set[int]:
        return {kwargs['point_ids'][0]}

    def get_candidates(_db: Any, **kwargs: Any) -> list[Any]:
        forwarded.append(list(kwargs['exclude_question_ids']))
        if kwargs['exclude_question_ids']:
            return [SimpleNamespace(question_id=21)]
        return [SimpleNamespace(question_id=11), SimpleNamespace(question_id=12)]

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))
    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))

    rows = asyncio.run(PracticeService._module_candidates(db=None, user_id=7, obj=_module_obj()))

    assert [row.question_id for row in rows] == [11, 12, 21]
    assert forwarded == [[], [11, 12]]


def test_module_candidates_reject_duplicate_question_inside_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_module_resolution(monkeypatch)

    def get_candidates(_db: Any, **_kwargs: Any) -> list[Any]:
        return [SimpleNamespace(question_id=11), SimpleNamespace(question_id=11)]

    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))

    with pytest.raises(errors.RequestError, match='可用不重复题不足 2 题'):
        asyncio.run(PracticeService._module_candidates(db=None, user_id=7, obj=_module_obj()))


def test_module_candidates_reject_cross_module_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    def resolve_points(**_kwargs: Any) -> set[int]:
        return {201}

    def get_candidates(_db: Any, **_kwargs: Any) -> list[Any]:
        return [SimpleNamespace(question_id=11)]

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))
    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))
    obj = CreatePracticeSessionParam(
        source_type='custom',
        module_quotas=[
            PracticeModuleQuota(knowledge_point_id=201, count=1),
            PracticeModuleQuota(knowledge_point_id=301, count=1),
        ],
        limit=2,
    )

    with pytest.raises(errors.RequestError, match='可用不重复题不足 1 题'):
        asyncio.run(PracticeService._module_candidates(db=None, user_id=7, obj=obj))


def test_module_candidates_reject_short_module(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_module_resolution(monkeypatch)

    def get_candidates(_db: Any, **_kwargs: Any) -> list[Any]:
        return [SimpleNamespace(question_id=11)]

    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))

    with pytest.raises(errors.RequestError, match='模块 201 可用不重复题不足 2 题'):
        asyncio.run(PracticeService._module_candidates(db=None, user_id=7, obj=_module_obj()))


def _patch_create_common(
    monkeypatch: pytest.MonkeyPatch,
    candidates: list[Any],
    *,
    resolved: set[int] | None = None,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def resolve_points(**kwargs: Any) -> set[int]:
        return resolved if resolved is not None else {kwargs['point_ids'][0]}

    def get_by_key(*_args: Any, **_kwargs: Any) -> None:
        return None

    def get_candidates(_db: Any, **kwargs: Any) -> list[Any]:
        captured.setdefault('calls', []).append(kwargs)
        if callable(candidates):
            return candidates(**kwargs)
        return candidates

    def create_session(_db: Any, values: dict[str, Any]) -> Any:
        captured['values'] = values
        return SimpleNamespace(id=1, session_key=values['session_key'])

    def create_items(_db: Any, **kwargs: Any) -> None:
        captured['items'] = kwargs['candidates']

    def get_detail(**_kwargs: Any) -> Any:
        return SimpleNamespace(session_key='created-session')

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))
    monkeypatch.setattr(module.knowledge_service, 'resolve_point_system_id', AsyncMock(return_value=11))
    monkeypatch.setattr(module.practice_session_dao, 'get_by_key', AsyncMock(side_effect=get_by_key))
    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))
    monkeypatch.setattr(module.practice_session_dao, 'create', AsyncMock(side_effect=create_session))
    monkeypatch.setattr(module.practice_session_item_dao, 'create_all', AsyncMock(side_effect=create_items))
    monkeypatch.setattr(PracticeService, 'get', AsyncMock(side_effect=get_detail))
    return captured


def test_create_does_not_persist_session_when_module_is_short(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_create_common(monkeypatch, [SimpleNamespace(question_id=11)])

    with pytest.raises(errors.RequestError, match='可用不重复题不足 2 题'):
        asyncio.run(PracticeService.create(db=None, user_id=7, obj=_module_obj()))

    assert 'values' not in captured
    assert 'items' not in captured


def test_create_module_session_records_quota_and_strategy_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    def candidates(**kwargs: Any) -> list[Any]:
        if kwargs['knowledge_point_ids'] == [201]:
            return [SimpleNamespace(question_id=11), SimpleNamespace(question_id=12)]
        return [SimpleNamespace(question_id=21)]

    captured = _patch_create_common(monkeypatch, candidates)

    result = asyncio.run(PracticeService.create(db=None, user_id=7, obj=_module_obj()))

    assert result.session_key == 'created-session'
    assert [row.question_id for row in captured['items']] == [11, 12, 21]
    assert captured['values']['total_items'] == 3
    assert captured['values']['delivery_config']['module_quotas'] == [
        {'knowledge_point_id': 201, 'count': 2},
        {'knowledge_point_id': 301, 'count': 1},
    ]
    assert captured['values']['delivery_config']['selection_strategy'] == 'default'
    assert captured['values']['source_snapshot']['knowledge_point_ids'] == [201, 301]


def _matching_session(obj: CreatePracticeSessionParam) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=7,
        mode=obj.mode,
        title_snapshot=obj.title,
        source_snapshot={
            'requested_source_type': obj.source_type,
            'bank_id': obj.bank_id,
            'section_id': obj.section_id,
            'favorite_folder_id': obj.favorite_folder_id,
            'question_ids': obj.question_ids,
            'knowledge_point_ids': obj.knowledge_point_ids,
            'knowledge_system_id': obj.knowledge_system_id,
        },
        delivery_config={
            'shuffle': obj.shuffle,
            'requested_limit': obj.limit,
            'requested_duration_minutes': obj.duration_minutes,
            'annotations_enabled': obj.annotations_enabled,
            'question_types': obj.question_types,
            'year_start': obj.year_start,
            'year_end': obj.year_end,
            'region': obj.region,
            'include_knowledge_descendants': obj.include_knowledge_descendants,
            'module_quotas': [item.model_dump() for item in obj.module_quotas],
            'selection_strategy': obj.selection_strategy,
        },
    )


def _matches(obj: CreatePracticeSessionParam, session: SimpleNamespace) -> bool:
    return PracticeService._matches_create_request(session=session, user_id=7, obj=obj)


def test_idempotent_match_distinguishes_module_quotas() -> None:
    obj = _module_obj()
    session = _matching_session(obj)

    assert _matches(obj, session) is True

    session.delivery_config['module_quotas'] = [
        {'knowledge_point_id': 201, 'count': 1},
        {'knowledge_point_id': 301, 'count': 2},
    ]
    assert _matches(obj, session) is False


def test_idempotent_match_distinguishes_selection_strategy() -> None:
    obj = CreatePracticeSessionParam(source_type='custom', knowledge_point_ids=[201], selection_strategy='high_error')
    session = _matching_session(obj)

    assert _matches(obj, session) is True

    session.delivery_config['selection_strategy'] = 'default'
    assert _matches(obj, session) is False


def test_high_error_sql_applies_threshold_visibility_and_current_placement(db: MemorySession) -> None:
    # 只保留：判分 >=20、正确率 <=0.6、公开、统计有效、当前发布版本且启用的编排
    assert high_error_candidates(db) == [8, 1, 6]


def test_high_error_sql_orders_by_rate_then_volume_without_duplicates(db: MemorySession) -> None:
    result = high_error_candidates(db)

    assert result == [8, 1, 6]
    assert len(result) == len(set(result))
    # 同正确率时按判分次数倒序：q8(30) 在 q1(20) 之前
    assert result.index(8) < result.index(1) < result.index(6)


def test_high_error_sql_respects_knowledge_point_scope(db: MemorySession) -> None:
    assert high_error_candidates(db, knowledge_point_ids=[301]) == [9]
    assert high_error_candidates(db, knowledge_point_ids=[201, 301]) == [9, 8, 1, 6]
    assert high_error_candidates(db, knowledge_point_ids=[999]) == []


def test_high_error_sql_does_not_fall_back_to_personal_wrong_books(db: MemorySession) -> None:
    db.connection.exec_driver_sql(
        'INSERT INTO qbank_v2_wrong_question_state VALUES (7, 2, 0, NULL),(7, 3, 0, NULL),(7, 4, 0, NULL)'
    )

    result = high_error_candidates(db)

    assert result == [8, 1, 6]
    assert 2 not in result
    assert 3 not in result
    assert 4 not in result


@pytest.mark.parametrize(
    'overrides',
    [
        {'source_type': 'wrong'},
        {'question_ids': [1]},
        {'knowledge_point_ids': []},
    ],
)
def test_high_error_returns_empty_for_invalid_scope(db: MemorySession, overrides: dict[str, Any]) -> None:
    assert high_error_candidates(db, **overrides) == []


def test_create_reports_friendly_message_when_high_error_has_no_candidates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_create_common(monkeypatch, [])
    obj = CreatePracticeSessionParam(
        source_type='custom',
        knowledge_point_ids=[201],
        selection_strategy='high_error',
        limit=20,
    )

    with pytest.raises(errors.RequestError, match='当前模块暂无样本充足的高频易错题'):
        asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj))


@pytest.mark.parametrize(('strategy', 'expected'), [('default', False), ('high_error', True)])
def test_create_forwards_high_error_only_for_that_strategy(
    monkeypatch: pytest.MonkeyPatch,
    strategy: str,
    *,
    expected: bool,
) -> None:
    captured = _patch_create_common(monkeypatch, [SimpleNamespace(question_id=1)])
    obj = CreatePracticeSessionParam(
        source_type='custom',
        knowledge_point_ids=[201],
        selection_strategy=strategy,
        limit=20,
    )

    asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj))

    assert ('high_error' in captured['calls'][0]) is expected
    assert captured['values']['delivery_config']['selection_strategy'] == strategy
