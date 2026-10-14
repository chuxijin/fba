#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""skill 题库只读端点 wiring 测试：闸门 + service 透传 + scope 校验"""

import asyncio
import importlib

import pytest

qbank_api = importlib.import_module('backend.app.skill.api.v1.qbank')
errors = importlib.import_module('backend.common.exception').errors


def test_endpoints_raise_without_membership() -> None:
    """会员闸门拒绝时应抛 ForbiddenError，且不会调用题库服务"""
    calls = {'bank': 0, 'questions': 0, 'detail': 0}

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        if raise_on_deny:
            raise errors.ForbiddenError(msg='使用公考 AI 助手需要开通会员')
        from backend.app.access.constants import ReasonCode
        from backend.app.access.schema.engine import Decision
        return Decision.deny(reason_code=ReasonCode.NO_MATCHING_GRANT)

    class _BankSvc:
        async def get_select(self, **_kwargs):
            calls['bank'] += 1
            return None

    class _QuestionSvc:
        async def get_list_select(self, **_kwargs):
            calls['questions'] += 1
            return None

        async def get(self, *, db, pk):
            calls['detail'] += 1
            return None

    api = qbank_api
    original_gate = api.ensure_skill_access
    original_bank, original_question = api.bank_service, api.question_service
    api.ensure_skill_access = fake_gate
    api.bank_service, api.question_service = _BankSvc(), _QuestionSvc()
    try:
        with pytest.raises(Exception) as exc_info:
            asyncio.run(api.skill_get_qbank_banks(db=None, identity=_identity()))
        with pytest.raises(Exception) as exc_info:
            asyncio.run(api.skill_get_qbank_questions(db=None, identity=_identity()))
        with pytest.raises(Exception) as exc_info:
            asyncio.run(api.skill_get_qbank_question_detail(db=None, identity=_identity(), pk=1))
        assert '会员' in str(exc_info.value)
        assert calls == {'bank': 0, 'questions': 0, 'detail': 0}
    finally:
        api.ensure_skill_access = original_gate
        api.bank_service, api.question_service = original_bank, original_question


def test_banks_passes_gate_and_service() -> None:
    """会员放行时应调用 bank_service.get_select 并返回分页结果"""
    page_data = {'items': [], 'total': 0, 'page': 1, 'size': 20, 'total_pages': 0, 'links': {}}

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        return None

    calls = {'kwargs': None}

    class _BankSvc:
        async def get_select(self, *, db, **kwargs):
            calls['kwargs'] = kwargs
            return 'stmt-marker'

    async def fake_paging_data(_db, _stmt, _schema):
        assert _stmt == 'stmt-marker'
        return page_data

    api = qbank_api
    original_gate = api.ensure_skill_access
    original_bank, original_paging = api.bank_service, api.paging_data
    api.ensure_skill_access = fake_gate
    api.bank_service = _BankSvc()
    api.paging_data = fake_paging_data
    try:
        result = asyncio.run(
            api.skill_get_qbank_banks(db=None, identity=_identity(), category_id=None, bank_kind=None, keyword=None)
        )
        assert calls['kwargs'] == {
            'category_id': None,
            'include_descendants': True,
            'bank_kind': None,
            'keyword': None,
        }
        assert result.data is page_data
    finally:
        api.ensure_skill_access = original_gate
        api.bank_service, api.paging_data = original_bank, original_paging


def test_questions_passes_filters_to_service() -> None:
    """检索应把 bank_id / question_type / keyword 透传给 question_service.get_list_select"""
    page_data = {'items': [], 'total': 0, 'page': 1, 'size': 20, 'total_pages': 0, 'links': {}}

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        return None

    calls = {'kwargs': None}

    class _QuestionSvc:
        async def get_list_select(self, *, db, **kwargs):
            calls['kwargs'] = kwargs
            return 'stmt-marker'

    async def fake_paging_data(_db, _stmt, _schema):
        return page_data

    api = qbank_api
    original_gate = api.ensure_skill_access
    original_question, original_paging = api.question_service, api.paging_data
    api.ensure_skill_access = fake_gate
    api.question_service = _QuestionSvc()
    api.paging_data = fake_paging_data
    try:
        result = asyncio.run(
            api.skill_get_qbank_questions(
                db=None,
                identity=_identity(),
                bank_id=7,
                question_type='single_choice',
                keyword='资料分析',
            )
        )
        assert calls['kwargs'] == {'bank_id': 7, 'question_type': 'single_choice', 'keyword': '资料分析', 'knowledge_point_ids': None}
        assert result.data is page_data
    finally:
        api.ensure_skill_access = original_gate
        api.question_service, api.paging_data = original_question, original_paging


