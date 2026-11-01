"""备考目标状态兼容：旧扁平/新版本化 JSON、列表整理、指纹与当前目标语义。"""

import asyncio
import hashlib
import importlib
import json

from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.schema.preference import GetPracticePreferenceDetail, UpdatePracticePreferenceParam
from backend.app.question_bank_v2.schema.study_goal import CreateGoalExamParam, StudyGoal
from backend.app.question_bank_v2.schema.study_goal_state import (
    current_study_goal,
    pack_study_goals,
    saved_study_goals,
    study_goal_key,
    study_goals_revision,
)
from backend.app.question_bank_v2.service.knowledge_service import knowledge_service
from backend.app.question_bank_v2.service.preference_service import preference_service
from backend.app.question_bank_v2.service.study_goal_service import study_goal_service
from backend.common.exception import errors

preference_service_module = importlib.import_module('backend.app.question_bank_v2.service.preference_service')
study_goal_service_module = importlib.import_module('backend.app.question_bank_v2.service.study_goal_service')
T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.new_event_loop().run_until_complete(coro)


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


def _dump(**overrides: Any) -> dict[str, Any]:
    return StudyGoal(**_goal(**overrides)).model_dump(mode='json')


def _packed(goals: list[dict[str, Any]], *, current: dict[str, Any] | None = None) -> dict[str, Any]:
    return {'current': current, 'saved': goals, 'version': 1}


def _target(domain_code: str = 'gongkao') -> SimpleNamespace:
    return SimpleNamespace(config=SimpleNamespace(domain_code=domain_code))


def _patch_read(monkeypatch: pytest.MonkeyPatch, raw: Any, *, disabled: bool = False) -> AsyncMock:
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=None if raw is None else SimpleNamespace(id=1, study_goal=raw, current_category_id=1)),
    )
    if disabled:
        monkeypatch.setattr(
            study_goal_service, 'get_target', AsyncMock(side_effect=errors.RequestError(msg='目标停用'))
        )
    else:
        monkeypatch.setattr(study_goal_service, 'get_target', AsyncMock(return_value=_target()))
    linked = AsyncMock(return_value={'current_category_id': 1400, 'current_knowledge_point_id': 1401})
    monkeypatch.setattr(study_goal_service, 'domain_category_ids', linked)
    return linked


def _patch_update(
    monkeypatch: pytest.MonkeyPatch,
    raw: Any,
    *,
    updated_raw: Any = None,
    disabled: bool = False,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    async def fake_update(_db: Any, _pk: int, *, user_id: int, data: dict[str, Any]) -> int:
        await asyncio.sleep(0)
        captured.update(data)
        return 1

    updated = SimpleNamespace(id=1, study_goal=updated_raw if updated_raw is not None else raw)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(side_effect=[SimpleNamespace(id=1, study_goal=raw), updated]),
    )
    monkeypatch.setattr(preference_service_module.practice_preference_dao, 'update', fake_update)
    monkeypatch.setattr(study_goal_service, 'validate_goal', AsyncMock(return_value=_target()))
    if disabled:
        monkeypatch.setattr(
            study_goal_service, 'get_target', AsyncMock(side_effect=errors.RequestError(msg='目标停用'))
        )
    else:
        monkeypatch.setattr(study_goal_service, 'get_target', AsyncMock(return_value=_target()))
    monkeypatch.setattr(
        study_goal_service,
        'domain_category_ids',
        AsyncMock(return_value={'current_category_id': 1400, 'current_knowledge_point_id': 1401}),
    )
    return captured


# ---------------------------------------------------------------------------
# 旧扁平 JSON / 新版本化 JSON / 空状态兼容
# ---------------------------------------------------------------------------


def test_current_helper_reads_legacy_flat_and_versioned_payloads() -> None:
    assert current_study_goal(None) is None
    assert current_study_goal({}) is None
    assert current_study_goal(_goal()) == _goal()
    assert current_study_goal(StudyGoal(**_goal())) == _goal()
    assert current_study_goal(_packed([_dump()], current=_goal())) == _goal()
    assert current_study_goal(_packed([_dump()])) is None


def test_saved_helper_reads_legacy_flat_as_single_goal_and_versioned_list() -> None:
    assert saved_study_goals(None) == []
    assert saved_study_goals({}) == []
    assert saved_study_goals(_goal()) == [StudyGoal(**_goal())]
    assert saved_study_goals(_packed([_dump(), _dump(exam_year=2027)])) == [
        StudyGoal(**_goal()),
        StudyGoal(**_goal(exam_year=2027)),
    ]
    assert saved_study_goals(_packed([], current=_goal())) == []


def test_pack_keeps_empty_contract_and_writes_version_for_any_state() -> None:
    assert pack_study_goals(None, []) == {}
    assert pack_study_goals(_goal(), []) == {'current': _goal(), 'saved': [], 'version': 1}
    assert pack_study_goals(None, [StudyGoal(**_goal())]) == _packed([_dump()])


