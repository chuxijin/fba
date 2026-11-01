"""备考目标：目标/模板校验、偏好读写、组卷快照与幂等隔离回归。"""

import asyncio
import importlib

from collections.abc import Coroutine
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError

from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank_v2.schema.preference import UpdatePracticePreferenceParam
from backend.app.question_bank_v2.schema.study_goal import (
    CreateGoalExamParam,
    ExamModule,
    ExamTargetConfig,
    ExamTemplate,
    StudyGoal,
)
from backend.app.question_bank_v2.service.practice_service import PracticeService, practice_service
from backend.app.question_bank_v2.service.preference_service import preference_service
from backend.app.question_bank_v2.service.study_goal_service import StudyGoalService, study_goal_service
from backend.common.exception import errors

study_goal_service_module = importlib.import_module('backend.app.question_bank_v2.service.study_goal_service')
preference_service_module = importlib.import_module('backend.app.question_bank_v2.service.preference_service')
T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """同步执行协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


def _template(**overrides: Any) -> dict[str, Any]:
    template: dict[str, Any] = {
        'key': 'basic',
        'name': '基础卷',
        'subject': 'xingce',
        'subject_name': '行测',
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
        'subjects': {'xingce': '行测'},
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
        'subjects': ['xingce'],
        'target_scores': {},
    }
    goal.update(overrides)
    return goal


def _obj(**overrides: Any) -> CreateGoalExamParam:
    data: dict[str, Any] = {
        'exam_target_code': 'gk_2026',
        'exam_year': 2026,
        'template_key': 'basic',
        'config_revision': StudyGoalService.parse_target(_row()).config_revision,
        'session_key': 'goal_session01',
    }
    data.update(overrides)
    return CreateGoalExamParam(**data)


class FakeSession:
    """validate_config 只用 db.scalar 读取领域分类编码"""

    def __init__(self, domain_code: str = 'pc_gongkao') -> None:
        self.domain_code = domain_code

    async def scalar(self, _statement: Any) -> str:
        return self.domain_code


# ---------------------------------------------------------------------------
# Schema 校验
# ---------------------------------------------------------------------------


def test_goal_schemas_forbid_unknown_extra_fields() -> None:
    with pytest.raises(ValidationError, match='Extra inputs are not permitted'):
        StudyGoal(**_goal(), unknown='x')
    with pytest.raises(ValidationError, match='Extra inputs are not permitted'):
        ExamModule(knowledge_point_id=201, name='言语理解', count=1, bank_id=21)
    with pytest.raises(ValidationError, match='Extra inputs are not permitted'):
        CreateGoalExamParam(
            exam_target_code='gk_2026',
            exam_year=2026,
            template_key='basic',
            config_revision='a' * 64,
            session_key='goal_session01',
            bank_id=21,
            duration_minutes=10,
        )


def test_exam_template_quota_total_must_equal_total() -> None:
    with pytest.raises(ValidationError, match='模块不能重复，且模块题量之和必须等于总题数'):
        ExamTargetConfig(**_config(templates=[_template(total=3)]))


def test_exam_template_rejects_duplicate_modules() -> None:
    modules = [
        {'knowledge_point_id': 201, 'name': '言语理解', 'count': 1},
        {'knowledge_point_id': 201, 'name': '言语理解', 'count': 1},
    ]
    with pytest.raises(ValidationError, match='模块不能重复'):
        ExamTemplate(**_template(modules=modules, total=2))


@pytest.mark.parametrize('years', [[2026, 2026], [1899], [2101], []])
def test_exam_target_rejects_invalid_years(years: list[int]) -> None:
    with pytest.raises(ValidationError):
        ExamTargetConfig(**_config(years=years))


def test_exam_target_rejects_duplicate_template_keys() -> None:
    with pytest.raises(ValidationError, match='组卷模板编码不能重复'):
        ExamTargetConfig(**_config(templates=[_template(), _template(name='第二套')]))


@pytest.mark.parametrize(
    'config',
    [
        {'subjects': {'xingce': '行测'}, 'templates': [_template(subject='shenlun', subject_name='申论')]},
        {'subjects': {'xingce': '行测'}, 'templates': [_template(subject_name='申论')]},
        {'subjects': {'': '行测'}, 'templates': []},
        {'subjects': {'xingce': 'x' * 33}, 'templates': []},
    ],
)
def test_exam_target_rejects_invalid_subjects(config: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ExamTargetConfig(**_config(**config))


def test_study_goal_rejects_duplicate_or_blank_subjects() -> None:
    with pytest.raises(ValidationError, match='备考科目不能重复'):
        StudyGoal(**_goal(subjects=['xingce', 'xingce']))
    with pytest.raises(ValidationError, match='备考科目编码无效'):
        StudyGoal(**_goal(subjects=['']))


@pytest.mark.parametrize('score', [Decimal('-0.01'), Decimal('1000.01')])
def test_study_goal_rejects_invalid_target_scores(score: Decimal) -> None:
    with pytest.raises(ValidationError, match='目标成绩必须对应已选科目且为0至1000的有限数值'):
        StudyGoal(**_goal(target_scores={'xingce': score}))


def test_study_goal_rejects_nan_target_score() -> None:
    with pytest.raises(ValidationError):
        StudyGoal(**_goal(target_scores={'xingce': Decimal('NaN')}))


def test_study_goal_rejects_score_for_unselected_subject() -> None:
    with pytest.raises(ValidationError, match='目标成绩必须对应已选科目且为0至1000的有限数值'):
        StudyGoal(**_goal(target_scores={'shenlun': Decimal(60)}))


@pytest.mark.parametrize('exam_year', [1899, 2101])
def test_study_goal_rejects_out_of_range_exam_year(exam_year: int) -> None:
    with pytest.raises(ValidationError):
        StudyGoal(**_goal(exam_year=exam_year))


# ---------------------------------------------------------------------------
# 目标目录读取与指纹
# ---------------------------------------------------------------------------


def test_parse_target_rejects_invalid_code_or_config() -> None:
    with pytest.raises(errors.RequestError, match='配置无效'):
        StudyGoalService.parse_target(_row(value='Bad-Code'))
    with pytest.raises(errors.RequestError, match='配置无效'):
        StudyGoalService.parse_target(_row(_config(domain_code='unknown')))


def test_config_revision_is_stable_and_changes_with_config() -> None:
    first = StudyGoalService.parse_target(_row(_config()))
    same = StudyGoalService.parse_target(_row(_config()))
    changed = StudyGoalService.parse_target(_row(_config(templates=[_template(duration_minutes=60)])))

    assert first.config_revision == same.config_revision
    assert first.config_revision != changed.config_revision


def test_get_targets_filters_by_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    cet_config = _config(domain_code='cet', subjects={'cet4': '四级'}, templates=[])
    rows = [_row(), _row(cet_config, value='cet_2026', label='四级2026')]
    monkeypatch.setattr(study_goal_service_module.study_goal_dao, 'get_targets', AsyncMock(return_value=rows))

    targets = run(study_goal_service.get_targets(db=None, domain_code='gongkao'))

    assert [target.code for target in targets] == ['gk_2026']


def test_get_targets_rejects_duplicate_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        study_goal_service_module.study_goal_dao,
        'get_targets',
        AsyncMock(return_value=[_row(), _row()]),
    )

    with pytest.raises(errors.RequestError, match='备考目标编码重复'):
        run(study_goal_service.get_targets(db=None))


def test_validate_goal_accepts_applicable_year_and_subjects(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        study_goal_service_module.study_goal_dao,
        'get_targets',
        AsyncMock(return_value=[_row()]),
    )

    target = run(study_goal_service.validate_goal(db=None, goal=StudyGoal(**_goal())))

    assert target.code == 'gk_2026'


@pytest.mark.parametrize('overrides', [{'exam_year': 2025}, {'subjects': ['shenlun']}])
def test_validate_goal_rejects_inapplicable_year_or_subject(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
) -> None:
    monkeypatch.setattr(
        study_goal_service_module.study_goal_dao,
        'get_targets',
        AsyncMock(return_value=[_row()]),
    )

    with pytest.raises(errors.RequestError, match='报考年度或科目不适用于该目标'):
        run(study_goal_service.validate_goal(db=None, goal=StudyGoal(**_goal(**overrides))))


def test_validate_goal_rejects_missing_or_disabled_target(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        study_goal_service_module.study_goal_dao,
        'get_targets',
        AsyncMock(return_value=[]),
    )

    with pytest.raises(errors.RequestError, match='不存在、已停用或编码重复'):
        run(study_goal_service.validate_goal(db=None, goal=StudyGoal(**_goal())))


# ---------------------------------------------------------------------------
# 模板题池/知识体系校验
# ---------------------------------------------------------------------------


def _patch_config_dependencies(monkeypatch: pytest.MonkeyPatch, **bank: Any) -> AsyncMock:
    monkeypatch.setattr(
        study_goal_service_module.knowledge_system_dao,
        'get',
        AsyncMock(return_value=SimpleNamespace(domain_category_id=1)),
    )
    bank_defaults = {'status': 'active', 'visibility': 'public', 'current_revision_id': 11}
    bank_defaults.update(bank)
    monkeypatch.setattr(
        study_goal_service_module.bank_dao,
        'get',
        AsyncMock(return_value=SimpleNamespace(**bank_defaults) if bank_defaults.get('status') else None),
    )
    resolve = AsyncMock(return_value={201})
    monkeypatch.setattr(
        study_goal_service_module.bank_revision_dao,
        'get',
        AsyncMock(return_value=SimpleNamespace(status='published')),
    )
    monkeypatch.setattr(study_goal_service_module.knowledge_service, 'resolve_point_ids', resolve)
    return resolve


def test_validate_config_binds_bank_and_knowledge_system(monkeypatch: pytest.MonkeyPatch) -> None:
    resolve = _patch_config_dependencies(monkeypatch)
    config = ExamTargetConfig(**_config())

    run(study_goal_service.validate_config(db=FakeSession(), config=config))

    resolve.assert_awaited_once()
    assert resolve.await_args.kwargs['point_ids'] == [201]
    assert resolve.await_args.kwargs['system_id'] == 11


def test_validate_config_rejects_missing_knowledge_system(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_config_dependencies(monkeypatch)
    monkeypatch.setattr(
        study_goal_service_module.knowledge_system_dao,
        'get',
        AsyncMock(return_value=None),
    )

    with pytest.raises(errors.RequestError, match='模板知识体系不存在或未启用'):
        run(study_goal_service.validate_config(db=FakeSession(), config=ExamTargetConfig(**_config())))


def test_validate_config_rejects_domain_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_config_dependencies(monkeypatch)

    with pytest.raises(errors.RequestError, match='模板知识体系与备考领域不一致'):
        run(study_goal_service.validate_config(db=FakeSession('pc_cet'), config=ExamTargetConfig(**_config())))


def test_validate_config_rejects_unpublished_bank(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_config_dependencies(monkeypatch, status='draft')

    with pytest.raises(errors.RequestError, match='目标模板必须绑定已发布的公共题库'):
        run(study_goal_service.validate_config(db=FakeSession(), config=ExamTargetConfig(**_config())))


@pytest.mark.parametrize('revision', [None, SimpleNamespace(status='draft')])
def test_validate_config_checks_current_revision(monkeypatch: pytest.MonkeyPatch, revision: Any) -> None:
    _patch_config_dependencies(monkeypatch)
    get_revision = AsyncMock(return_value=revision)
    monkeypatch.setattr(study_goal_service_module.bank_revision_dao, 'get', get_revision)
    with pytest.raises(errors.RequestError, match='当前发布版本不存在或尚未发布'):
        run(study_goal_service.validate_config(db=FakeSession(), config=ExamTargetConfig(**_config())))
    get_revision.assert_awaited_once()
    assert get_revision.await_args.kwargs['bank_id'] == 21


# ---------------------------------------------------------------------------
# 偏好读写：显式 null 清空、省略保持
# ---------------------------------------------------------------------------


def _patch_domain_ids(
    monkeypatch: pytest.MonkeyPatch,
    *,
    category_id: int = 1400,
    point_id: int | None = 1401,
) -> AsyncMock:
    linked = AsyncMock(return_value={'current_category_id': category_id, 'current_knowledge_point_id': point_id})
    monkeypatch.setattr(study_goal_service, 'domain_category_ids', linked)
    return linked


def _capture_preference_update(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    async def fake_update(_db: Any, _pk: int, *, user_id: int, data: dict[str, Any]) -> int:
        await asyncio.sleep(0)
        captured.update(data)
        return 1

    monkeypatch.setattr(preference_service_module.practice_preference_dao, 'update', fake_update)
    return captured


def _packed(goals: list[dict[str, Any]], *, current: dict[str, Any] | None = None) -> dict[str, Any]:
    return {'current': current, 'saved': goals, 'version': 1}


def test_explicit_null_study_goal_clears_current_and_keeps_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    goal = _goal()
    existing = SimpleNamespace(id=1, study_goal=goal)
    updated = SimpleNamespace(id=1, study_goal=_packed([goal]))
    captured: dict[str, Any] = {}
    linked = _patch_domain_ids(monkeypatch)

    async def fake_update(_db: Any, _pk: int, *, user_id: int, data: dict[str, Any]) -> int:
        await asyncio.sleep(0)
        captured.update(data)
        return 1

    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(side_effect=[existing, updated]),
    )
    monkeypatch.setattr(preference_service_module.practice_preference_dao, 'update', fake_update)

    result = run(preference_service.update(db=None, user_id=7, obj=UpdatePracticePreferenceParam(study_goal=None)))

    assert captured['study_goal'] == _packed([StudyGoal(**goal).model_dump(mode='json')])
    assert 'current_category_id' not in captured, '显式清空目标不应改动当前方向'
    assert linked.await_count == 0
    assert result.study_goal is None
    assert result.saved_study_goals == [StudyGoal(**goal)]


def test_omitted_study_goal_keeps_existing_value(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = SimpleNamespace(id=1, study_goal={})
    update = AsyncMock()
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=existing),
    )
    monkeypatch.setattr(preference_service_module.practice_preference_dao, 'update', update)

    run(preference_service.update(db=None, user_id=7, obj=UpdatePracticePreferenceParam()))

    assert update.await_count == 0


def test_valid_study_goal_is_validated_and_linked_to_target_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = SimpleNamespace(id=1, study_goal={})
    updated = SimpleNamespace(id=1, study_goal=_packed([_goal()], current=_goal()))
    captured = _capture_preference_update(monkeypatch)
    validate = AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(domain_code='gongkao')))
    monkeypatch.setattr(study_goal_service, 'validate_goal', validate)
    monkeypatch.setattr(
        study_goal_service,
        'get_target',
        AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(domain_code='gongkao'))),
    )
    linked = _patch_domain_ids(monkeypatch)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(side_effect=[existing, updated]),
    )

    run(
        preference_service.update(
            db=None, user_id=7, obj=UpdatePracticePreferenceParam(study_goal=StudyGoal(**_goal()))
        )
    )

    assert validate.await_count == 1
    assert linked.await_args.kwargs['domain_code'] == 'gongkao'
    goal = StudyGoal(**_goal()).model_dump(mode='json')
    assert captured['study_goal'] == _packed([goal], current=goal)
    assert captured['current_category_id'] == 1400
    assert captured['current_knowledge_point_id'] == 1401


def test_complete_goal_overrides_client_category_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = SimpleNamespace(id=1, study_goal={})
    updated = SimpleNamespace(id=1, study_goal=_packed([_goal()], current=_goal()))
    captured = _capture_preference_update(monkeypatch)
    monkeypatch.setattr(
        study_goal_service,
        'validate_goal',
        AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(domain_code='gongkao'))),
    )
    monkeypatch.setattr(
        study_goal_service,
        'get_target',
        AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(domain_code='gongkao'))),
    )
    _patch_domain_ids(monkeypatch, category_id=1400, point_id=1401)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(side_effect=[existing, updated]),
    )

    run(
        preference_service.update(
            db=None,
            user_id=7,
            obj=UpdatePracticePreferenceParam(
                study_goal=StudyGoal(**_goal()),
                current_category_id=1,
                current_knowledge_point_id=2,
            ),
        )
    )

    goal = StudyGoal(**_goal()).model_dump(mode='json')
    assert captured['study_goal'] == _packed([goal], current=goal)
    assert captured['current_category_id'] == 1400
    assert captured['current_knowledge_point_id'] == 1401


def test_browse_domain_only_sets_direction_and_clears_full_goal(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = SimpleNamespace(id=1, study_goal=_goal())
    updated = SimpleNamespace(id=1, study_goal=_packed([_goal()]))
    captured = _capture_preference_update(monkeypatch)
    linked = _patch_domain_ids(monkeypatch)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(side_effect=[existing, updated]),
    )

    run(preference_service.update(db=None, user_id=7, obj=UpdatePracticePreferenceParam(browse_domain_code='gongkao')))

    assert linked.await_args.kwargs['domain_code'] == 'gongkao'
    goal = StudyGoal(**_goal()).model_dump(mode='json')
    assert captured['study_goal'] == _packed([goal]), '先逛逛只清当前目标，保留已添加列表'
    assert captured['current_category_id'] == 1400
    assert captured['current_knowledge_point_id'] == 1401
    assert 'browse_domain_code' not in captured, 'browse_domain_code 仅请求字段，不落库'


def test_browse_domain_rejects_complete_goal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=None),
    )

    with pytest.raises(errors.RequestError, match='完整备考目标与仅浏览方向不能同时设置'):
        run(
            preference_service.update(
                db=None,
                user_id=7,
                obj=UpdatePracticePreferenceParam(study_goal=StudyGoal(**_goal()), browse_domain_code='gongkao'),
            )
        )


def test_legacy_category_switch_normalizes_ids_when_same_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = SimpleNamespace(id=1, study_goal=_goal())
    updated = SimpleNamespace(id=1, study_goal=_goal())
    captured = _capture_preference_update(monkeypatch)
    monkeypatch.setattr(
        study_goal_service,
        'get_target',
        AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(domain_code='gongkao'))),
    )
    _patch_domain_ids(monkeypatch, category_id=1400, point_id=1401)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(side_effect=[existing, updated]),
    )

    run(
        preference_service.update(
            db=None,
            user_id=7,
            obj=UpdatePracticePreferenceParam(current_category_id=1400, current_knowledge_point_id=99),
        )
    )

    assert captured['current_category_id'] == 1400
    assert captured['current_knowledge_point_id'] == 1401, '旧客户端知识点必须归一到目标领域根节点'


def test_legacy_category_switch_rejects_cross_domain_goal(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = SimpleNamespace(id=1, study_goal=_goal())
    monkeypatch.setattr(
        study_goal_service,
        'get_target',
        AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(domain_code='gongkao'))),
    )
    _patch_domain_ids(monkeypatch, category_id=1400)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=existing),
    )

    with pytest.raises(errors.RequestError, match='请通过切换备考目标更换备考方向'):
        run(
            preference_service.update(
                db=None,
                user_id=7,
                obj=UpdatePracticePreferenceParam(current_category_id=1),
            )
        )


def test_preference_get_links_category_from_current_goal(monkeypatch: pytest.MonkeyPatch) -> None:
    preference = SimpleNamespace(id=1, study_goal=_goal(), current_category_id=1, current_knowledge_point_id=2)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=preference),
    )
    monkeypatch.setattr(
        study_goal_service,
        'get_target',
        AsyncMock(return_value=SimpleNamespace(config=SimpleNamespace(domain_code='gongkao'))),
    )
    _patch_domain_ids(monkeypatch, category_id=1400, point_id=1401)

    result = run(preference_service.get(db=None, user_id=7))

    assert result.current_category_id == 1400
    assert result.current_knowledge_point_id == 1401
    assert result.study_goal == StudyGoal(**_goal())


def test_preference_get_keeps_history_when_target_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    preference = SimpleNamespace(id=1, study_goal=_goal(), current_category_id=1, current_knowledge_point_id=2)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=preference),
    )
    monkeypatch.setattr(
        study_goal_service,
        'get_target',
        AsyncMock(side_effect=errors.RequestError(msg='备考目标不存在、已停用或编码重复，请重新选择')),
    )
    linked = _patch_domain_ids(monkeypatch)

    result = run(preference_service.get(db=None, user_id=7))

    assert result.study_goal == StudyGoal(**_goal())
    assert result.current_category_id == 1, '停用目标读取不崩溃，也不猜测新类别'
    assert result.current_knowledge_point_id == 2
    assert linked.await_count == 0


def test_preference_get_without_goal_does_not_link(monkeypatch: pytest.MonkeyPatch) -> None:
    preference = SimpleNamespace(id=1, study_goal={}, current_category_id=1, current_knowledge_point_id=2)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=preference),
    )
    target = AsyncMock()
    linked = _patch_domain_ids(monkeypatch)
    monkeypatch.setattr(study_goal_service, 'get_target', target)

    result = run(preference_service.get(db=None, user_id=7))

    assert result.study_goal is None
    assert result.current_category_id == 1
    assert target.await_count == 0
    assert linked.await_count == 0


# ---------------------------------------------------------------------------
# 目标组卷：前缀、偏好来源、模板快照、配置版本与幂等
# ---------------------------------------------------------------------------


def _patch_create_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rows: list[SimpleNamespace] | None = None,
    goal: dict[str, Any] | None = None,
    existing: Any = None,
) -> AsyncMock:
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
    return AsyncMock()


def test_create_exam_uses_preference_goal_and_template_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
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
    body = captured['obj']
    assert body.source_type == 'custom'
    assert body.bank_id == 21
    assert body.knowledge_system_id == 11
    assert [quota.model_dump() for quota in body.module_quotas] == [{'knowledge_point_id': 201, 'count': 2}]
    assert body.mode == 'exam'
    assert body.duration_minutes == 30
    assert body.limit == 2
    assert body.shuffle is True
    assert body.title == '2026 国考2026 · 基础卷'
    assert body.session_key == obj.session_key

    context = captured['goal_context']
    assert context['request'] == obj.model_dump(exclude={'session_key'})
    assert context['goal'] == StudyGoal(**_goal()).model_dump(mode='json')
    assert context['target_name'] == '国考2026'
    assert context['template'] == ExamTargetConfig(**_config()).templates[0].model_dump(mode='json')


def test_create_exam_requires_goal_session_prefix() -> None:
    with pytest.raises(errors.RequestError, match='goal_前缀'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj(session_key='session_plain')))


def test_create_exam_requires_existing_preference_goal(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_create_dependencies(monkeypatch, goal={})

    with pytest.raises(errors.RequestError, match='请先设置备考目标'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj()))


@pytest.mark.parametrize(
    'overrides',
    [
        {'exam_target_code': 'other_2026'},
        {'exam_year': 2025},
    ],
)
def test_create_exam_rejects_changed_preference_goal(
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, Any],
) -> None:
    _patch_create_dependencies(monkeypatch)

    with pytest.raises(errors.ConflictError, match='备考目标已变更'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj(**overrides)))


def test_create_exam_rejects_stale_config_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_create_dependencies(monkeypatch)

    with pytest.raises(errors.ConflictError, match='组卷配置已更新'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj(config_revision='b' * 64)))


def test_create_exam_rejects_missing_template(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_create_dependencies(monkeypatch)

    with pytest.raises(errors.RequestError, match='暂无此组卷模板'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj(template_key='missing')))


def test_create_exam_rejects_template_for_unselected_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    config = _config(
        subjects={'xingce': '行测', 'shenlun': '申论'},
        templates=[_template(), _template(key='essay', name='申论卷', subject='shenlun', subject_name='申论')],
    )
    _patch_create_dependencies(monkeypatch, rows=[_row(config)], goal=_goal(subjects=['shenlun']))
    revision = StudyGoalService.parse_target(_row(config)).config_revision

    with pytest.raises(errors.RequestError, match='暂无此组卷模板'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj(config_revision=revision)))


def test_create_exam_retry_reuses_old_snapshot_without_current_goal(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = _obj()
    request = obj.model_dump(exclude={'session_key'})
    existing = SimpleNamespace(source_snapshot={'study_goal': {'request': request}})
    _patch_create_dependencies(monkeypatch, existing=existing)
    preference = AsyncMock()
    monkeypatch.setattr(study_goal_service_module.practice_preference_dao, 'get_by_user_id', preference)
    trace = AsyncMock()
    monkeypatch.setattr(study_goal_service_module.study_goal_dao, 'get_targets', trace)
    detail = SimpleNamespace(session_key=obj.session_key)
    monkeypatch.setattr(practice_service, 'get', AsyncMock(return_value=detail))

    result = run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))

    assert result is detail
    assert preference.await_count == 0
    assert trace.await_count == 0


def test_create_exam_rejects_session_key_reused_by_other_request(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = SimpleNamespace(source_snapshot={'study_goal': {'request': {'exam_target_code': 'other'}}})
    _patch_create_dependencies(monkeypatch, existing=existing)

    with pytest.raises(errors.ConflictError, match='会话标识已被其他请求使用'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=_obj()))


# ---------------------------------------------------------------------------
# 目标会话与普通创建的幂等隔离
# ---------------------------------------------------------------------------


def test_goal_key_cannot_be_created_through_plain_entry() -> None:
    obj = CreatePracticeSessionParam(source_type='custom', knowledge_point_ids=[201], session_key='goal_plain01')

    with pytest.raises(errors.RequestError, match='目标考试请通过目标组卷入口创建'):
        run(PracticeService.create(db=None, user_id=7, obj=obj))


def test_goal_context_is_isolated_from_plain_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PracticeService, '_matches_create_request', staticmethod(lambda **_kwargs: True))
    session = SimpleNamespace(source_snapshot={'study_goal': {'request': {'a': 1}}})
    monkeypatch.setattr(practice_session_dao, 'get_by_key', AsyncMock(return_value=session))
    detail = SimpleNamespace(session_key='goal_key01')
    monkeypatch.setattr(PracticeService, 'get', AsyncMock(return_value=detail))
    obj = CreatePracticeSessionParam(source_type='custom', knowledge_point_ids=[201], session_key='goal_key01')

    with pytest.raises(errors.ConflictError, match='会话标识已被其他目标请求使用'):
        run(
            PracticeService._get_idempotent_session(
                db=None,
                session_key='goal_key01',
                user_id=7,
                obj=obj,
                goal_context={'request': {'a': 2}},
            )
        )

    with pytest.raises(errors.ConflictError, match='会话标识已被其他目标请求使用'):
        run(
            PracticeService._get_idempotent_session(
                db=None,
                session_key='goal_key01',
                user_id=7,
                obj=obj,
                goal_context=None,
            )
        )

    assert (
        run(
            PracticeService._get_idempotent_session(
                db=None,
                session_key='goal_key01',
                user_id=7,
                obj=obj,
                goal_context={'request': {'a': 1}},
            )
        )
        is detail
    )
