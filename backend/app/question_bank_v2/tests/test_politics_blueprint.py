"""考研政治六模块蓝图：配额分配、真实体系计划、模块抽题与快照幂等回归。"""

import asyncio
import itertools

from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.crud.crud_practice import PracticeCandidate
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank_v2.service import practice_service as module
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.app.question_bank_v2.utils.politics_paper import (
    POLITICS_MODULES,
    PoliticsModuleQuota,
    build_politics_quotas,
)
from backend.common.exception import errors

EXPECTED_SINGLE = {
    'kaoyan_politics_mayuan': 4,
    'kaoyan_politics_maozhongte': 2,
    'kaoyan_politics_xinshixiang': 3,
    'kaoyan_politics_shigang': 4,
    'kaoyan_politics_sixiu': 1,
    'kaoyan_politics_shizheng': 2,
}
EXPECTED_MULTIPLE = {
    'kaoyan_politics_mayuan': 5,
    'kaoyan_politics_maozhongte': 1,
    'kaoyan_politics_xinshixiang': 4,
    'kaoyan_politics_shigang': 3,
    'kaoyan_politics_sixiu': 2,
    'kaoyan_politics_shizheng': 2,
}


def _module(code: str) -> Any:
    return next(item for item in POLITICS_MODULES if item.code == code)


def _snapshot_code(snapshot: dict[str, Any]) -> str | None:
    if 'module_code' in snapshot:
        return snapshot['module_code']
    if 'code' in snapshot:
        return snapshot['code']
    nested = snapshot.get('module')
    if isinstance(nested, dict):
        return nested.get('code')
    return getattr(nested, 'code', None)


def _candidate(question_id: int) -> PracticeCandidate:
    return PracticeCandidate(
        question_id=question_id,
        bank_item_id=None,
        max_score=Decimal(9),
        display_config={},
    )


def _politics_obj(**overrides: Any) -> CreatePracticeSessionParam:
    params: dict[str, Any] = {
        'source_type': 'custom',
        'knowledge_point_ids': [101, 201],
        'knowledge_system_id': 8,
        'paper_profile': 'kaoyan_politics',
        'mode': 'practice',
    }
    params.update(overrides)
    return CreatePracticeSessionParam(**params)


# ---------------------------------------------------------------------------
# 纯配额 helper：固定六模块、部分范围最大余数、单模块、顺序与快照
# ---------------------------------------------------------------------------


def test_full_scope_uses_fixed_six_module_counts() -> None:
    scopes = [(item, frozenset({5000 + index})) for index, item in enumerate(POLITICS_MODULES)]

    plan = build_politics_quotas(scopes)

    assert [quota.module.code for quota in plan] == [item.code for item in POLITICS_MODULES]
    assert [quota.single_count for quota in plan] == [EXPECTED_SINGLE[item.code] for item in POLITICS_MODULES]
    assert [quota.multiple_count for quota in plan] == [EXPECTED_MULTIPLE[item.code] for item in POLITICS_MODULES]
    assert sum(quota.single_count for quota in plan) == 16
    assert sum(quota.multiple_count for quota in plan) == 17


def test_every_nonempty_module_subset_keeps_16_single_and_17_multiple() -> None:
    for size in range(1, len(POLITICS_MODULES) + 1):
        for modules in itertools.combinations(POLITICS_MODULES, size):
            scopes = [(item, frozenset({index + 1})) for index, item in enumerate(modules)]
            forward = build_politics_quotas(scopes)
            reverse = build_politics_quotas(list(reversed(scopes)))
            assert forward == reverse
            assert sum(quota.single_count for quota in forward) == 16
            assert sum(quota.multiple_count for quota in forward) == 17
            assert all(quota.single_count > 0 and quota.multiple_count > 0 for quota in forward)


