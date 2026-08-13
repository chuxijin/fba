#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import importlib

from datetime import datetime
from types import SimpleNamespace

from sqlalchemy.dialects.postgresql.ranges import Range


my_service_module = importlib.import_module('backend.app.access.service.my_service')
crud_quota_grant_module = importlib.import_module('backend.app.access.crud.crud_quota_grant')
ledger_module = importlib.import_module('backend.app.access.engine.ledger')
subscription_service_module = importlib.import_module('backend.app.access.service.subscription_service')


def test_my_access_service_load_quota_balances_uses_scope_key(monkeypatch) -> None:
    """权益汇总应按资源档案解析的 scope_key 聚合额度包余额"""
    captured: dict[str, object] = {}

    async def fake_get_balances(_db, *, user_id, entitlement_codes, scope_key, ts):
        captured['user_id'] = user_id
        captured['entitlement_codes'] = list(entitlement_codes)
        captured['scope_key'] = scope_key
        captured['ts'] = ts
        return {'render_book.export.quota': 19}

    async def fake_get_quota_scope_keys_from_rules(*_args, **_kwargs) -> dict[str, str]:
        return {'render_book.export.quota': 'render_book'}

    monkeypatch.setattr(
        crud_quota_grant_module.quota_grant_dao,
        'get_balances',
        fake_get_balances,
    )
    monkeypatch.setattr(
        my_service_module.MyAccessService,
        '_get_quota_scope_keys_from_rules',
        fake_get_quota_scope_keys_from_rules,
    )

    now = datetime(2026, 7, 7, 21, 30, 0)
    balances = asyncio.run(
        my_service_module.MyAccessService._load_quota_balances(
            None,
            user_id=20,
            now=now,
            pack_items=[],
            quota_codes=['render_book.export.quota'],
        )
    )

    assert balances['render_book.export.quota'] == 19
    assert captured['user_id'] == 20
    assert captured['scope_key'] == 'render_book'
    assert captured['entitlement_codes'] == ['render_book.export.quota']
    assert captured['ts'] == now


def test_load_quota_balances_falls_back_to_pack_limit(monkeypatch) -> None:
    """尚未生成额度包时应回退展示权益包配置的名义额度"""

    async def fake_get_balances(*_args, **_kwargs) -> dict[str, int]:
        return {}

    async def fake_get_quota_scope_keys_from_rules(*_args, **_kwargs) -> dict[str, str]:
        return {}

    monkeypatch.setattr(crud_quota_grant_module.quota_grant_dao, 'get_balances', fake_get_balances)
    monkeypatch.setattr(
        my_service_module.MyAccessService,
        '_get_quota_scope_keys_from_rules',
        fake_get_quota_scope_keys_from_rules,
    )

    balances = asyncio.run(
        my_service_module.MyAccessService._load_quota_balances(
            None,
            user_id=20,
            now=datetime(2026, 7, 7, 21, 30, 0),
            pack_items=[{'entitlement_code': 'agent.grade.quota', 'value_int': 30, 'value_meta': {}}],
            quota_codes=['agent.grade.quota'],
        )
    )

    assert balances['agent.grade.quota'] == 30


class _FakeGrant:
    """额度包替身"""

    def __init__(self, grant_id: int, remaining: int) -> None:
        self.id = grant_id
        self.granted_amount = remaining
        self.remaining_amount = remaining


class _FakeDB:
    """只记录写入的会话替身"""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, entry) -> None:
        self.added.append(entry)

    async def flush(self) -> None:
        return None


