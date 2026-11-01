"""字典扩展配置：备考目标编码稳定性、通用字典隔离与旧客户端兼容回归。"""

import asyncio

from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest

from backend.app.question_bank_v2.schema.study_goal import EXAM_TARGET_DICT_CODE
from backend.app.question_bank_v2.service.study_goal_service import study_goal_service
from backend.common.enums import StatusType
from backend.common.exception import errors
from backend.plugin.dict.crud.crud_dict_data import dict_data_dao
from backend.plugin.dict.schema.dict_data import CreateDictDataParam, UpdateDictDataParam
from backend.plugin.dict.service.dict_data_service import DictDataService

T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """同步执行协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


def _config() -> dict[str, Any]:
    return {
        'version': '2026.1',
        'domain_code': 'gongkao',
        'region_code': None,
        'exam_kind': 'national',
        'years': [2026],
        'subjects': {'xingce': '行测'},
        'templates': [
            {
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
        ],
    }


def _param(
    *,
    value: str = 'gk_2026',
    label: str = '国考2026',
    extra: dict[str, Any] | None = None,
    status: StatusType = StatusType.enable,
) -> CreateDictDataParam:
    return CreateDictDataParam(
        type_id=1,
        label=label,
        value=value,
        sort=0,
        status=status,
        extra=_config() if extra is None else extra,
    )


def test_general_dict_skips_exam_target_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    duplicate = AsyncMock()
    validate = AsyncMock()
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', duplicate)
    monkeypatch.setattr(study_goal_service, 'validate_config', validate)

    run(DictDataService._validate_exam_target(db=None, obj=_param(extra={'anything': True}), code='practice_mode'))

    assert duplicate.await_count == 0
    assert validate.await_count == 0


def test_exam_target_rejects_duplicate_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dict_data_dao,
        'get_by_value_and_type_code',
        AsyncMock(return_value=[SimpleNamespace(id=2)]),
    )

    with pytest.raises(errors.ConflictError, match='备考目标编码已存在'):
        run(
            DictDataService._validate_exam_target(
                db=None,
                obj=_param(),
                code=EXAM_TARGET_DICT_CODE,
                existing=SimpleNamespace(id=1),
            )
        )


def test_exam_target_allows_same_record_and_validates_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        dict_data_dao,
        'get_by_value_and_type_code',
        AsyncMock(return_value=[SimpleNamespace(id=1)]),
    )
    validate = AsyncMock()
    monkeypatch.setattr(study_goal_service, 'validate_config', validate)

    run(
        DictDataService._validate_exam_target(
            db=None,
            obj=_param(),
            code=EXAM_TARGET_DICT_CODE,
            existing=SimpleNamespace(id=1, value='gk_2026'),
        )
    )

    validate.assert_awaited_once()
    assert validate.await_args.kwargs['config'].years == [2026]


def test_exam_target_code_is_immutable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', AsyncMock(return_value=[]))

    with pytest.raises(errors.RequestError, match='不可修改'):
        run(
            DictDataService._validate_exam_target(
                db=None,
                obj=_param(value='gk_2027'),
                code=EXAM_TARGET_DICT_CODE,
                existing=SimpleNamespace(id=1, value='gk_2026'),
            )
        )


def test_exam_target_rejects_invalid_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', AsyncMock(return_value=[]))

    with pytest.raises(errors.RequestError, match='扩展配置不合法'):
        run(
            DictDataService._validate_exam_target(
                db=None,
                obj=_param(extra={'version': '2026.1'}),
                code=EXAM_TARGET_DICT_CODE,
            )
        )


def test_disabled_exam_target_with_empty_extra_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', AsyncMock(return_value=[]))
    validate = AsyncMock()
    monkeypatch.setattr(study_goal_service, 'validate_config', validate)

    run(
        DictDataService._validate_exam_target(
            db=None,
            obj=_param(extra={}, status=StatusType.disable),
            code=EXAM_TARGET_DICT_CODE,
        )
    )

    assert validate.await_count == 0


def test_disabled_exam_target_with_config_still_validates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', AsyncMock(return_value=[]))

    with pytest.raises(errors.RequestError, match='扩展配置不合法'):
        run(
            DictDataService._validate_exam_target(
                db=None,
                obj=_param(extra={'version': '2026.1'}, status=StatusType.disable),
                code=EXAM_TARGET_DICT_CODE,
            )
        )


def test_crud_update_keeps_extra_when_old_client_omits_it(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_update(_db: Any, data: dict[str, Any], **_kwargs: Any) -> int:
        await asyncio.sleep(0)
        captured.update(data)
        return 1

    monkeypatch.setattr(dict_data_dao, 'update_model_by_column', fake_update)
    obj = UpdateDictDataParam(type_id=1, label='国考2026', value='gk_2026', sort=0, status=StatusType.enable)
    assert 'extra' not in obj.model_fields_set

    run(dict_data_dao.update(db=None, pk=5, obj=obj, type_code='other_dict'))

    assert 'extra' not in captured
    assert captured['type_code'] == 'other_dict'


def test_crud_update_writes_extra_when_explicitly_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_update(_db: Any, data: dict[str, Any], **_kwargs: Any) -> int:
        await asyncio.sleep(0)
        captured.update(data)
        return 1

    monkeypatch.setattr(dict_data_dao, 'update_model_by_column', fake_update)
    obj = UpdateDictDataParam(
        type_id=1,
        label='国考2026',
        value='gk_2026',
        sort=0,
        status=StatusType.enable,
        extra={'key': 'v'},
    )
    assert 'extra' in obj.model_fields_set

    run(dict_data_dao.update(db=None, pk=5, obj=obj, type_code=EXAM_TARGET_DICT_CODE))

    assert captured['extra'] == {'key': 'v'}


def test_exam_target_rejects_invalid_code(monkeypatch: pytest.MonkeyPatch) -> None:
    duplicates = AsyncMock()
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', duplicates)

    with pytest.raises(errors.RequestError, match='备考目标编码只允许小写字母、数字和下划线'):
        run(
            DictDataService._validate_exam_target(
                db=None,
                obj=_param(value='Bad-Code'),
                code=EXAM_TARGET_DICT_CODE,
            )
        )

    assert duplicates.await_count == 0


def test_existing_exam_target_cannot_move_to_other_type(monkeypatch: pytest.MonkeyPatch) -> None:
    duplicates = AsyncMock()
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', duplicates)

    with pytest.raises(errors.RequestError, match='备考目标不可改为其他字典类型'):
        run(
            DictDataService._validate_exam_target(
                db=None,
                obj=_param(),
                code='practice_mode',
                existing=SimpleNamespace(id=1, type_code=EXAM_TARGET_DICT_CODE, value='gk_2026', extra=_config()),
            )
        )

    assert duplicates.await_count == 0


def test_enabled_exam_target_with_empty_extra_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', AsyncMock(return_value=[]))

    with pytest.raises(errors.RequestError, match='扩展配置不合法'):
        run(
            DictDataService._validate_exam_target(
                db=None,
                obj=_param(extra={}, status=StatusType.enable),
                code=EXAM_TARGET_DICT_CODE,
            )
        )


def test_disabled_exam_target_with_valid_extra_skips_offline_bank_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', AsyncMock(return_value=[]))
    validate = AsyncMock(side_effect=errors.RequestError(msg='目标模板必须绑定已发布的公共题库'))
    monkeypatch.setattr(study_goal_service, 'validate_config', validate)

    run(
        DictDataService._validate_exam_target(
            db=None,
            obj=_param(extra=_config(), status=StatusType.disable),
            code=EXAM_TARGET_DICT_CODE,
        )
    )

    assert validate.await_count == 0


def test_pg_advisory_lock_is_acquired_before_duplicate_check(monkeypatch: pytest.MonkeyPatch) -> None:
    order: list[tuple[str, str]] = []

    class FakeDialect:
        name = 'postgresql'

    class FakeBind:
        dialect = FakeDialect()

    class FakeSession:
        def get_bind(self) -> Any:
            return FakeBind()

        async def execute(self, statement: Any) -> None:
            order.append(('lock', str(statement)))

    async def fake_duplicates(_db: Any, value: str, _code: str) -> list[Any]:
        await asyncio.sleep(0)
        order.append(('duplicate', value))
        return []

    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', fake_duplicates)
    monkeypatch.setattr(study_goal_service, 'validate_config', AsyncMock())

    run(DictDataService._validate_exam_target(db=FakeSession(), obj=_param(), code=EXAM_TARGET_DICT_CODE))

    assert [item[0] for item in order] == ['lock', 'duplicate']
    assert 'pg_advisory_xact_lock' in order[0][1]
    assert order[1][1] == 'gk_2026'


def test_none_db_skips_lock_and_still_checks_duplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    duplicates = AsyncMock(return_value=[])
    monkeypatch.setattr(dict_data_dao, 'get_by_value_and_type_code', duplicates)
    monkeypatch.setattr(study_goal_service, 'validate_config', AsyncMock())

    run(DictDataService._validate_exam_target(db=None, obj=_param(), code=EXAM_TARGET_DICT_CODE))

    duplicates.assert_awaited_once()