def test_goal_key_is_target_year_category() -> None:
    assert study_goal_key(StudyGoal(**_goal())) == ('gk_2026', 2026, 'bingtuan')
    assert study_goal_key(StudyGoal(**_goal(category_code=None))) == ('gk_2026', 2026, None)
    assert study_goal_key(StudyGoal(**_goal(exam_year=2027))) != study_goal_key(StudyGoal(**_goal()))


def test_empty_state_returns_none_study_goal_and_stable_fingerprint(monkeypatch: pytest.MonkeyPatch) -> None:
    empty_fingerprint = hashlib.sha256(b'{}').hexdigest()

    assert GetPracticePreferenceDetail().study_goal is None
    assert GetPracticePreferenceDetail().saved_study_goals == []
    assert GetPracticePreferenceDetail().study_goals_revision == empty_fingerprint

    linked = _patch_read(monkeypatch, None)
    result = run(preference_service.get(db=None, user_id=7))

    assert result.study_goal is None
    assert result.saved_study_goals == []
    assert result.study_goals_revision == empty_fingerprint
    assert linked.await_count == 0


def test_get_reads_legacy_flat_goal_and_exposes_saved_list(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_read(monkeypatch, _goal())

    result = run(preference_service.get(db=None, user_id=7))

    assert result.study_goal == StudyGoal(**_goal())
    assert result.saved_study_goals == [StudyGoal(**_goal())]
    assert result.study_goals_revision == study_goals_revision(_goal())


def test_get_reads_versioned_state_with_current_and_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump(), _dump(exam_year=2027)], current=_dump())
    _patch_read(monkeypatch, raw)

    result = run(preference_service.get(db=None, user_id=7))

    assert result.study_goal == StudyGoal(**_goal())
    assert result.saved_study_goals == [StudyGoal(**_goal()), StudyGoal(**_goal(exam_year=2027))]
    assert result.study_goals_revision == study_goals_revision(raw)


# ---------------------------------------------------------------------------
# 保存：自动 upsert 与上限
# ---------------------------------------------------------------------------


def test_saving_same_key_updates_saved_item_in_place(monkeypatch: pytest.MonkeyPatch) -> None:
    second = _dump(exam_year=2027)
    raw = _packed([_dump(), second], current=_dump())
    updated = _packed([_dump(subjects=['xingce', 'shenlun']), second], current=_dump(subjects=['xingce', 'shenlun']))
    captured = _patch_update(monkeypatch, raw, updated_raw=updated)

    run(
        preference_service.update(
            db=None,
            user_id=7,
            obj=UpdatePracticePreferenceParam(study_goal=StudyGoal(**_goal(subjects=['xingce', 'shenlun']))),
        )
    )

    assert captured['study_goal'] == updated


def test_saving_new_key_appends_to_saved_list(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump()], current=_dump())
    captured = _patch_update(monkeypatch, raw)

    run(
        preference_service.update(
            db=None,
            user_id=7,
            obj=UpdatePracticePreferenceParam(study_goal=StudyGoal(**_goal(exam_year=2027))),
        )
    )

    assert captured['study_goal'] == _packed([_dump(), _dump(exam_year=2027)], current=_dump(exam_year=2027))


def test_saving_goal_beyond_twenty_goal_limit_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = [_dump(exam_year=year) for year in range(2001, 2021)]
    raw = _packed(existing, current=existing[0])
    _patch_update(monkeypatch, raw)

    with pytest.raises(errors.RequestError, match='最多保存20个备考目标'):
        run(
            preference_service.update(
                db=None,
                user_id=7,
                obj=UpdatePracticePreferenceParam(study_goal=StudyGoal(**_goal(exam_year=2021))),
            )
        )


def test_clearing_current_goal_keeps_all_saved_goals(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump(), _dump(exam_year=2027)], current=_dump())
    captured = _patch_update(monkeypatch, raw, updated_raw=_packed([_dump(), _dump(exam_year=2027)]))

    run(preference_service.update(db=None, user_id=7, obj=UpdatePracticePreferenceParam(study_goal=None)))

    assert captured['study_goal'] == _packed([_dump(), _dump(exam_year=2027)])
    assert 'current_category_id' not in captured, '清当前目标不能改写浏览领域'


# ---------------------------------------------------------------------------
# 列表整理：删除、排序、只读原内容
# ---------------------------------------------------------------------------