def test_try_consume_drains_expiring_grant_first(monkeypatch) -> None:
    """扣减应跨包消耗, 先扣即将失效的包, 并失效我的权益汇总缓存"""
    # list_consumable 已按 expires_at 升序返回: 1 号包月底过期, 2 号包永不过期
    grants = [_FakeGrant(1, 2), _FakeGrant(2, 5)]
    captured: dict[str, object] = {}

    async def fake_ensure_cycle_grant(*_args, **_kwargs) -> None:
        return None

    async def fake_get_by_idempotency_key(*_args, **_kwargs):
        return None

    async def fake_list_consumable(*_args, **_kwargs):
        return grants

    async def fake_invalidate(user_id: int) -> None:
        captured['user_id'] = user_id

    monkeypatch.setattr(
        ledger_module.LedgerService,
        '_ensure_cycle_grant',
        staticmethod(fake_ensure_cycle_grant),
    )
    monkeypatch.setattr(
        ledger_module.quota_ledger_dao,
        'get_by_idempotency_key',
        fake_get_by_idempotency_key,
    )
    monkeypatch.setattr(ledger_module.quota_grant_dao, 'list_consumable', fake_list_consumable)
    monkeypatch.setattr(my_service_module.my_summary_cache, 'invalidate', fake_invalidate)

    entry = asyncio.run(
        ledger_module.ledger_service.try_consume(
            _FakeDB(),
            user_id=20,
            entitlement_code='agent.grade.quota',
            amount=3,
            cycle_type='monthly',
            scope_key='global',
            source='metered',
            source_ref='job:1',
            idempotency_key='job:1',
        )
    )

    assert entry is not None
    # 先扣光 1 号包的 2 次, 再从 2 号包扣 1 次
    assert grants[0].remaining_amount == 0
    assert grants[1].remaining_amount == 4
    assert entry.grant_breakdown == [{'grant_id': 1, 'amount': 2}, {'grant_id': 2, 'amount': 1}]
    assert entry.balance_after == 4
    assert captured['user_id'] == 20


def test_try_consume_returns_none_when_total_insufficient(monkeypatch) -> None:
    """所有额度包合计不足时不扣减并返回 None"""
    grants = [_FakeGrant(1, 1)]

    async def fake_ensure_cycle_grant(*_args, **_kwargs) -> None:
        return None

    async def fake_get_by_idempotency_key(*_args, **_kwargs):
        return None

    async def fake_list_consumable(*_args, **_kwargs):
        return grants

    monkeypatch.setattr(
        ledger_module.LedgerService,
        '_ensure_cycle_grant',
        staticmethod(fake_ensure_cycle_grant),
    )
    monkeypatch.setattr(
        ledger_module.quota_ledger_dao,
        'get_by_idempotency_key',
        fake_get_by_idempotency_key,
    )
    monkeypatch.setattr(ledger_module.quota_grant_dao, 'list_consumable', fake_list_consumable)

    entry = asyncio.run(
        ledger_module.ledger_service.try_consume(
            _FakeDB(),
            user_id=20,
            entitlement_code='agent.grade.quota',
            amount=3,
            cycle_type='monthly',
            source='metered',
        )
    )

    assert entry is None
    assert grants[0].remaining_amount == 1


def _build_subscription(
    *,
    subscription_id: int,
    tier_code: str,
    tier_name: str,
    tier_weight: int,
    is_paid: bool,
    domain_codes: list[str],
):
    valid_from = datetime(2026, 8, 1, 0, 0, 0)
    return my_service_module.GetMySubscription(
        id=subscription_id,
        template_code=f'template.{tier_code.lower()}',
        template_name=f'{tier_name}年卡',
        tier_code=tier_code,
        tier_name=tier_name,
        tier_weight=tier_weight,
        is_paid_membership=is_paid,
        pack_code=f'pack.{tier_code.lower()}',
        pack_codes=[f'pack.{tier_code.lower()}'],
        domain_codes=domain_codes,
        valid_period=my_service_module.TimePeriodOutput(valid_from=valid_from, valid_to=None),
        valid_from=valid_from,
        valid_to=None,
        status='active',
        created_time=valid_from,
    )