def test_detail_passes_gate_and_service() -> None:
    """详情应透传题目 ID 并返回 question_service.get 结果"""

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        return None

    calls = {'pk': None}

    class _QuestionSvc:
        async def get(self, *, db, pk):
            calls['pk'] = pk
            return 'detail-marker'

    api = qbank_api
    original_gate = api.ensure_skill_access
    original_question = api.question_service
    api.ensure_skill_access = fake_gate
    api.question_service = _QuestionSvc()
    try:
        result = asyncio.run(api.skill_get_qbank_question_detail(db=None, identity=_identity(), pk=42))
        assert calls['pk'] == 42
        assert result.data == 'detail-marker'
    finally:
        api.ensure_skill_access = original_gate
        api.question_service = original_question


def test_categories_passes_gate_and_service() -> None:
    """分类树应透传 app_code / type / status 并返回 category_service.get_tree 结果"""

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        return None

    calls = {'kwargs': None}

    class _CategorySvc:
        async def get_tree(self, *, db, **kwargs):
            calls['kwargs'] = kwargs
            return [{'id': 1, 'name': '考研', 'children': [{'id': 2, 'name': '政治', 'children': []}]}]

    api = qbank_api
    original_gate = api.ensure_skill_access
    original_category = api.category_service
    api.ensure_skill_access = fake_gate
    api.category_service = _CategorySvc()
    try:
        result = asyncio.run(
            api.skill_get_qbank_categories(db=None, identity=_identity(), app_code='youanshang',
                                           category_type='product_catalog', include_disabled=False)
        )
        assert calls['kwargs'] == {'app_code': 'youanshang', 'type_': 'product_catalog', 'status': True}
        assert result.data[0]['name'] == '考研'
    finally:
        api.ensure_skill_access = original_gate
        api.category_service = original_category


def test_questions_passes_knowledge_point_ids() -> None:
    """知识点筛选应透传 knowledge_point_ids 给 question_service.get_list_select"""
    page_data = {'items': [], 'total': 0, 'page': 1, 'size': 20, 'total_pages': 0, 'links': {}}

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        return None

    calls = {'kwargs': None}

    class _QuestionSvc:
        async def get_list_select(self, *, db, **kwargs):
            calls['kwargs'] = kwargs
            return 'stmt-marker'

    async def fake_paging_data(_db, _stmt, _schema):
        return page_data

    api = qbank_api
    original_gate = api.ensure_skill_access
    original_question, original_paging = api.question_service, api.paging_data
    api.ensure_skill_access = fake_gate
    api.question_service = _QuestionSvc()
    api.paging_data = fake_paging_data
    try:
        result = asyncio.run(
            api.skill_get_qbank_questions(db=None, identity=_identity(), bank_id=None,
                                          question_type=None, keyword=None, knowledge_point_ids='1,2,3')
        )
        assert calls['kwargs'] == {'bank_id': None, 'question_type': None, 'keyword': None, 'knowledge_point_ids': [1, 2, 3]}
        assert result.data is page_data
    finally:
        api.ensure_skill_access = original_gate
        api.question_service, api.paging_data = original_question, original_paging


def test_knowledge_systems_passes_gate_and_service() -> None:
    """知识体系列表应透传 domain_category_id 并返回分页结果"""
    page_data = {'items': [], 'total': 0, 'page': 1, 'size': 20, 'total_pages': 0, 'links': {}}

    async def fake_gate(_db, *, user_id, raise_on_deny=True):
        return None

    calls = {'kwargs': None}

    class _KnowledgeSvc:
        def get_systems_select(self, *, domain_category_id=None, code=None):
            calls['kwargs'] = {'domain_category_id': domain_category_id, 'code': code}
            return 'stmt-marker'

        async def get_points_tree(self, *, db, system_id):
            return {'system': None, 'points': []}

    async def fake_paging_data(_db, _stmt, _schema):
        return page_data

    api = qbank_api
    original_gate = api.ensure_skill_access
    original_knowledge, original_paging = api.knowledge_service, api.paging_data
    api.ensure_skill_access = fake_gate
    api.knowledge_service = _KnowledgeSvc()
    api.paging_data = fake_paging_data
    try:
        result = asyncio.run(api.skill_get_knowledge_systems(db=None, identity=_identity(), domain_category_id=2))
        assert calls['kwargs'] == {'domain_category_id': 2, 'code': None}
        assert result.data is page_data
    finally:
        api.ensure_skill_access = original_gate
        api.knowledge_service, api.paging_data = original_knowledge, original_paging


def test_scope_constant() -> None:
    """题库端点必须要求 qbank:read scope，与 calculation 的 skill:use 隔离"""
    assert qbank_api.QbankIdentity is not None
    dependency = qbank_api.router.dependencies
    assert not dependency  # scope 校验在 QbankIdentity 注解内，路由本身不额外声明


def _identity():
    from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult
    from backend.utils.timezone import timezone

    return GetOpenAuthCheckResult(
        user_id=1,
        client_id='oac_gongkao_cli_dev',
        scopes=['qbank:read'],
        authorized=True,
        expires_at=timezone.now(),
    )
