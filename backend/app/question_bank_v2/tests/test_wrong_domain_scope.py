"""错题本的领域筛选口径测试。

错题本是跨领域的全局账本：列表、计数、分组都必须能按当前领域收窄，
否则切到考公后会看到考研的错题。
"""

import asyncio

from datetime import UTC, datetime
from typing import Any

from backend.app.question_bank_v2.crud.crud_review import wrong_question_state_dao

# 自主录入的领域归属：entry_metadata 里的领域键被取成整数后与领域子树求交集
RECORDED_DOMAIN_SQL = "CAST(qbank_v2_wrong_question_state.entry_metadata['domain_category_id'] AS BIGINT)"


class _EmptyMappings:
    def all(self) -> list[dict[str, Any]]:
        return []

    def one(self) -> dict[str, int]:
        return {
            'total_count': 0,
            'active_count': 0,
            'resolved_count': 0,
            'wrong_occurrence_count': 0,
            'reviewed_count': 0,
            'pending_review_count': 0,
            'due_count': 0,
        }


class _Result:
    def mappings(self) -> _EmptyMappings:
        return _EmptyMappings()

    def scalar_one(self) -> int:
        return 0


class _CapturingSession:
    """记录执行过的语句，用于断言 SQL 是否带上领域条件"""

    def __init__(self) -> None:
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> _Result:
        self.statements.append(statement)
        return _Result()

    def sql(self) -> str:
        return '\n'.join(str(stmt.compile(compile_kwargs={'literal_binds': True})) for stmt in self.statements)


def test_pending_review_select_scopes_domain() -> None:
    """待复盘队列必须同时覆盖题库错题与自主录入的领域归属"""
    stmt = wrong_question_state_dao.get_pending_review_list_select(
        user_id=20,
        entry_scope=None,
        domain_category_ids=[1400, 1365],
    )
    sql = str(stmt.compile(compile_kwargs={'literal_binds': True}))

    # 题库错题：题目的题库命中当前领域分类
    assert 'qbank_v2_bank_category' in sql
    assert 'qbank_v2_bank_category.category_id IN (1400, 1365)' in sql
    assert 'qbank_v2_bank_item.question_id = qbank_v2_wrong_question_state.question_id' in sql
    # 自主录入：按录入时记录的领域
    assert RECORDED_DOMAIN_SQL in sql
    assert 'IN (1400, 1365)' in sql.split(RECORDED_DOMAIN_SQL, 1)[1]


def test_domain_scope_is_absent_without_domain() -> None:
    """拿不到领域时不过滤，保证历史账号仍能看到自己的错题"""
    stmt = wrong_question_state_dao.get_pending_review_list_select(
        user_id=20,
        entry_scope=None,
        domain_category_ids=None,
    )
    sql = str(stmt.compile(compile_kwargs={'literal_binds': True}))

    assert 'qbank_v2_bank_category' not in sql
    assert 'entry_metadata' not in sql


def test_reviewed_and_plain_list_share_the_same_domain_scope() -> None:
    """错题列表与复盘档案必须用同一套领域口径，避免两个入口看到不同范围"""
    list_sql = str(
        wrong_question_state_dao.get_list_select(
            user_id=20,
            status='active',
            entry_source=None,
            domain_category_ids=[1, 8],
        ).compile(compile_kwargs={'literal_binds': True})
    )
    reviewed_sql = str(
        wrong_question_state_dao.get_reviewed_list_select(
            user_id=20,
            mastery_state=None,
            tag_id=None,
            knowledge_point_id=None,
            domain_category_ids=[1, 8],
        ).compile(compile_kwargs={'literal_binds': True})
    )

    for sql in (list_sql, reviewed_sql):
        assert 'qbank_v2_bank_category.category_id IN (1, 8)' in sql
        assert RECORDED_DOMAIN_SQL in sql


def test_statistics_counts_use_the_domain_scope() -> None:
    """看板计数与列表同口径，否则会出现「角标 28、列表 3 条」"""
    db = _CapturingSession()

    statistics = asyncio.run(
        wrong_question_state_dao.get_statistics(
            db,
            user_id=20,
            now=datetime(2026, 10, 13, 12, tzinfo=UTC),
            domain_category_ids=[1400],
        )
    )

    assert statistics['pending_review_count'] == 0
    assert 'qbank_v2_bank_category.category_id IN (1400)' in db.sql()


def test_group_counts_scopes_both_bank_and_external_groups() -> None:
    """按题库分组时，题库错题与自主录入都要按领域收窄"""
    db = _CapturingSession()

    asyncio.run(
        wrong_question_state_dao.get_group_counts(
            db,
            user_id=20,
            group_by='bank',
            knowledge_system_ids=[],
            domain_category_ids=[1400],
        )
    )

    assert len(db.statements) == 2
    sql = db.sql()
    assert sql.count('qbank_v2_bank_category.category_id IN (1400)') == 2
    assert sql.count(RECORDED_DOMAIN_SQL) == 2


def test_dashboard_distributions_use_the_domain_scope() -> None:
    """复盘看板的错因分布/事件数与列表同口径，回到错题状态上取领域归属"""
    db = _CapturingSession()

    event_count, reason_rows, knowledge_rows = asyncio.run(
        wrong_question_state_dao.get_dashboard_rows(
            db,
            user_id=20,
            since=datetime(2026, 9, 13, 12, tzinfo=UTC),
            knowledge_system_ids=[2],
            domain_category_ids=[1400],
        )
    )

    assert (event_count, reason_rows, knowledge_rows) == (0, [], [])
    sql = db.sql()
    # 事件范围、错因分布、知识点分布三条语句都必须限定领域
    assert sql.count('qbank_v2_bank_category.category_id IN (1400)') == 3
    assert sql.count(RECORDED_DOMAIN_SQL) == 3
    assert 'qbank_v2_wrong_question_state.id = qbank_v2_question_review.wrong_state_id' in sql
