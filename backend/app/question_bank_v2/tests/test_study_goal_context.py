"""备考目标上下文：领域分类解析、公开目录裁剪与公开接口鉴权边界。"""

import asyncio
import json

from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

import pytest

from starlette.requests import Request

from backend.app.question_bank_v2.api.v1.study_goal import get_exam_target_catalog
from backend.app.question_bank_v2.api.v1.study_goal import router as study_goal_router
from backend.app.question_bank_v2.schema.study_goal import ExamTargetConfig, GetExamTarget
from backend.app.question_bank_v2.service.study_goal_service import StudyGoalService, study_goal_service
from backend.common.exception import errors
from backend.core.conf import settings
from backend.middleware.jwt_auth_middleware import JwtAuthMiddleware

T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class FakeSession:
    """只模拟 domain_category_ids 使用的 db.execute。"""

    def __init__(self, rows: list[Any]) -> None:
        self.rows = rows
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> FakeResult:
        self.statements.append(statement)
        return FakeResult(self.rows)


def _target(*, template: bool = True) -> GetExamTarget:
    templates = []
    if template:
        templates = [
            {
                'key': 'basic',
                'name': '基础卷',
                'subject': 'xingce',
                'subject_name': '行测',
                'knowledge_system_id': 11,
                'bank_id': 21,
                'total': 1,
                'duration_minutes': 30,
                'modules': [{'knowledge_point_id': 201, 'name': '言语理解', 'count': 1}],
            }
        ]
    config = ExamTargetConfig(
        version='2026.1',
        domain_code='gongkao',
        region_code=None,
        exam_kind='national',
        years=[2026],
        subjects={'xingce': '行测'},
        templates=templates,
    )
    return GetExamTarget(code='gk_2026', name='国考2026', config_revision='r' * 64, config=config)


# ---------------------------------------------------------------------------
# 领域分类解析：按 app_code + 根节点业务 code 查询，不硬编码 ID
# ---------------------------------------------------------------------------


def test_domain_category_ids_reads_root_catalog_and_knowledge_point() -> None:
    db = FakeSession([
        SimpleNamespace(id=9001, type='product_catalog'),
        SimpleNamespace(id=9002, type='knowledge_point'),
    ])

    result = run(StudyGoalService.domain_category_ids(db=db, domain_code='gongkao'))

    assert result == {'current_category_id': 9001, 'current_knowledge_point_id': 9002}, 'ID 必须来自数据库'


def test_domain_category_ids_allows_missing_knowledge_point_root() -> None:
    db = FakeSession([SimpleNamespace(id=9001, type='product_catalog')])

    result = run(StudyGoalService.domain_category_ids(db=db, domain_code='kaoyan'))

    assert result == {'current_category_id': 9001, 'current_knowledge_point_id': None}


def test_domain_category_ids_requires_enabled_product_catalog() -> None:
    db = FakeSession([SimpleNamespace(id=9002, type='knowledge_point')])

    with pytest.raises(errors.RequestError, match='该备考方向尚未配置有效内容目录'):
        run(StudyGoalService.domain_category_ids(db=db, domain_code='gongkao'))


def test_domain_category_ids_query_uses_business_codes_and_root_scope() -> None:
    db = FakeSession([
        SimpleNamespace(id=9001, type='product_catalog'),
        SimpleNamespace(id=9002, type='knowledge_point'),
    ])

    run(StudyGoalService.domain_category_ids(db=db, domain_code='gongkao'))

    sql = str(db.statements[0].compile(compile_kwargs={'literal_binds': True}))
    assert 'sys_category' in sql
    assert "app_code = 'youanshang'" in sql
    assert "'pc_gongkao'" in sql
    assert "'kp_gongkao'" in sql
    assert 'parent_id IS NULL' in sql
    assert 'deleted = 0' in sql


def test_domain_category_ids_does_not_reuse_another_domain() -> None:
    db = FakeSession([
        SimpleNamespace(id=7001, type='product_catalog'),
        SimpleNamespace(id=7002, type='knowledge_point'),
    ])

    result = run(StudyGoalService.domain_category_ids(db=db, domain_code='cet'))

    assert result['current_category_id'] == 7001
    assert result['current_knowledge_point_id'] == 7002


# ---------------------------------------------------------------------------
# 公开目录：不含组卷资源，也不泄露题池/知识体系/模块
# ---------------------------------------------------------------------------


def test_public_catalog_strips_templates_and_keeps_original(monkeypatch: pytest.MonkeyPatch) -> None:
    target = _target()
    monkeypatch.setattr(study_goal_service, 'get_targets', AsyncMock(return_value=[target]))

    response = run(get_exam_target_catalog(db=None))

    catalog_target = response.data[0]
    assert target.config.templates, '目标自身配置不能被修改'
    assert catalog_target.config.templates == []
    assert catalog_target.code == target.code
    assert catalog_target.config_revision == target.config_revision

    payload = json.dumps(catalog_target.model_dump(), ensure_ascii=False)
    for field in ('bank_id', 'knowledge_system_id', 'modules'):
        assert field not in payload


def test_public_catalog_keeps_anonymous_access_and_private_routes_require_login() -> None:
    routes = {route.path: route for route in study_goal_router.routes}

    assert routes['/exam-target-catalog'].dependencies == []
    assert routes['/exam-targets'].dependencies, '完整目标目录仍需登录'
    assert routes['/goal-exams'].dependencies, '目标组卷仍需登录'


def test_jwt_whitelist_only_opens_the_exact_public_catalog_path() -> None:
    prefix = settings.FASTAPI_API_V1_PATH
    catalog_path = f'{prefix}/qbank-v2/exam-target-catalog'
    whitelist = settings.TOKEN_REQUEST_PATH_EXCLUDE

    assert whitelist.count(catalog_path) == 1
    assert f'{prefix}/qbank-v2' not in whitelist
    for private in (
        f'{prefix}/qbank-v2/exam-targets',
        f'{prefix}/qbank-v2/goal-exams',
        f'{prefix}/qbank-v2/preferences',
    ):
        assert private not in whitelist


def _request(path: str, token: str = 'expired-token') -> Request:
    return Request({
        'type': 'http',
        'method': 'GET',
        'path': path,
        'raw_path': path.encode(),
        'query_string': b'',
        'headers': [(b'authorization', f'Bearer {token}'.encode())],
        'scheme': 'http',
        'server': ('testserver', 80),
        'root_path': '',
        'client': ('127.0.0.1', 12345),
    })


def test_middleware_ignores_expired_token_for_public_catalog_only() -> None:
    prefix = settings.FASTAPI_API_V1_PATH
    catalog_path = f'{prefix}/qbank-v2/exam-target-catalog'

    assert JwtAuthMiddleware.extract_token(_request(catalog_path)) is None
    assert JwtAuthMiddleware.extract_token(_request(catalog_path, token='expired-token')) is None

    private_paths = [
        f'{prefix}/qbank-v2/exam-targets',
        f'{prefix}/qbank-v2/goal-exams',
        f'{prefix}/qbank-v2/preferences',
        f'{catalog_path}/',
        f'{catalog_path}-private',
    ]
    for path in private_paths:
        assert JwtAuthMiddleware.extract_token(_request(path)) == 'expired-token', f'{path} 不能放开鉴权'


def test_public_catalog_route_hides_disabled_or_missing_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        study_goal_service,
        'get_targets',
        AsyncMock(side_effect=errors.RequestError(msg='备考目标不存在、已停用或编码重复，请重新选择')),
    )

    with pytest.raises(errors.RequestError, match='不存在、已停用或编码重复'):
        run(get_exam_target_catalog(db=None))
