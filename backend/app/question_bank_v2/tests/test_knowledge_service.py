import asyncio

from decimal import Decimal
from types import SimpleNamespace

import pytest

from pydantic import ValidationError

from backend.app.question_bank_v2.crud.crud_knowledge import knowledge_system_dao
from backend.app.question_bank_v2.crud.crud_practice import practice_session_item_dao
from backend.app.question_bank_v2.crud.crud_review import review_reference_dao
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank_v2.service.knowledge_service import KnowledgeService


def test_knowledge_tree_uses_deduplicated_descendant_progress() -> None:
    points = [
        SimpleNamespace(
            id=1,
            system_id=10,
            code='root',
            name='根节点',
            parent_id=None,
            path='/1/',
            depth=0,
            sort_order=0,
            description=None,
        ),
        SimpleNamespace(
            id=2,
            system_id=10,
            code='child-a',
            name='子节点 A',
            parent_id=1,
            path='/1/2/',
            depth=1,
            sort_order=0,
            description=None,
        ),
        SimpleNamespace(
            id=3,
            system_id=10,
            code='child-b',
            name='子节点 B',
            parent_id=1,
            path='/1/3/',
            depth=1,
            sort_order=1,
            description=None,
        ),
    ]
    progress = {
        1: {
            'direct_question_count': 1,
            'question_count': 15,
            'answered_count': 6,
            'correct_count': 4,
            'mastered_count': 2,
            'mastery_sum': Decimal('2.7'),
            'mastery_sample_count': 6,
        },
        2: {
            'direct_question_count': 10,
            'question_count': 10,
            'answered_count': 5,
            'correct_count': 4,
            'mastered_count': 2,
            'mastery_sum': Decimal('2.5'),
            'mastery_sample_count': 5,
        },
        3: {'direct_question_count': 4, 'question_count': 4},
    }

    tree = KnowledgeService._build_tree(points=points, progress=progress, root_id=None)

    assert len(tree) == 1
    assert tree[0].direct_question_count == 1
    assert (tree[0].question_count, tree[0].answered_count, tree[0].correct_count) == (15, 6, 4)
    assert tree[0].correct_rate == Decimal('0.6667')
    assert tree[0].mastery_score == Decimal('0.4500')
    assert [item.id for item in tree[0].children] == [2, 3]


def test_practice_filters_are_normalized_and_validate_year_range() -> None:
    obj = CreatePracticeSessionParam(
        bank_id=1,
        knowledge_point_ids=[3, 3, 2],
        question_types=['single_choice', 'single_choice', 'fill_blank'],
        year_start=2022,
        year_end=2026,
    )

    assert obj.knowledge_point_ids == [2, 3]
    assert obj.question_types == ['fill_blank', 'single_choice']
    with pytest.raises(ValidationError, match='起始年份不能大于结束年份'):
        CreatePracticeSessionParam(bank_id=1, year_start=2026, year_end=2022)


def test_candidate_query_uses_indexable_year_type_and_knowledge_filters() -> None:
    class EmptyResult:
        def scalars(self) -> 'EmptyResult':
            return self

        def all(self) -> list[object]:
            return []

    class CapturingSession:
        statement: object | None = None

        async def execute(self, statement: object) -> EmptyResult:
            self.statement = statement
            return EmptyResult()

    db = CapturingSession()
    asyncio.run(
        practice_session_item_dao.get_candidates(
            db,
            bank_revision_id=11,
            section_id=12,
            knowledge_point_ids=[21, 22],
            question_types=['single_choice'],
            year_start=2022,
            year_end=2026,
            shuffle=False,
            limit=20,
        )
    )
    sql = str(db.statement.compile(compile_kwargs={'literal_binds': True}))

    assert 'qbank_v2_bank_item.exam_year >= 2022' in sql
    assert 'qbank_v2_bank_item.exam_year <= 2026' in sql
    assert 'qbank_v2_question.question_type IN' in sql
    assert 'qbank_v2_question_knowledge_point.knowledge_point_id IN' in sql


class _EmptyResult:
    def scalars(self) -> '_EmptyResult':
        return self

    def all(self) -> list[object]:
        return []

    def first(self) -> None:
        return None


class _CapturingSession:
    statement: object | None = None

    async def execute(self, statement: object) -> _EmptyResult:
        self.statement = statement
        return _EmptyResult()


def _compile(statement: object) -> str:
    return str(statement.compile(compile_kwargs={'literal_binds': True}))


def test_default_system_lookup_targets_version_default() -> None:
    """默认体系解析必须限定领域，且只命中 active 且 version=default 的系统"""
    db = _CapturingSession()
    asyncio.run(knowledge_system_dao.get_default_system_id(db, domain_category_id=1400, code='xingce'))
    sql = _compile(db.statement)

    assert "qbank_v2_knowledge_system.version = 'default'" in sql
    assert "qbank_v2_knowledge_system.status = 'active'" in sql
    assert "qbank_v2_knowledge_system.deleted = 0" in sql
    # 领域与科目必须进入 WHERE，否则多领域下会随机命中别的领域的 default
    assert 'qbank_v2_knowledge_system.domain_category_id = 1400' in sql
    assert "qbank_v2_knowledge_system.code = 'xingce'" in sql


def test_default_system_lookup_without_code_still_scopes_domain() -> None:
    """不指定科目时仍必须限定领域"""
    db = _CapturingSession()
    asyncio.run(knowledge_system_dao.get_default_system_id(db, domain_category_id=1))
    sql = _compile(db.statement)

    assert 'qbank_v2_knowledge_system.domain_category_id = 1' in sql
    assert 'qbank_v2_knowledge_system.code' not in sql.split('WHERE', 1)[1]


def test_valid_knowledge_points_are_scoped_to_default_system() -> None:
    """复盘可选知识点必须限定在默认体系内，杜绝跨体系混用"""
    db = _CapturingSession()
    asyncio.run(
        review_reference_dao.get_valid_knowledge_point_ids(
            db,
            knowledge_point_ids=[21, 22],
            knowledge_system_id=2,
        )
    )
    sql = _compile(db.statement)

    assert 'qbank_v2_knowledge_point.system_id = 2' in sql
    assert 'qbank_v2_knowledge_point.id IN (21, 22)' in sql