def test_single_module_scope_fills_whole_paper() -> None:
    sixiu = _module('kaoyan_politics_sixiu')

    plan = build_politics_quotas([(sixiu, frozenset({7}))])

    assert len(plan) == 1
    assert plan[0].module.code == 'kaoyan_politics_sixiu'
    assert plan[0].point_ids == frozenset({7})
    assert plan[0].single_count == 16
    assert plan[0].multiple_count == 17


def test_partial_scope_allocates_single_and_multiple_by_largest_remainder() -> None:
    mayuan = _module('kaoyan_politics_mayuan')
    xinshixiang = _module('kaoyan_politics_xinshixiang')

    plan = build_politics_quotas([
        (mayuan, frozenset({1})),
        (xinshixiang, frozenset({2})),
    ])

    assert [quota.single_count for quota in plan] == [9, 7]
    assert [quota.multiple_count for quota in plan] == [9, 8]
    assert sum(quota.single_count for quota in plan) == 16
    assert sum(quota.multiple_count for quota in plan) == 17


def test_equal_remainders_follow_fixed_module_order() -> None:
    mayuan = _module('kaoyan_politics_mayuan')
    maozhongte = _module('kaoyan_politics_maozhongte')
    shigang = _module('kaoyan_politics_shigang')
    sixiu = _module('kaoyan_politics_sixiu')
    shizheng = _module('kaoyan_politics_shizheng')

    single_plan = build_politics_quotas([
        (shigang, frozenset({3})),
        (maozhongte, frozenset({2})),
        (mayuan, frozenset({1})),
    ])
    multiple_plan = build_politics_quotas([
        (shizheng, frozenset({5})),
        (sixiu, frozenset({4})),
    ])

    assert [quota.module.code for quota in single_plan] == [
        'kaoyan_politics_mayuan',
        'kaoyan_politics_maozhongte',
        'kaoyan_politics_shigang',
    ]
    assert [quota.single_count for quota in single_plan] == [7, 3, 6]
    assert [quota.module.code for quota in multiple_plan] == [
        'kaoyan_politics_sixiu',
        'kaoyan_politics_shizheng',
    ]
    assert [quota.multiple_count for quota in multiple_plan] == [9, 8]


def test_scope_input_order_does_not_change_plan() -> None:
    mayuan = _module('kaoyan_politics_mayuan')
    xinshixiang = _module('kaoyan_politics_xinshixiang')

    forward = build_politics_quotas([
        (mayuan, frozenset({1})),
        (xinshixiang, frozenset({2})),
    ])
    reverse = build_politics_quotas([
        (xinshixiang, frozenset({2})),
        (mayuan, frozenset({1})),
    ])

    assert [quota.as_snapshot() for quota in forward] == [quota.as_snapshot() for quota in reverse]


def test_quota_snapshot_records_module_counts_and_points() -> None:
    sixiu = _module('kaoyan_politics_sixiu')

    plan = build_politics_quotas([(sixiu, frozenset({9, 7}))])
    snapshot = plan[0].as_snapshot()

    assert _snapshot_code(snapshot) == 'kaoyan_politics_sixiu'
    assert snapshot['single_count'] == 16
    assert snapshot['multiple_count'] == 17
    assert snapshot['knowledge_point_ids'] == [7, 9]


@pytest.mark.parametrize(
    'scopes',
    [
        [],
        [(_module('kaoyan_politics_mayuan'), frozenset())],
    ],
)
def test_build_quotas_rejects_empty_scope(scopes: list[tuple[Any, frozenset[int]]]) -> None:
    with pytest.raises(errors.RequestError):
        build_politics_quotas(scopes)


def test_build_quotas_rejects_unknown_module() -> None:
    with pytest.raises(errors.RequestError):
        build_politics_quotas([(SimpleNamespace(code='kaoyan_politics_unknown'), frozenset({1}))])


