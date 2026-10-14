import asyncio

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.app.payment.service.group_buy_service import group_buy_service
from backend.core.conf import settings
from backend.utils.timezone import timezone

DAO = 'backend.app.payment.service.group_buy_service.group_buy_dao'


def _team(team_id: int, people: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=team_id,
        activity_id=1,
        share_code=f'{team_id:024x}',
        people=people,
        deadline=timezone.now() + timedelta(hours=2),
        snapshot={
            'template_code': 'sub.kaoyan_svip.annual',
            'base': {'name': '考研·SVIP 年卡'},
            'price_cents': 290,
        },
    )


def _paid_member(team_id: int, user_id: int) -> SimpleNamespace:
    return SimpleNamespace(team_id=team_id, user_id=user_id, status='paid', order_id=user_id * 10, paid_at=None)


def _patch(
    monkeypatch: pytest.MonkeyPatch,
    *,
    teams: list[SimpleNamespace],
    members: list[SimpleNamespace],
    avatars: dict[int, str],
) -> None:
    monkeypatch.setattr(settings, 'PAYMENT_GROUP_BUY_ENABLE', True)
    monkeypatch.setattr(f'{DAO}.open_teams', AsyncMock(return_value=teams))
    monkeypatch.setattr(f'{DAO}.paid_members', AsyncMock(return_value=members))
    monkeypatch.setattr(f'{DAO}.avatars', AsyncMock(return_value=avatars))


def test_open_teams_exposes_only_display_fields_and_paid_avatars(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch(
        monkeypatch,
        teams=[_team(1, 3), _team(2, 5)],
        members=[_paid_member(1, 7), _paid_member(1, 8), _paid_member(2, 9)],
        avatars={7: 'https://cdn/7.png', 9: 'https://cdn/9.png'},
    )

    data = asyncio.run(group_buy_service.open_teams(SimpleNamespace(), limit=20))

    assert [row['paid_people'] for row in data] == [2, 1]
    assert [row['remaining_people'] for row in data] == [1, 4]
    # 没有头像的成员不产生占位项，避免把账号信息下发给客户端
    assert data[0]['avatars'] == ['https://cdn/7.png']
    assert data[1]['avatars'] == ['https://cdn/9.png']
    assert data[0]['template_code'] == 'sub.kaoyan_svip.annual'
    assert data[0]['template_name'] == '考研·SVIP 年卡'
    assert data[0]['price_cents'] == 290
    assert set(data[0]) == {
        'activity_id',
        'template_code',
        'template_name',
        'share_code',
        'people',
        'paid_people',
        'remaining_people',
        'price_cents',
        'deadline',
        'avatars',
    }


def test_open_teams_caps_avatars_per_team(monkeypatch: pytest.MonkeyPatch) -> None:
    members = [_paid_member(1, user_id) for user_id in range(7, 12)]
    _patch(
        monkeypatch,
        teams=[_team(1, 5)],
        members=members,
        avatars={user_id: f'https://cdn/{user_id}.png' for user_id in range(7, 12)},
    )

    data = asyncio.run(group_buy_service.open_teams(SimpleNamespace(), limit=20))

    assert data[0]['paid_people'] == 5
    assert data[0]['remaining_people'] == 0
    assert data[0]['avatars'] == ['https://cdn/7.png', 'https://cdn/8.png', 'https://cdn/9.png']


def test_open_teams_returns_nothing_and_skips_queries_when_group_buy_is_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, 'PAYMENT_GROUP_BUY_ENABLE', False)
    open_teams = AsyncMock()
    monkeypatch.setattr(f'{DAO}.open_teams', open_teams)

    assert asyncio.run(group_buy_service.open_teams(SimpleNamespace(), limit=20)) == []
    open_teams.assert_not_awaited()