def test_deleting_current_goal_clears_current_but_keeps_domain(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = _dump(), _dump(exam_year=2027)
    raw = _packed([first, second], current=first)
    captured = _patch_update(monkeypatch, raw, updated_raw=_packed([second]))

    run(
        preference_service.update(
            db=None,
            user_id=7,
            obj=UpdatePracticePreferenceParam(
                saved_study_goals=[StudyGoal(**second)],
                study_goals_revision=study_goals_revision(raw),
            ),
        )
    )

    assert captured['study_goal'] == _packed([second])
    assert 'current_category_id' not in captured, '删除当前目标不应清空当前领域'
    assert 'current_knowledge_point_id' not in captured


def test_deleting_non_current_goal_keeps_current(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second, third = _dump(), _dump(exam_year=2027), _dump(exam_year=2028)
    raw = _packed([first, second, third], current=first)
    captured = _patch_update(monkeypatch, raw, updated_raw=_packed([first, third], current=first))

    run(
        preference_service.update(
            db=None,
            user_id=7,
            obj=UpdatePracticePreferenceParam(
                saved_study_goals=[StudyGoal(**first), StudyGoal(**third)],
                study_goals_revision=study_goals_revision(raw),
            ),
        )
    )

    assert captured['study_goal'] == _packed([first, third], current=first)


def test_reordering_saved_goals_preserves_requested_order(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second, third = _dump(), _dump(exam_year=2027), _dump(exam_year=2028)
    raw = _packed([first, second, third], current=first)
    reordered = [third, first, second]
    captured = _patch_update(monkeypatch, raw, updated_raw=_packed(reordered, current=first))

    run(
        preference_service.update(
            db=None,
            user_id=7,
            obj=UpdatePracticePreferenceParam(
                saved_study_goals=[StudyGoal(**item) for item in reordered],
                study_goals_revision=study_goals_revision(raw),
            ),
        )
    )

    assert captured['study_goal'] == _packed(reordered, current=first)


def test_tidy_requires_original_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump()], current=_dump())
    _patch_update(monkeypatch, raw)

    with pytest.raises(errors.RequestError, match='整理目标列表前请先刷新'):
        run(
            preference_service.update(
                db=None,
                user_id=7,
                obj=UpdatePracticePreferenceParam(saved_study_goals=[StudyGoal(**_goal())]),
            )
        )


def test_tidy_rejects_stale_revision(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump()], current=_dump())
    _patch_update(monkeypatch, raw)

    with pytest.raises(errors.ConflictError, match='备考目标列表已变更'):
        run(
            preference_service.update(
                db=None,
                user_id=7,
                obj=UpdatePracticePreferenceParam(
                    saved_study_goals=[StudyGoal(**_goal())],
                    study_goals_revision='0' * 64,
                ),
            )
        )


def test_tidy_rejects_new_goal_not_in_original_list(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump()], current=_dump())
    _patch_update(monkeypatch, raw)

    with pytest.raises(errors.RequestError, match='请通过添加或修改目标更新目标内容'):
        run(
            preference_service.update(
                db=None,
                user_id=7,
                obj=UpdatePracticePreferenceParam(
                    saved_study_goals=[StudyGoal(**_goal()), StudyGoal(**_goal(exam_year=2027))],
                    study_goals_revision=study_goals_revision(raw),
                ),
            )
        )


def test_tidy_rejects_modified_goal_content(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump()], current=_dump())
    _patch_update(monkeypatch, raw)

    with pytest.raises(errors.RequestError, match='请通过添加或修改目标更新目标内容'):
        run(
            preference_service.update(
                db=None,
                user_id=7,
                obj=UpdatePracticePreferenceParam(
                    saved_study_goals=[StudyGoal(**_goal(subjects=['shenlun']))],
                    study_goals_revision=study_goals_revision(raw),
                ),
            )
        )


def test_tidy_rejects_duplicate_target_year_category(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump()], current=_dump())
    _patch_update(monkeypatch, raw)

    with pytest.raises(errors.RequestError, match='相同年度和类别的备考目标不能重复添加'):
        run(
            preference_service.update(
                db=None,
                user_id=7,
                obj=UpdatePracticePreferenceParam(
                    saved_study_goals=[StudyGoal(**_goal()), StudyGoal(**_goal())],
                    study_goals_revision=study_goals_revision(raw),
                ),
            )
        )


# ---------------------------------------------------------------------------
# 指纹：基于原 JSON 的 sha256，列表顺序可感知
# ---------------------------------------------------------------------------