def test_build_quotas_merges_repeated_module_scopes() -> None:
    mayuan = _module('kaoyan_politics_mayuan')

    plan = build_politics_quotas([
        (mayuan, frozenset({1})),
        (mayuan, frozenset({2})),
    ])

    assert len(plan) == 1
    assert plan[0].module.code == 'kaoyan_politics_mayuan'
    assert plan[0].point_ids == frozenset({1, 2})
    assert plan[0].single_count == 16
    assert plan[0].multiple_count == 17


# ---------------------------------------------------------------------------
# 真实 _politics_plan：体系 code + 父链，节点 ID 全部从 code 定位
# ---------------------------------------------------------------------------


def _politics_points() -> tuple[list[SimpleNamespace], dict[str, int]]:
    points: list[SimpleNamespace] = []
    identifiers: dict[str, int] = {}
    cursor = itertools.count(5001)

    def add(code: str, name: str, parent_id: int | None) -> int:
        point_id = next(cursor)
        points.append(
            SimpleNamespace(
                id=point_id,
                code=code,
                name=name,
                parent_id=parent_id,
                system_id=8,
                depth=0,
            )
        )
        return point_id

    identifiers['system_root'] = add('kaoyan_politics', '考研政治', None)
    for item in POLITICS_MODULES:
        identifiers[item.code] = add(item.code, item.name, identifiers['system_root'])
    identifiers['mayuan_leaf'] = add(
        'kaoyan_politics_mayuan_leaf_a', '马原叶子A', identifiers['kaoyan_politics_mayuan']
    )
    identifiers['mayuan_deep_leaf'] = add(
        'kaoyan_politics_mayuan_leaf_b', '马原叶子B', identifiers['mayuan_leaf']
    )
    identifiers['sixiu_leaf'] = add(
        'kaoyan_politics_sixiu_leaf', '思修叶子', identifiers['kaoyan_politics_sixiu']
    )
    identifiers['misc_root'] = add('kaoyan_politics_misc', '未归属模块', identifiers['system_root'])
    identifiers['misc_leaf'] = add('kaoyan_politics_misc_leaf', '未归属叶子', identifiers['misc_root'])
    return points, identifiers


def _run_plan(
    monkeypatch: pytest.MonkeyPatch,
    *,
    point_ids: set[int],
    points: list[SimpleNamespace],
    system: SimpleNamespace | None = None,
) -> list[PoliticsModuleQuota]:
    selected_system = system or SimpleNamespace(id=8, code='kaoyan_politics', status='active')
    monkeypatch.setattr(module.knowledge_system_dao, 'get', AsyncMock(return_value=selected_system))
    monkeypatch.setattr(module.knowledge_point_dao, 'get_all', AsyncMock(return_value=points))
    obj = SimpleNamespace(knowledge_system_id=8, paper_profile='kaoyan_politics')
    return asyncio.run(PracticeService._politics_plan(db=None, obj=obj, point_ids=set(point_ids)))


def test_real_plan_locates_system_and_full_scope_from_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    points, identifiers = _politics_points()
    point_ids = {identifiers[item.code] for item in POLITICS_MODULES}

    plan = _run_plan(monkeypatch, point_ids=point_ids, points=points)

    assert [quota.module.code for quota in plan] == [item.code for item in POLITICS_MODULES]
    assert [quota.single_count for quota in plan] == [EXPECTED_SINGLE[item.code] for item in POLITICS_MODULES]
    assert module.knowledge_system_dao.get.await_args.args[1] == 8


def test_real_plan_accepts_any_leaf_under_a_module(monkeypatch: pytest.MonkeyPatch) -> None:
    points, identifiers = _politics_points()

    plan = _run_plan(monkeypatch, point_ids={identifiers['mayuan_deep_leaf']}, points=points)

    assert len(plan) == 1
    assert plan[0].module.code == 'kaoyan_politics_mayuan'
    assert plan[0].point_ids == frozenset({identifiers['mayuan_deep_leaf']})
    assert plan[0].single_count == 16
    assert plan[0].multiple_count == 17


