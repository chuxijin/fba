#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import importlib

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from pytest import MonkeyPatch
from sqlalchemy.dialects import postgresql
from starlette.testclient import TestClient

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.app.access.schema.catalog import GetSubscriptionCatalog
from backend.app.access.schema.template import GetTemplateListItem, TemplatePackBrief
from backend.database.db import get_db

catalog_module = importlib.import_module('backend.app.access.service.catalog_service')
dao_module = importlib.import_module('backend.app.access.crud.crud_template')


def test_catalog_query_excludes_internal_inactive_and_out_of_sale_templates() -> None:
    """公开目录与管理查询分离，并在数据库中限定销售范围"""
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalars=lambda: SimpleNamespace(all=list),
    )))
    assert asyncio.run(dao_module.subscription_template_dao.get_sale_catalog(db)) == []
    stmt = db.execute.call_args.args[0]
    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert 'membership_tier.is_paid IS false' in sql
    assert 'subscription_template.price_cents >=' in sql
    assert 'subscription_template.sale_period IS NULL' in sql
    assert '@>' in sql
    assert 'subscription_template.price_cents >' in sql
    values = compiled.params.values()
    assert [TemplateKind.STANDARD, TemplateKind.BUNDLE] in values
    assert 'GBS_' in values
    assert sum(value == CommonStatus.ACTIVE for value in values) == 2


def test_catalog_only_exposes_referenced_active_sales_descriptions(monkeypatch: MonkeyPatch) -> None:
    """公开返回不包含订阅、余额、管理元数据或未引用的权益"""
    template = GetTemplateListItem(
        id=1, code='vip-month', name='月卡', kind=TemplateKind.STANDARD,
        tier_code='VIP', tier_name='VIP', tier_weight=10, is_paid_membership=True,
        duration_days=30, auto_renewable=False, price_cents=490, display_order=1,
        cover_image=None, description='刷题会员', sale_period=None,
        status=CommonStatus.ACTIVE, created_time=datetime(2026, 10, 17, tzinfo=UTC),
        pack_codes=['qbank', 'retired'], domain_codes=['gongkao'],
        packs=[TemplatePackBrief(code='qbank', name='刷题包'), TemplatePackBrief(code='retired', name='已归档')],
    )
    get_templates = AsyncMock(return_value=[template])
    build_items = AsyncMock(return_value=[template])
    get_packs = AsyncMock(return_value=[SimpleNamespace(id=2, code='qbank', name='刷题包', description='题库使用')])
    get_items = AsyncMock(return_value=[
        SimpleNamespace(pack_id=2, entitlement_id=3),
        SimpleNamespace(pack_id=2, entitlement_id=4),
    ])
    get_entitlements = AsyncMock(return_value=[SimpleNamespace(
        id=3, code='qbank.access', name='刷题', category='access', description='题库使用',
    )])
    monkeypatch.setattr(catalog_module.subscription_template_dao, 'get_sale_catalog', get_templates)
    monkeypatch.setattr(catalog_module.subscription_template_service, 'build_list_items', build_items)
    monkeypatch.setattr(catalog_module.entitlement_pack_dao, 'select_models', get_packs)
    monkeypatch.setattr(catalog_module.pack_item_dao, 'get_by_packs', get_items)
    monkeypatch.setattr(catalog_module.entitlement_dao, 'select_models', get_entitlements)
    data = asyncio.run(catalog_module.subscription_catalog_service.get_catalog(db=None)).model_dump()
    assert data['templates'][0]['pack_codes'] == ['qbank']
    assert data['packs'][0]['entitlement_codes'] == ['qbank.access']
    assert get_packs.call_args.kwargs['status__eq'] == CommonStatus.ACTIVE
    assert get_entitlements.call_args.kwargs['status__eq'] == CommonStatus.ACTIVE
    assert len(data['entitlements']) == 1
    for private_field in ['metadata', 'created_time', 'updated_time', 'subscriptions', 'balance', 'value_meta']:
        assert private_field not in repr(data)


def test_catalog_is_readable_without_login_and_keeps_the_response_contract(monkeypatch: MonkeyPatch) -> None:
    """游客访问销售资料不依赖鉴权或用户上下文"""
    route_module = importlib.import_module('backend.app.access.api.v1.catalog')
    monkeypatch.setattr(
        route_module.subscription_catalog_service, 'get_catalog',
        AsyncMock(return_value=GetSubscriptionCatalog(templates=[], packs=[], entitlements=[])),
    )
    app = FastAPI()
    app.include_router(route_module.router, prefix='/api/v1/access/catalog')

    def fake_db() -> Iterator[None]:
        yield None

    app.dependency_overrides[get_db] = fake_db
    response = TestClient(app).get('/api/v1/access/catalog')
    assert response.status_code == 200
    assert response.json()['data'] == {'templates': [], 'packs': [], 'entitlements': []}
