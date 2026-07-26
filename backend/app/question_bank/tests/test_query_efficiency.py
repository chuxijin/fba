import asyncio

from collections.abc import Coroutine
from types import SimpleNamespace
from typing import Any, TypeVar
from unittest.mock import AsyncMock

from sqlalchemy.dialects import postgresql
from starlette.routing import Match

from backend.app.question_bank.model.practice import SessionQuestion
from backend.app.question_bank.model.question import Question
from backend.app.question_bank.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank.schema.question import QuestionCollectParam
from backend.app.question_bank.service.knowledge_point_service import KnowledgePointService
from backend.app.question_bank.service.question_selector_service import QuestionSelectorService
from backend.app.question_bank.service.session_service import SessionService
from backend.middleware.access_middleware import resolve_request_path_template

T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """Run an async unit under the project's synchronous test setup."""
    return asyncio.run(coro)


class ScalarResult:
    def __init__(self, rows: list[int]) -> None:
        self.rows = rows

    def scalars(self) -> 'ScalarResult':
        return self

    def all(self) -> list[int]:
        return self.rows


class MatchingRoute:
    path = '/api/v1/question-bank/sessions/{session_key}'

    def matches(self, _scope: dict[str, Any]) -> tuple[Match, dict[str, Any]]:
        return Match.FULL, {}


def test_placement_selection_deduplicates_and_limits_in_sql() -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult([101, 102])))
    params = QuestionCollectParam(
        source_type='placement',
        content_status=10,
        is_active=True,
        limit=2,
    )

    result = run(
        QuestionSelectorService._select_placement_question_ids(
            db=db,
            params=params,
            kp_ids=[],
            kp_names=[],
            cat_ids=None,
            chapter_scope_ids=None,
            apply_limit=False,
        )
    )

    stmt = db.execute.await_args.args[0]
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert result == [101, 102]
    assert 'row_number() OVER (PARTITION BY study_question_placement.question_id' in sql
    assert 'LIMIT 2' in sql


def test_single_bank_selection_uses_direct_limited_query() -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=ScalarResult([101, 102])))
    params = QuestionCollectParam(source_type='placement', bank_id=3, is_active=True, limit=2)

    result = run(
        QuestionSelectorService._select_placement_question_ids(
            db=db,
            params=params,
            kp_ids=[],
            kp_names=[],
            cat_ids=None,
            chapter_scope_ids=None,
            apply_limit=False,
        )
    )

    stmt = db.execute.await_args.args[0]
    sql = str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
    assert result == [101, 102]
    assert 'row_number()' not in sql
    assert 'LIMIT 2' in sql


def test_session_collect_limit_is_pushed_down_only_for_ordered_selection() -> None:
    ordered = CreatePracticeSessionParam(session_type='bank', bank_id=3, limit=20, shuffle=False)
    shuffled = CreatePracticeSessionParam(session_type='bank', bank_id=3, limit=20, shuffle=True)

    assert SessionService._build_collect_param(obj=ordered, source_type='placement').limit == 20
    assert SessionService._build_collect_param(obj=shuffled, source_type='placement').limit is None


def test_knowledge_point_tree_aggregates_with_preindexed_children() -> None:
    children = [
        SimpleNamespace(id=2, parent_id=1, name='父节点', code='parent', sort_order=1),
        SimpleNamespace(id=3, parent_id=2, name='叶子 B', code='leaf-b', sort_order=2),
        SimpleNamespace(id=4, parent_id=2, name='叶子 A', code='leaf-a', sort_order=1),
    ]

    tree = KnowledgePointService._build_kp_tree(children, {'leaf-a': 3, 'leaf-b': 5}, 1)

    assert len(tree) == 1
    assert tree[0].question_count == 8
    assert [node.name for node in tree[0].children] == ['叶子 A', '叶子 B']


def test_metrics_path_uses_route_template() -> None:
    request = SimpleNamespace(
        scope={'path': '/api/v1/question-bank/sessions/abc123'},
        app=SimpleNamespace(routes=[MatchingRoute()]),
        url=SimpleNamespace(path='/api/v1/question-bank/sessions/abc123'),
    )

    assert resolve_request_path_template(request) == '/api/v1/question-bank/sessions/{session_key}'


def test_unmatched_metrics_path_uses_fixed_label() -> None:
    request = SimpleNamespace(
        scope={'path': '/api/v1/random/attacker-value'},
        app=SimpleNamespace(routes=[]),
        url=SimpleNamespace(path='/api/v1/random/attacker-value'),
    )

    assert resolve_request_path_template(request) == '__unmatched__'


def test_query_indexes_are_registered_in_model_metadata() -> None:
    question_indexes = {index.name for index in Question.__table__.indexes}
    session_question_indexes = {index.name for index in SessionQuestion.__table__.indexes}

    assert 'idx_question_knowledge_point_gin' in question_indexes
    assert 'idx_session_question_valid_answer_time' in session_question_indexes