def test_real_plan_keeps_parent_and_child_overlap_without_double_count(monkeypatch: pytest.MonkeyPatch) -> None:
    points, identifiers = _politics_points()
    root_id = identifiers['kaoyan_politics_mayuan']
    leaf_id = identifiers['mayuan_leaf']

    plan = _run_plan(monkeypatch, point_ids={root_id, leaf_id}, points=points)

    assert len(plan) == 1
    assert plan[0].module.code == 'kaoyan_politics_mayuan'
    assert plan[0].point_ids == frozenset({root_id, leaf_id})
    assert plan[0].single_count == 16
    assert plan[0].multiple_count == 17


@pytest.mark.parametrize('selector', ['misc_leaf', 'cross_system', 'empty'])
def test_real_plan_rejects_unknown_branch_cross_system_and_empty_scope(
    monkeypatch: pytest.MonkeyPatch,
    selector: str,
) -> None:
    points, identifiers = _politics_points()
    point_ids = {
        'misc_leaf': {identifiers['misc_leaf']},
        'cross_system': {999999},
        'empty': set(),
    }[selector]

    with pytest.raises(errors.RequestError):
        _run_plan(monkeypatch, point_ids=point_ids, points=points)


def test_real_plan_rejects_foreign_knowledge_system(monkeypatch: pytest.MonkeyPatch) -> None:
    points, identifiers = _politics_points()

    with pytest.raises(errors.RequestError):
        _run_plan(
            monkeypatch,
            point_ids={identifiers['mayuan_leaf']},
            points=points,
            system=SimpleNamespace(id=8, code='gongkao', status='active'),
        )


@pytest.mark.parametrize('missing_code', ['kaoyan_politics', 'kaoyan_politics_shizheng'])
def test_real_plan_rejects_incomplete_taxonomy_without_reweighting(
    monkeypatch: pytest.MonkeyPatch, missing_code: str
) -> None:
    points, identifiers = _politics_points()
    points = [point for point in points if point.code != missing_code]
    with pytest.raises(errors.RequestError, match='不完整'):
        _run_plan(monkeypatch, point_ids={identifiers['mayuan_leaf']}, points=points)


def test_real_plan_infers_system_when_request_omits_system_id(monkeypatch: pytest.MonkeyPatch) -> None:
    points, identifiers = _politics_points()
    monkeypatch.setattr(
        module.knowledge_system_dao, 'get', AsyncMock(return_value=SimpleNamespace(code='kaoyan_politics'))
    )
    monkeypatch.setattr(module.knowledge_point_dao, 'get_all', AsyncMock(return_value=points))
    monkeypatch.setattr(module.knowledge_service, 'resolve_point_system_id', AsyncMock(return_value=8))
    point_id = identifiers['mayuan_deep_leaf']
    obj = _politics_obj(knowledge_point_ids=[point_id], knowledge_system_id=None)

    plan = asyncio.run(PracticeService._politics_plan(db=None, obj=obj, point_ids={point_id}))

    assert plan[0].point_ids == frozenset({point_id})
    module.knowledge_service.resolve_point_system_id.assert_awaited_once_with(db=None, point_ids=[point_id])


# ---------------------------------------------------------------------------
# 按题型再按模块抽题：分值、顺序、primary 过滤、整卷唯一
# ---------------------------------------------------------------------------


def _small_plan() -> list[PoliticsModuleQuota]:
    return [
        PoliticsModuleQuota(
            module=_module('kaoyan_politics_mayuan'),
            point_ids=frozenset({101, 102}),
            single_count=2,
            multiple_count=3,
        ),
        PoliticsModuleQuota(
            module=_module('kaoyan_politics_sixiu'),
            point_ids=frozenset({201}),
            single_count=1,
            multiple_count=2,
        ),
    ]