def test_revision_is_sha256_of_canonical_original_json() -> None:
    raw = _packed([_dump(), _dump(exam_year=2027)], current=_dump())
    expected = hashlib.sha256(
        json.dumps(raw, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    ).hexdigest()

    assert study_goals_revision(raw) == expected
    assert study_goals_revision(None) == study_goals_revision({}) == hashlib.sha256(b'{}').hexdigest()


def test_revision_changes_when_saved_order_changes() -> None:
    first, second = _dump(), _dump(exam_year=2027)

    assert study_goals_revision(_packed([first, second])) != study_goals_revision(_packed([second, first]))


# ---------------------------------------------------------------------------
# 当前目标语义：停用目标、知识体系解析与组卷
# ---------------------------------------------------------------------------


def test_disabled_target_still_reads_current_and_saved(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump(), _dump(exam_year=2027)], current=_dump())
    linked = _patch_read(monkeypatch, raw, disabled=True)

    result = run(preference_service.get(db=None, user_id=7))

    assert result.study_goal == StudyGoal(**_goal())
    assert result.saved_study_goals == [StudyGoal(**_goal()), StudyGoal(**_goal(exam_year=2027))]
    assert result.current_category_id == 1, '停用目标不猜测新领域'
    assert linked.await_count == 0


def test_disabled_target_list_still_can_be_tidied(monkeypatch: pytest.MonkeyPatch) -> None:
    first, second = _dump(), _dump(exam_year=2027)
    raw = _packed([first, second], current=first)
    captured = _patch_update(monkeypatch, raw, updated_raw=_packed([second]), disabled=True)

    run(
        preference_service.update(
            db=None,
            user_id=7,
            obj=UpdatePracticePreferenceParam(
                saved_study_goals=[StudyGoal(**second)],
                study_goals_revision=study_goals_revision(raw),
            ),
        )
    )

    assert captured['study_goal'] == _packed([second])


def test_knowledge_domain_ignores_saved_goals_without_current(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump()], current=None)
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=SimpleNamespace(id=1, study_goal=raw, current_category_id=555)),
    )
    target = AsyncMock(return_value=_target())
    monkeypatch.setattr(study_goal_service, 'get_target', target)
    linked = AsyncMock(return_value={'current_category_id': 1400})
    monkeypatch.setattr(study_goal_service, 'domain_category_ids', linked)

    resolved = run(knowledge_service.resolve_optional_domain_category_id(db=None, user_id=7))

    assert resolved == 555
    assert target.await_count == 0
    assert linked.await_count == 0


def test_knowledge_domain_resolves_from_current_goal_only(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _packed([_dump(exam_year=2027), _dump()], current=_dump())
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=SimpleNamespace(id=1, study_goal=raw, current_category_id=555)),
    )
    monkeypatch.setattr(study_goal_service, 'get_target', AsyncMock(return_value=_target()))
    linked = AsyncMock(return_value={'current_category_id': 1400})
    monkeypatch.setattr(study_goal_service, 'domain_category_ids', linked)

    resolved = run(knowledge_service.resolve_optional_domain_category_id(db=None, user_id=7))

    assert resolved == 1400
    assert linked.await_args.kwargs['domain_code'] == 'gongkao'


def test_create_exam_rejects_saved_list_without_current_goal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=SimpleNamespace(study_goal=_packed([_dump()], current=None))),
    )
    monkeypatch.setattr(study_goal_service_module.practice_session_dao, 'get_by_key', AsyncMock(return_value=None))
    obj = CreateGoalExamParam(
        exam_target_code='gk_2026',
        exam_year=2026,
        category_code='bingtuan',
        template_key='basic',
        config_revision='a' * 64,
        session_key='goal_nocurrent01',
    )

    with pytest.raises(errors.RequestError, match='请先设置备考目标'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))


def test_legacy_goal_without_category_is_readable_but_cannot_start_exam(monkeypatch: pytest.MonkeyPatch) -> None:
    legacy = _goal()
    legacy.pop('category_code')
    _patch_read(monkeypatch, legacy)

    result = run(preference_service.get(db=None, user_id=7))

    assert result.study_goal == StudyGoal(**legacy)
    assert result.saved_study_goals == [StudyGoal(**legacy)]

    monkeypatch.setattr(
        preference_service_module.practice_preference_dao,
        'get_by_user_id',
        AsyncMock(return_value=SimpleNamespace(study_goal=legacy)),
    )
    monkeypatch.setattr(study_goal_service_module.practice_session_dao, 'get_by_key', AsyncMock(return_value=None))
    config = {
        'version': '2026.1',
        'domain_code': 'gongkao',
        'region_code': None,
        'exam_kind': 'national',
        'years': [2026],
        'subjects': {'xingce': '行测'},
        'categories': [{'code': 'bingtuan', 'name': '兵团', 'children': []}],
        'templates': [],
    }
    monkeypatch.setattr(
        study_goal_service_module.study_goal_dao,
        'get_targets',
        AsyncMock(return_value=[SimpleNamespace(value='gk_2026', label='国考2026', extra=config)]),
    )
    obj = CreateGoalExamParam(
        exam_target_code='gk_2026',
        exam_year=2026,
        category_code=None,
        template_key='basic',
        config_revision='a' * 64,
        session_key='goal_legacy01',
    )

    with pytest.raises(errors.RequestError, match='旧目标需要补选类别'):
        run(study_goal_service.create_exam(db=None, user_id=7, obj=obj))
