"""备考目标分类树：结构边界、末级选择、严格组卷、快照与旧会话兼容回归。"""

import asyncio
import importlib

from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError

from backend.app.question_bank_v2.schema.study_goal import (
    CreateGoalExamParam,
    ExamCategory,
    ExamTargetConfig,
    StudyGoal,
)
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.app.question_bank_v2.service.study_goal_service import StudyGoalService, study_goal_service
from backend.common.exception import errors

study_goal_service_module = importlib.import_module('backend.app.question_bank_v2.service.study_goal_service')
T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """同步执行协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


def _categories() -> list[dict[str, Any]]:
    return [
        {
            'code': 'xinjiang',
            'name': '新疆',
            'children': [
                {
                    'code': 'qukao',
                    'name': '区考',
                    'children': [
                        {'code': 'bingtuan', 'name': '兵团', 'children': []},
                        {'code': 'difang', 'name': '地方', 'children': []},
                    ],
                },
            ],
        },
        {'code': 'national', 'name': '国考', 'children': []},
    ]


def _template(**overrides: Any) -> dict[str, Any]:
    template: dict[str, Any] = {
        'key': 'basic',
        'name': '基础卷',
        'subject': 'xingce',
        'subject_name': '行测',
        'category_code': 'bingtuan',
        'years': [],
        'knowledge_system_id': 11,
        'bank_id': 21,
        'total': 2,
        'duration_minutes': 30,
        'modules': [{'knowledge_point_id': 201, 'name': '言语理解', 'count': 2}],
    }
    template.update(overrides)
    return template


def _config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        'version': '2026.1',
        'domain_code': 'gongkao',
        'region_code': None,
        'exam_kind': 'national',
        'years': [2026],
        'subjects': {'xingce': '行测', 'shenlun': '申论'},
        'categories': _categories(),
        'templates': [_template()],
    }
    config.update(overrides)
    return config


def _row(config: dict[str, Any] | None = None, *, value: str = 'gk_2026', label: str = '国考2026') -> SimpleNamespace:
    return SimpleNamespace(value=value, label=label, extra=config if config is not None else _config())


def _goal(**overrides: Any) -> dict[str, Any]:
    goal: dict[str, Any] = {
        'exam_target_code': 'gk_2026',
        'exam_year': 2026,
        'category_code': 'bingtuan',
        'subjects': ['xingce'],
        'target_scores': {},
    }
    goal.update(overrides)
    return goal


def _obj(**overrides: Any) -> CreateGoalExamParam:
    data: dict[str, Any] = {
        'exam_target_code': 'gk_2026',
        'exam_year': 2026,
        'category_code': 'bingtuan',
        'template_key': 'basic',
        'config_revision': StudyGoalService.parse_target(_row()).config_revision,
        'session_key': 'goal_cat01',
    }
    data.update(overrides)
    return CreateGoalExamParam(**data)


# ---------------------------------------------------------------------------
# 分类树结构边界
# ---------------------------------------------------------------------------


def test_category_tree_accepts_nested_xinjiang_qukao_bingtuan() -> None:
    config = ExamTargetConfig(**_config())

    path = config.category_path('bingtuan')

    assert [(node.code, node.name) for node in path] == [('xinjiang', '新疆'), ('qukao', '区考'), ('bingtuan', '兵团')]
    assert path[-1].children == []


def test_category_path_returns_parent_for_parent_code_and_empty_for_unknown() -> None:
    config = ExamTargetConfig(**_config())

    assert [node.code for node in config.category_path('qukao')] == ['xinjiang', 'qukao']
    assert config.category_path('missing') == []
    assert config.category_path(None) == []


def test_category_codes_must_be_unique_across_tree() -> None:
    categories = [
        {'code': 'xinjiang', 'name': '新疆', 'children': [{'code': 'bingtuan', 'name': '兵团', 'children': []}]},
        {'code': 'xinjiang', 'name': '重复', 'children': []},
    ]

    with pytest.raises(ValidationError, match='目标内考试类别编码不能重复，名称不能为空'):
        ExamTargetConfig(**_config(categories=categories))


def test_category_name_must_not_be_blank() -> None:
    with pytest.raises(ValidationError, match='目标内考试类别编码不能重复，名称不能为空'):
        ExamTargetConfig(**_config(categories=[{'code': 'xinjiang', 'name': '   ', 'children': []}]))


@pytest.mark.parametrize('code', ['Xinjiang', 'xin-jiang', '新疆', ''])
def test_category_code_must_be_lowercase_token(code: str) -> None:
    with pytest.raises(ValidationError):
        ExamCategory(code=code, name='新疆')


def _chain(levels: int) -> list[dict[str, Any]]:
    root: dict[str, Any] = {'code': 'l1', 'name': '一级', 'children': []}
    node = root
    for depth in range(2, levels + 1):
        child: dict[str, Any] = {'code': f'l{depth}', 'name': f'{depth}级', 'children': []}
        node['children'] = [child]
        node = child
    return [root]


def _forest(branches: int, per_branch: int) -> list[dict[str, Any]]:
    return [
        {
            'code': f'r{index}',
            'name': f'根{index}',
            'children': [
                {'code': f'r{index}c{child}', 'name': f'叶{child}', 'children': []} for child in range(per_branch)
            ],
        }
        for index in range(branches)
    ]


def test_category_tree_allows_five_levels() -> None:
    config = ExamTargetConfig(**_config(categories=_chain(5), templates=[]))

    assert len(config.category_path('l5')) == 5


def test_category_tree_rejects_sixth_level() -> None:
    with pytest.raises(ValidationError, match='考试类别最多5层、200个节点'):
        ExamTargetConfig(**_config(categories=_chain(6), templates=[]))


def test_category_tree_allows_two_hundred_nodes() -> None:
    config = ExamTargetConfig(**_config(categories=_forest(4, 49), templates=[]))

    assert len(config.categories) == 4
    assert sum(1 + len(node.children) for node in config.categories) == 200


def test_category_tree_rejects_more_than_two_hundred_nodes() -> None:
    with pytest.raises(ValidationError, match='考试类别最多5层、200个节点'):
        ExamTargetConfig(**_config(categories=_forest(4, 50), templates=[]))


@pytest.mark.parametrize('category_code', [None, 'xinjiang', 'qukao'])
def test_template_must_bind_leaf_category_when_tree_exists(category_code: str | None) -> None:
    with pytest.raises(ValidationError, match='组卷模板必须绑定本目标的末级考试类别；无类别目录不能指定类别'):
        ExamTargetConfig(**_config(templates=[_template(category_code=category_code)]))


def test_target_without_categories_forbids_template_category() -> None:
    with pytest.raises(ValidationError, match='组卷模板必须绑定本目标的末级考试类别；无类别目录不能指定类别'):
        ExamTargetConfig(**_config(categories=[], templates=[_template()]))


def test_config_revision_changes_with_category_tree() -> None:
    first = StudyGoalService.parse_target(_row(_config()))
    same = StudyGoalService.parse_target(_row(_config()))
    changed = StudyGoalService.parse_target(
        _row(
            _config(
                categories=[{'code': 'national', 'name': '国考', 'children': []}],
                templates=[_template(category_code='national')],
            ),
        ),
    )

    assert first.config_revision == same.config_revision
    assert first.config_revision != changed.config_revision


def test_target_without_categories_accepts_null_template_category() -> None:
    config = ExamTargetConfig(**_config(categories=[], templates=[_template(category_code=None)]))

    assert config.categories == []
    assert config.templates[0].category_code is None


@pytest.mark.parametrize('years', [[2025], [2026, 2026]])
def test_template_years_must_be_unique_and_within_target(years: list[int]) -> None:
    with pytest.raises(ValidationError, match='模板年度不能重复且必须属于目标年度'):
        ExamTargetConfig(**_config(templates=[_template(years=years)]))


# ---------------------------------------------------------------------------
# 目标保存与旧偏好补选
# ---------------------------------------------------------------------------


def _patch_targets(monkeypatch: pytest.MonkeyPatch, rows: list[SimpleNamespace] | None = None) -> None:
    monkeypatch.setattr(
        study_goal_service_module.study_goal_dao,
        'get_targets',
        AsyncMock(return_value=rows if rows is not None else [_row()]),
    )


def test_validate_goal_accepts_leaf_category(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_targets(monkeypatch)

    target = run(study_goal_service.validate_goal(db=None, goal=StudyGoal(**_goal())))

    assert target.code == 'gk_2026'


@pytest.mark.parametrize('category_code', ['xinjiang', 'qukao'])
def test_validate_goal_rejects_parent_category(monkeypatch: pytest.MonkeyPatch, category_code: str) -> None:
    _patch_targets(monkeypatch)

    with pytest.raises(errors.RequestError, match='请选择该目标的末级考试类别'):
        run(study_goal_service.validate_goal(db=None, goal=StudyGoal(**_goal(category_code=category_code))))


def test_validate_goal_rejects_unknown_category(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_targets(monkeypatch)

    with pytest.raises(errors.RequestError, match='请选择该目标的末级考试类别'):
        run(study_goal_service.validate_goal(db=None, goal=StudyGoal(**_goal(category_code='missing'))))


def test_validate_goal_rejects_category_for_target_without_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_targets(monkeypatch, [_row(_config(categories=[], templates=[_template(category_code=None)]))])

    with pytest.raises(errors.RequestError, match='该目标没有此考试类别'):
        run(study_goal_service.validate_goal(db=None, goal=StudyGoal(**_goal(category_code='national'))))


def test_legacy_goal_reads_without_category_and_requires_reselection(monkeypatch: pytest.MonkeyPatch) -> None:
    legacy = {
        'exam_target_code': 'gk_2026',
        'exam_year': 2026,
        'subjects': ['xingce'],
        'target_scores': {},
    }
    goal = StudyGoal.model_validate(legacy)
    _patch_targets(monkeypatch)

    assert goal.category_code is None
    with pytest.raises(errors.RequestError, match='旧目标需要补选类别'):
        run(study_goal_service.validate_goal(db=None, goal=goal))


def test_legacy_goal_without_tree_still_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_targets(monkeypatch, [_row(_config(categories=[], templates=[_template(category_code=None)]))])

    target = run(study_goal_service.validate_goal(db=None, goal=StudyGoal(**_goal(category_code=None))))

    assert target.code == 'gk_2026'


# ---------------------------------------------------------------------------
# 组卷严格匹配、快照与幂等隔离
# ---------------------------------------------------------------------------


def _patch_create_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rows: list[SimpleNamespace] | None = None,
    goal: dict[str, Any] | None = None,
    existing: Any = None,
) -> None:
    monkeypatch.setattr(
        study_goal_service_module.study_goal_dao,
        'get_targets',
        AsyncMock(return_value=rows if rows is not None else [_row()]),
    )
    monkeypatch.setattr(
        study_goal_service_module.practice_session_dao,
        'get_by_key',
        AsyncMock(return_value=existing),
    )
    monkeypatch.setattr(
        study_goal_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=SimpleNamespace(study_goal=goal if goal is not None else _goal())),
    )
    monkeypatch.setattr(StudyGoalService, 'validate_config', AsyncMock())


def test_create_exam_snapshots_category_path_and_title(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_create_dependencies(monkeypatch)
    captured: dict[str, Any] = {}

    async def fake_create(**kwargs: Any) -> Any:
        await asyncio.sleep(0)
        captured.update(kwargs)
        return SimpleNamespace(session_key='created-session')

    monkeypatch.setattr(practice_service, 'create', fake_create)

    obj = _obj()
    result = run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))

    assert result.session_key == 'created-session'
    assert captured['obj'].title == '2026 国考2026 · 新疆 / 区考 / 兵团 · 基础卷'
    context = captured['goal_context']
    assert context['category_path'] == [
        {'code': 'xinjiang', 'name': '新疆'},
        {'code': 'qukao', 'name': '区考'},
        {'code': 'bingtuan', 'name': '兵团'},
    ]
    assert context['request'] == obj.model_dump(exclude={'session_key'})
    assert context['goal']['category_code'] == 'bingtuan'


def test_create_exam_rejects_request_category_mismatch_preference(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_create_dependencies(monkeypatch)

    with pytest.raises(errors.ConflictError, match='备考目标已变更'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj(category_code='difang')))


def test_create_exam_rejects_template_from_other_category(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(
        templates=[
            _template(key='basic', category_code='bingtuan'),
            _template(key='essay', name='申论卷', subject='shenlun', subject_name='申论', category_code='difang'),
        ],
    )
    _patch_create_dependencies(monkeypatch, rows=[_row(config)], goal=_goal(subjects=['xingce', 'shenlun']))
    obj = _obj(
        template_key='essay',
        config_revision=StudyGoalService.parse_target(_row(config)).config_revision,
    )

    with pytest.raises(errors.RequestError, match='暂无此组卷模板'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))


def test_create_exam_rejects_template_outside_goal_year(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(years=[2025, 2026], templates=[_template(years=[2025])])
    _patch_create_dependencies(monkeypatch, rows=[_row(config)])
    obj = _obj(config_revision=StudyGoalService.parse_target(_row(config)).config_revision)

    with pytest.raises(errors.RequestError, match='暂无此组卷模板'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))


def test_create_exam_retry_reuses_snapshot_for_same_category(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = _obj()
    request = obj.model_dump(exclude={'session_key'})
    existing = SimpleNamespace(source_snapshot={'study_goal': {'request': request}})
    _patch_create_dependencies(monkeypatch, existing=existing)
    preference = AsyncMock()
    monkeypatch.setattr(study_goal_service_module.practice_preference_dao, 'get_by_user_id', preference)
    detail = SimpleNamespace(session_key=obj.session_key)
    monkeypatch.setattr(practice_service, 'get', AsyncMock(return_value=detail))

    result = run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))

    assert result is detail
    assert preference.await_count == 0


def test_create_exam_rejects_same_session_key_with_changed_category(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _obj(category_code='difang').model_dump(exclude={'session_key'})
    existing = SimpleNamespace(source_snapshot={'study_goal': {'request': request}})
    _patch_create_dependencies(monkeypatch, existing=existing)

    with pytest.raises(errors.ConflictError, match='会话标识已被其他请求使用'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj(category_code='bingtuan')))


def test_legacy_session_without_category_retries_as_null(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = _obj(category_code=None)
    legacy_request = {
        'exam_target_code': 'gk_2026',
        'exam_year': 2026,
        'template_key': 'basic',
        'config_revision': obj.config_revision,
    }
    existing = SimpleNamespace(source_snapshot={'study_goal': {'request': legacy_request}})
    _patch_create_dependencies(monkeypatch, existing=existing)
    preference = AsyncMock()
    monkeypatch.setattr(study_goal_service_module.practice_preference_dao, 'get_by_user_id', preference)
    detail = SimpleNamespace(session_key=obj.session_key)
    monkeypatch.setattr(practice_service, 'get', AsyncMock(return_value=detail))

    result = run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))

    assert result is detail
    assert preference.await_count == 0


def test_legacy_session_without_category_cannot_retry_with_category(monkeypatch: pytest.MonkeyPatch) -> None:
    legacy_request = {
        'exam_target_code': 'gk_2026',
        'exam_year': 2026,
        'template_key': 'basic',
        'config_revision': _obj().config_revision,
    }
    existing = SimpleNamespace(source_snapshot={'study_goal': {'request': legacy_request}})
    _patch_create_dependencies(monkeypatch, existing=existing)

    with pytest.raises(errors.ConflictError, match='会话标识已被其他请求使用'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj(category_code='bingtuan')))


def test_create_exam_without_tree_keeps_null_category_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(categories=[], templates=[_template(category_code=None)])
    _patch_create_dependencies(monkeypatch, rows=[_row(config)], goal=_goal(category_code=None))
    captured: dict[str, Any] = {}

    async def fake_create(**kwargs: Any) -> Any:
        await asyncio.sleep(0)
        captured.update(kwargs)
        return SimpleNamespace(session_key='plain-session')

    monkeypatch.setattr(practice_service, 'create', fake_create)
    obj = _obj(
        category_code=None,
        config_revision=StudyGoalService.parse_target(_row(config)).config_revision,
    )

    result = run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))

    assert result.session_key == 'plain-session'
    assert captured['goal_context']['category_path'] == []
    assert captured['obj'].title == '2026 国考2026 · 基础卷'