def _run_candidates(
    monkeypatch: pytest.MonkeyPatch,
    *,
    plan: list[PoliticsModuleQuota] | None,
    rows: Any = None,
    point_ids: set[int] | None = None,
) -> tuple[list[PracticeCandidate], list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []
    cursor = itertools.count(1)

    def dispatch(_db: Any, **kwargs: Any) -> list[PracticeCandidate]:
        calls.append(kwargs)
        if rows is not None:
            return rows(kwargs)
        return [_candidate(next(cursor)) for _ in range(kwargs['limit'])]

    monkeypatch.setattr(
        module.practice_session_item_dao,
        'get_user_candidates',
        AsyncMock(side_effect=dispatch),
    )
    result = asyncio.run(
        PracticeService._politics_candidates(
            db=None,
            user_id=7,
            obj=_politics_obj(),
            point_ids={101, 102, 201} if point_ids is None else point_ids,
            plan=plan,
        )
    )
    return result, calls


def test_candidates_draw_single_then_multiple_for_each_module(monkeypatch: pytest.MonkeyPatch) -> None:
    result, calls = _run_candidates(monkeypatch, plan=_small_plan())

    assert [call['question_types'] for call in calls] == [
        ['single_choice'],
        ['single_choice'],
        ['multiple_choice'],
        ['multiple_choice'],
    ]
    assert [call['limit'] for call in calls] == [2, 1, 3, 2]
    assert [call['knowledge_point_ids'] for call in calls] == [[101, 102], [201], [101, 102], [201]]
    assert [item.max_score for item in result] == [Decimal(1)] * 3 + [Decimal(2)] * 5
    assert [len({item.question_id for item in result})] == [len(result)]
    assert [item.display_config['paper_module_code'] for item in result] == [
        'kaoyan_politics_mayuan',
        'kaoyan_politics_mayuan',
        'kaoyan_politics_sixiu',
        'kaoyan_politics_mayuan',
        'kaoyan_politics_mayuan',
        'kaoyan_politics_mayuan',
        'kaoyan_politics_sixiu',
        'kaoyan_politics_sixiu',
    ]


def test_candidates_always_filter_primary_knowledge_point_role(monkeypatch: pytest.MonkeyPatch) -> None:
    _result, calls = _run_candidates(monkeypatch, plan=_small_plan())

    assert calls
    assert all(call['knowledge_point_role'] == 'primary' for call in calls)


def test_candidates_build_plan_when_not_supplied(monkeypatch: pytest.MonkeyPatch) -> None:
    plan_calls: list[set[int]] = []

    async def fake_plan(db: Any = None, obj: Any = None, point_ids: Any = None) -> list[PoliticsModuleQuota]:
        await asyncio.sleep(0)
        plan_calls.append(set(point_ids or ()))
        return _small_plan()

    monkeypatch.setattr(PracticeService, '_politics_plan', fake_plan, raising=False)

    _result, _calls = _run_candidates(monkeypatch, plan=None)

    assert plan_calls == [{101, 102, 201}]


def test_candidates_fail_whole_paper_when_one_module_type_is_short(monkeypatch: pytest.MonkeyPatch) -> None:
    def short_rows(kwargs: dict[str, Any]) -> list[PracticeCandidate]:
        if kwargs['knowledge_point_ids'] == [101, 102] and kwargs['question_types'] == ['single_choice']:
            return [_candidate(1)]
        return [_candidate(100 + index) for index in range(kwargs['limit'])]

    with pytest.raises(errors.RequestError) as error:
        _run_candidates(monkeypatch, plan=_small_plan(), rows=short_rows)

    message = str(error.value)
    assert 'kaoyan_politics_mayuan' in message or _module('kaoyan_politics_mayuan').name in message
    assert '单选' in message


def test_candidates_reject_question_already_used_by_another_module(monkeypatch: pytest.MonkeyPatch) -> None:
    def duplicate_rows(kwargs: dict[str, Any]) -> list[PracticeCandidate]:
        if kwargs['knowledge_point_ids'] == [101, 102]:
            return [_candidate(1), _candidate(2)]
        return [_candidate(1)]

    with pytest.raises(errors.RequestError):
        _run_candidates(monkeypatch, plan=_small_plan(), rows=duplicate_rows)


# ---------------------------------------------------------------------------
# create：先计划再抽题、蓝图快照、分值固定、旧会话不重抽
# ---------------------------------------------------------------------------


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
            'paper_profile': obj.paper_profile,
        },
    )