def test_build_subscription_items_from_rows_keeps_tier_and_pack_data() -> None:
    """订阅聚合结果应完整保留档位、权益包和领域信息"""
    valid_from = datetime(2026, 8, 1, 0, 0, 0)
    period = Range(valid_from, None, bounds='[)')
    common = {
        'subscription_id': 10,
        'template_id': 20,
        'valid_period': period,
        'status': 'active',
        'created_time': valid_from,
        'template_code': 'template.svip',
        'template_name': 'SVIP年卡',
        'cover_image': None,
        'template_metadata': {'domain_codes': ['general']},
        'tier_code': 'SVIP',
        'tier_name': 'SVIP会员',
        'tier_weight': 200,
        'tier_is_paid': True,
        'tier_badge_color': '#7C3AED',
    }
    rows = [
        SimpleNamespace(**common, pack_id=1, pack_code='pack.general', domain_code=None),
        SimpleNamespace(**common, pack_id=2, pack_code='pack.kaoyan', domain_code='kaoyan'),
    ]

    subscriptions = my_service_module.MyAccessService._build_subscription_items_from_rows(rows)

    assert len(subscriptions) == 1
    subscription = subscriptions[0]
    assert subscription.tier_code == 'SVIP'
    assert subscription.tier_weight == 200
    assert subscription.is_paid_membership is True
    assert subscription.pack_codes == ['pack.general', 'pack.kaoyan']
    assert subscription.domain_codes == ['general', 'kaoyan']
    assert subscription.valid_to is None


def test_build_membership_profile_separates_free_and_paid_membership() -> None:
    """免费订阅只发权益，付费档位才形成会员身份"""
    free = _build_subscription(
        subscription_id=1,
        tier_code='FREE',
        tier_name='普通用户',
        tier_weight=0,
        is_paid=False,
        domain_codes=['general'],
    )
    free_profile = my_service_module.MyAccessService._build_membership_profile([free])
    assert free_profile.is_member is False
    assert free_profile.is_vip is False
    assert free_profile.tier_code == 'FREE'

    svip = _build_subscription(
        subscription_id=2,
        tier_code='SVIP',
        tier_name='SVIP会员',
        tier_weight=200,
        is_paid=True,
        domain_codes=['general', 'kaoyan'],
    )
    paid_profile = my_service_module.MyAccessService._build_membership_profile([svip, free])
    assert paid_profile.is_member is True
    assert paid_profile.is_vip is True
    assert paid_profile.is_svip is True
    assert paid_profile.tier_code == 'SVIP'


def test_build_domain_memberships_uses_highest_tier_per_domain() -> None:
    """同一领域存在多个订阅时应展示权重最高的会员档位"""
    vip = _build_subscription(
        subscription_id=1,
        tier_code='VIP',
        tier_name='VIP会员',
        tier_weight=100,
        is_paid=True,
        domain_codes=['kaoyan', 'cet'],
    )
    svip = _build_subscription(
        subscription_id=2,
        tier_code='SVIP',
        tier_name='SVIP会员',
        tier_weight=200,
        is_paid=True,
        domain_codes=['kaoyan'],
    )

    memberships = my_service_module.MyAccessService._build_domain_memberships([vip, svip])
    membership_map = {item.domain_code: item for item in memberships}

    assert membership_map['kaoyan'].tier_code == 'SVIP'
    assert membership_map['cet'].tier_code == 'VIP'


def test_has_active_subscription_only_checks_paid_membership(monkeypatch) -> None:
    """CMS 会员人群判断应委托付费会员查询，而不是任意免费订阅"""
    captured: dict[str, object] = {}

    async def fake_has_active_paid_membership(_db, *, user_id, ts):
        captured['user_id'] = user_id
        captured['ts'] = ts
        return False

    monkeypatch.setattr(
        subscription_service_module.subscription_dao,
        'has_active_paid_membership',
        fake_has_active_paid_membership,
    )

    result = asyncio.run(
        subscription_service_module.SubscriptionService.has_active_subscription(None, user_id=88)
    )

    assert result is False
    assert captured['user_id'] == 88
    assert isinstance(captured['ts'], datetime)
