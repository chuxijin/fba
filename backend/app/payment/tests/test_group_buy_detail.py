import asyncio

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.payment.schema.group_buy import GroupBuySummary
from backend.app.payment.service.group_buy_service import group_buy_service
from backend.utils.timezone import timezone


@pytest.mark.parametrize('user_id', [7, 8, None])
def test_team_detail_exposes_payment_deadline_only_to_order_owner(
    monkeypatch: pytest.MonkeyPatch, user_id: int | None
) -> None:
    now = timezone.now()
    reservation = (now + timedelta(minutes=5)).isoformat()
    team = SimpleNamespace(
        id=1,
        activity_id=1,
        share_code='abcdef0123456789abcdef01',
        leader_user_id=7,
        status='forming',
        people=3,
        deadline=now + timedelta(hours=1),
        draft_until=now,
        snapshot={
            'name': '拼团活动',
            'price_cents': 1200,
            'original_price_cents': 3000,
            'base': {'name': '测试套餐'},
            'channels': ['virtual', 'hupijiao'],
            'rewards': {'member_rewards': [{'name': '奖励套餐', 'duration_days': 7}], 'leader_rewards': []},
        },
    )
    member = SimpleNamespace(user_id=7, order_id=17, status='reserved')
    order = SimpleNamespace(
        order_no='GROUP_ORDER_7',
        status='pending',
        fulfill_status='pending',
        pay_type='hupijiao',
        extra_data={'group_buy_reserved_until': reservation, 'openid': 'private-payment-identity'},
    )
    db = SimpleNamespace(get=AsyncMock(return_value=order))
    monkeypatch.setattr(
        'backend.app.payment.service.group_buy_service.group_buy_dao.team', AsyncMock(return_value=team)
    )
    monkeypatch.setattr(
        'backend.app.payment.service.group_buy_service.group_buy_dao.members', AsyncMock(return_value=[member])
    )
    monkeypatch.setattr(
        'backend.app.payment.service.group_buy_service.group_buy_dao.avatars',
        AsyncMock(return_value={7: 'https://cdn/7.png'}),
    )
    monkeypatch.setattr(
        type(group_buy_service),
        'summary',
        AsyncMock(
            return_value=GroupBuySummary(
                share_code=team.share_code,
                status='forming',
                people=3,
                paid_people=0,
                deadline=team.deadline,
            )
        ),
    )

    data = asyncio.run(group_buy_service.detail(db, team.share_code, user_id=user_id))
    assert data['server_time'] >= now
    assert data['deadline'] == team.deadline
    if user_id == 7:
        assert data['my_order']['pay_type'] == 'hupijiao'
        assert data['my_order']['reserved_until'] == reservation
        assert data['my_order']['reserved_until'] != team.deadline.isoformat()
        assert 'openid' not in data['my_order']
        assert 'extra_data' not in data['my_order']
        # 只下发头像用于展示；账号、订单等标识不能出现在成员项里
        assert data['members'][0]['avatar'] == 'https://cdn/7.png'
        assert 'user_id' not in data['members'][0]
        assert 'order_id' not in data['members'][0]
    else:
        assert data['my_order'] is None
        assert data['members'] == []
        db.get.assert_not_awaited()