def _patch_create(
    monkeypatch: pytest.MonkeyPatch,
    *,
    plan: list[PoliticsModuleQuota],
    resolved: set[int],
    existing: Any = None,
    detail: Any = None,
    rows: Any = None,
    forbid_draw: bool = False,
) -> dict[str, Any]:
    captured: dict[str, Any] = {'calls': [], 'plan_calls': []}
    cursor = itertools.count(1)
    session_detail = detail or SimpleNamespace(session_key='created-session')

    async def fake_plan(db: Any = None, obj: Any = None, point_ids: Any = None) -> list[PoliticsModuleQuota]:
        await asyncio.sleep(0)
        captured['plan_calls'].append(set(point_ids or ()))
        return plan

    def resolve_points(**_kwargs: Any) -> set[int]:
        return set(resolved)

    def get_by_key(*_args: Any, **_kwargs: Any) -> Any:
        return existing

    def get_candidates(_db: Any, **kwargs: Any) -> list[PracticeCandidate]:
        captured['calls'].append(kwargs)
        if forbid_draw:
            raise AssertionError('现有会话不得重新抽题')
        if rows is not None:
            return rows(kwargs)
        return [_candidate(next(cursor)) for _ in range(kwargs['limit'])]

    def create_session(_db: Any, values: dict[str, Any]) -> Any:
        captured['values'] = values
        return SimpleNamespace(id=1, session_key=values['session_key'])

    def create_items(_db: Any, **kwargs: Any) -> None:
        captured['items'] = kwargs['candidates']

    def get_detail(**_kwargs: Any) -> Any:
        return session_detail

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))
    monkeypatch.setattr(module.knowledge_service, 'resolve_point_system_id', AsyncMock(return_value=8))
    monkeypatch.setattr(module.practice_session_dao, 'get_by_key', AsyncMock(side_effect=get_by_key))
    monkeypatch.setattr(PracticeService, '_politics_plan', fake_plan, raising=False)
    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))
    monkeypatch.setattr(module.practice_session_dao, 'create', AsyncMock(side_effect=create_session))
    monkeypatch.setattr(module.practice_session_item_dao, 'create_all', AsyncMock(side_effect=create_items))
    monkeypatch.setattr(PracticeService, 'get', AsyncMock(side_effect=get_detail))
    return captured


def _two_module_plan() -> list[PoliticsModuleQuota]:
    return build_politics_quotas([
        (_module('kaoyan_politics_mayuan'), frozenset({101, 102})),
        (_module('kaoyan_politics_sixiu'), frozenset({201})),
    ])


