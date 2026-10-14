"""公开题目检索的查询口径与路由契约测试。

小程序搜索框要能按「题干 / 选项 / 解析」找题，但只能看到公开已发布题库里的题，
并且不能顺带把标准答案吐出来；领域范围按分类子树收窄，默认落在用户当前领域内。
"""

import asyncio
import re

from collections.abc import Coroutine
from typing import Any, TypeVar

import pytest

from fastapi import FastAPI
from pytest import MonkeyPatch
from sqlalchemy.dialects import postgresql

from backend.app.question_bank_v2.api.router import v1 as question_bank_v2_router
from backend.app.question_bank_v2.api.v1.question_search import search_questions
from backend.app.question_bank_v2.crud.crud_question import question_dao
from backend.app.question_bank_v2.schema.question import GetQuestionSearchItem
from backend.app.question_bank_v2.service.catalog_service import catalog_service
from backend.app.question_bank_v2.service.question_service import question_service
from backend.common.exception import errors

T = TypeVar('T')

SEARCH_PATH = '/api/v1/qbank-v2/questions/search'
QUESTION_DETAIL_PATH = '/api/v1/qbank-v2/questions/{pk}'


def run(coro: Coroutine[Any, Any, T]) -> T:
    """同步执行协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


def compile_sql(stmt: Any) -> str:
    """按 PostgreSQL 方言编译查询，ILIKE / DISTINCT ON 只在 PG 方言下才成立"""
    return str(stmt.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))


def test_public_search_only_covers_public_published_banks() -> None:
    """草稿、下架题库和非公开题库的题目都不能被搜出来"""
    sql = compile_sql(question_dao.get_public_search_select(keyword='行政执法'))

    assert 'qbank_v2_bank.visibility' in sql
    assert "qbank_v2_bank.visibility = 'public'" in sql
    assert "qbank_v2_bank.status = 'active'" in sql
    assert "qbank_v2_bank_revision.status = 'published'" in sql
    assert "qbank_v2_question.visibility = 'public'" in sql
    assert "qbank_v2_question.status = 'active'" in sql
    # 同一道题挂在多份试卷里时只保留一条来源上下文，避免分页出现重复题
    assert 'DISTINCT ON (qbank_v2_bank_item.question_id)' in sql


def test_public_search_matches_stem_options_and_explanation() -> None:
    """命中口径覆盖题干、有序选项与已发布解析三处"""
    sql = compile_sql(question_dao.get_public_search_select(keyword='行政执法'))

    assert 'qbank_v2_question.stem ILIKE' in sql
    assert 'CAST(qbank_v2_question.option_data AS TEXT) ILIKE' in sql
    assert 'EXISTS (SELECT qbank_v2_question_explanation.id' in sql
    assert 'qbank_v2_question_explanation.content ILIKE' in sql
    assert "qbank_v2_question_explanation.status = 'published'" in sql
    # 关键词按整串子串匹配，不做隐式分词（literal_binds 会把 % 转义成 %%）
    assert re.search(r"ILIKE '%+行政执法%+'", sql)


def test_public_search_never_returns_standard_answer() -> None:
    """检索是公开接口，不能顺带查答案表，否则等于开放批量对答案入口"""
    sql = compile_sql(question_dao.get_public_search_select(keyword='行政执法'))

    assert 'qbank_v2_question_answer' not in sql
    assert 'answer_data' not in sql
    assert 'answer' not in GetQuestionSearchItem.model_fields


def test_public_search_prioritises_stem_hits() -> None:
    """题干命中排在仅选项或解析命中的前面"""
    sql = compile_sql(question_dao.get_public_search_select(keyword='行政执法'))
    # 子查询里也有 ORDER BY（来源去重），取最后一段才是外层排序
    order_by = sql.rsplit('ORDER BY', 1)[-1]

    assert 'CASE WHEN (qbank_v2_question.stem ILIKE' in order_by
    assert 'THEN 0 ELSE 1 END' in order_by


def test_public_search_ands_multiple_keywords() -> None:
    """空格分隔的多个关键词是「与」关系，与题库名检索口径保持一致"""
    sql = compile_sql(question_dao.get_public_search_select(keyword='行政执法 2024'))

    assert re.search(r"ILIKE '%+行政执法%+'", sql)
    assert re.search(r"ILIKE '%+2024%+'", sql)
    assert ' AND ' in sql
    # 排序里同样要求全部关键词都落在题干上，才算「题干命中」
    order_by = sql.rsplit('ORDER BY', 1)[-1]
    assert order_by.count('qbank_v2_question.stem ILIKE') == 2


def test_public_search_scopes_domain_by_category_subtree() -> None:
    """传领域时按分类子树收窄；不传时不做领域限制但仍只搜公开题库"""
    scoped_sql = compile_sql(
        question_dao.get_public_search_select(keyword='行测', domain_category_ids=[1400, 1365])
    )
    assert 'qbank_v2_bank_category.category_id IN (1400, 1365)' in scoped_sql

    unscoped_sql = compile_sql(question_dao.get_public_search_select(keyword='行测'))
    assert 'qbank_v2_bank_category' not in unscoped_sql


def test_service_expands_domain_category_to_subtree(monkeypatch: MonkeyPatch) -> None:
    """服务层负责把领域根分类展开成子树，DAO 只接收最终 ID 列表"""
    captured: dict[str, Any] = {}

    async def fake_resolve(*, db: Any, cat_id: int) -> set[int]:
        await asyncio.sleep(0)
        captured['cat_id'] = cat_id
        return {1400, 31, 34}

    monkeypatch.setattr(catalog_service, 'resolve_category_subtree_ids', fake_resolve)

    sql = compile_sql(
        run(question_service.get_public_search_select(db=None, keyword='行测', domain_category_id=1400))
    )

    assert captured['cat_id'] == 1400
    matched = re.search(r'qbank_v2_bank_category\.category_id IN \(([^)]*)\)', sql)
    assert matched is not None
    assert set(matched.group(1).split(', ')) == {'1400', '31', '34'}


def test_service_skips_category_lookup_without_domain(monkeypatch: MonkeyPatch) -> None:
    """没有领域时不查分类表，避免游客搜索多一次无意义的库查询"""

    async def fail_resolve(*, db: Any, cat_id: int) -> set[int]:
        await asyncio.sleep(0)
        raise AssertionError('未传领域时不应解析分类子树')

    monkeypatch.setattr(catalog_service, 'resolve_category_subtree_ids', fail_resolve)

    sql = compile_sql(run(question_service.get_public_search_select(db=None, keyword='行测')))
    assert 'qbank_v2_bank_category' not in sql


def test_search_endpoint_is_public_and_registered_before_question_detail() -> None:
    """检索必须挂在无鉴权路由上，且排在 /questions/{pk} 之前，否则会被当成题目详情"""
    app = FastAPI()
    app.include_router(question_bank_v2_router)
    paths = app.openapi()['paths']
    keys = list(paths)

    assert SEARCH_PATH in keys
    assert keys.index(SEARCH_PATH) < keys.index(QUESTION_DETAIL_PATH)
    # 公开接口不能带 Authorization scheme；同为公开的合集目录也没有
    assert 'security' not in paths[SEARCH_PATH]['get']
    assert 'security' not in paths['/api/v1/qbank-v2/collections/catalog']['get']
    # 对照：题目管理列表仍然要求鉴权，说明上面的断言判断的是真差异
    assert 'security' in paths['/api/v1/qbank-v2/questions']['get']


@pytest.mark.parametrize('keyword', ['   ', '\t', '\n'])
def test_blank_keyword_is_rejected(keyword: str) -> None:
    """空白关键词会让 ILIKE '%%' 命中全库，必须在入口拦掉"""
    with pytest.raises(errors.RequestError):
        run(search_questions(db=None, keyword=keyword, domain_category_id=None))