def test_create_generates_plan_then_persists_blueprint_and_fixed_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = _patch_create(monkeypatch, plan=_two_module_plan(), resolved={101, 102, 201})

    result = asyncio.run(PracticeService.create(db=None, user_id=7, obj=_politics_obj()))

    assert result.session_key == 'created-session'
    assert captured['plan_calls'] == [{101, 102, 201}]
    values = captured['values']
    items = captured['items']
    assert values['total_items'] == 33
    assert len(items) == 33
    assert [item.max_score for item in items[:16]] == [Decimal(1)] * 16
    assert [item.max_score for item in items[16:]] == [Decimal(2)] * 17
    assert [item.display_config['paper_module_code'] for item in items[:13]] == ['kaoyan_politics_mayuan'] * 13
    assert [item.display_config['paper_module_code'] for item in items[13:16]] == ['kaoyan_politics_sixiu'] * 3
    assert [item.display_config['paper_module_code'] for item in items[16:28]] == ['kaoyan_politics_mayuan'] * 12
    assert [item.display_config['paper_module_code'] for item in items[28:]] == ['kaoyan_politics_sixiu'] * 5

    blueprint = values['source_snapshot']['politics_blueprint']
    assert blueprint['version'] == 'real_2025_2026_v1'
    snapshots = blueprint['module_quotas']
    assert [_snapshot_code(snapshot) for snapshot in snapshots] == [
        'kaoyan_politics_mayuan',
        'kaoyan_politics_sixiu',
    ]
    assert [snapshot['single_count'] for snapshot in snapshots] == [13, 3]
    assert [snapshot['multiple_count'] for snapshot in snapshots] == [12, 5]
    assert values['delivery_config']['paper_profile'] == 'kaoyan_politics'
    assert values['delivery_config']['requested_limit'] == 33


@pytest.mark.parametrize('mode', ['practice', 'exam'])
def test_create_full_blueprint_draws_all_six_modules_with_exact_scores(
    monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    scopes = [(item, frozenset({100 + index})) for index, item in enumerate(POLITICS_MODULES)]
    plan = build_politics_quotas(scopes)
    captured = _patch_create(monkeypatch, plan=plan, resolved=set(range(100, 106)))

    asyncio.run(PracticeService.create(db=None, user_id=7, obj=_politics_obj(mode=mode)))

    assert len(captured['calls']) == 12
    assert [call['limit'] for call in captured['calls']] == [4, 2, 3, 4, 1, 2, 5, 1, 4, 3, 2, 2]
    items = captured['items']
    assert len({item.question_id for item in items}) == 33
    assert sum(item.max_score for item in items) == Decimal(50)
    assert captured['values']['source_snapshot']['politics_blueprint']['module_quotas'] == [
        quota.as_snapshot() for quota in plan
    ]
    expected_excluded_counts = [0, 4, 6, 9, 13, 14, 16, 21, 22, 26, 29, 31]
    assert [len(call['exclude_question_ids']) for call in captured['calls']] == expected_excluded_counts


def test_create_short_module_does_not_persist_session(monkeypatch: pytest.MonkeyPatch) -> None:
    cursor = itertools.count(1000)

    def short_rows(kwargs: dict[str, Any]) -> list[PracticeCandidate]:
        if kwargs['knowledge_point_ids'] == [201] and kwargs['question_types'] == ['multiple_choice']:
            return [_candidate(next(cursor))]
        return [_candidate(next(cursor)) for _ in range(kwargs['limit'])]

    captured = _patch_create(
        monkeypatch,
        plan=_two_module_plan(),
        resolved={101, 102, 201},
        rows=short_rows,
    )

    with pytest.raises(errors.RequestError) as error:
        asyncio.run(PracticeService.create(db=None, user_id=7, obj=_politics_obj()))

    assert 'values' not in captured
    assert 'items' not in captured
    message = str(error.value)
    assert 'kaoyan_politics_sixiu' in message or _module('kaoyan_politics_sixiu').name in message
    assert '多选' in message


def test_create_reuses_existing_paper_session_without_redrawing(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = _politics_obj(session_key='politics_blueprint_existing')
    existing = _matching_session(obj)
    existing.source_snapshot['politics_blueprint'] = {'version': 'legacy_v0', 'module_quotas': []}
    expected = SimpleNamespace(session_key='politics_blueprint_existing')

    captured = _patch_create(
        monkeypatch,
        plan=_two_module_plan(),
        resolved={101, 102, 201},
        existing=existing,
        detail=expected,
        forbid_draw=True,
    )

    assert asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj)) is expected
    assert captured['plan_calls'] == []
    assert captured['calls'] == []
    assert existing.source_snapshot['politics_blueprint'] == {'version': 'legacy_v0', 'module_quotas': []}
