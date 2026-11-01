from collections.abc import Sequence
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.app.cms.schema.share import SHARE_SCENES, SHARE_VARIABLES
from backend.app.cms.service.share_service import normalize_share_slot, share_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


def slot(**changes: Any) -> SimpleNamespace:
    return SimpleNamespace(**{
        'id': 1, 'code': 'bank_default', 'scene': 'share.bank', 'status': 1, 'deleted': 0,
        'start_time': None, 'end_time': None, 'target_user_type': 0,
        'title': '{{bank_title}} 共 {{question_count}} 题', 'subtitle': '{{content_type}}',
        'image_url': 'https://cdn.example.com/bank.png', 'extra': {},
        'max_show_per_user': 1, 'close_dismiss_count': 1,
        **changes,
    })


def mock_sources(
    monkeypatch: pytest.MonkeyPatch,
    slots: list[SimpleNamespace],
    configs: Sequence[SimpleNamespace] = (),
) -> AsyncMock:
    slots_mock = AsyncMock(return_value=slots)
    config_mock = AsyncMock(return_value=configs)
    monkeypatch.setattr('backend.app.cms.service.share_service.cms_slot_dao.get_share_slots', slots_mock)
    monkeypatch.setattr('backend.app.cms.service.share_service.config_dao.get_all', config_mock)
    return config_mock


def test_bank_scene_registered_with_expected_variables() -> None:
    assert 'bank' in SHARE_SCENES
    assert SHARE_VARIABLES['bank'] == {'brand', 'bank_title', 'question_count', 'content_type'}


def test_bank_slot_accepts_supported_variables() -> None:
    result = normalize_share_slot({
        'slot_type': 'share',
        'scene': 'share.bank',
        'title': '{{bank_title}} · 共 {{question_count}} 题',
        'subtitle': '{{content_type}} · {{brand}}',
    })
    assert result['scene'] == 'share.bank'
    assert result['title'] == '{{bank_title}} · 共 {{question_count}} 题'
    assert result['subtitle'] == '{{content_type}} · {{brand}}'
    assert result['jump_type'] == 'none'
    assert result['extra']['share']['poster_mode'] == 'disabled'


async def test_bank_catalog_serializes_bank_material(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_sources(monkeypatch, [slot(end_time=timezone.now() + timedelta(hours=1))])
    payload = (await share_service.catalog(None)).model_dump(mode='json')
    assert len(payload['materials']) == 1
    material = payload['materials'][0]
    assert material['scene'] == 'bank'
    assert material['code'] == 'bank_default'
    assert material['title'] == '{{bank_title}} 共 {{question_count}} 题'
    assert material['settings']['poster_mode'] == 'disabled'
    for value in (material['valid_until'], payload['server_time']):
        assert value is not None
        assert 'T' in value
        assert '+' in value or value.endswith('Z')


@pytest.mark.parametrize('field,text', [
    ('title', '{{access_token}}'),
    ('title', '{{unknown_variable}}'),
    ('title', '{{resource_title}}'),
    ('subtitle', '{{product_name}}'),
])
def test_bank_rejects_unknown_or_private_variables(field: str, text: str) -> None:
    with pytest.raises(errors.RequestError):
        normalize_share_slot({'slot_type': 'share', 'scene': 'share.bank', field: text})


@pytest.mark.parametrize('scene', ['share.unknown', 'bank', 'share.bank.extra'])
def test_unknown_scene_is_rejected(scene: str) -> None:
    with pytest.raises(errors.RequestError):
        normalize_share_slot({'slot_type': 'share', 'scene': scene, 'title': '{{bank_title}}'})


@pytest.mark.parametrize('share', [
    {'poster_mode': 'template'},
    {'poster_mode': 'static', 'poster_image_url': 'https://cdn.example.com/poster.png'},
])
def test_bank_poster_cannot_be_enabled(share: dict[str, str]) -> None:
    with pytest.raises(errors.RequestError):
        normalize_share_slot({
            'slot_type': 'share',
            'scene': 'share.bank',
            'title': '{{bank_title}}',
            'extra': {'share': share},
        })


async def test_catalog_returns_only_online_unexpired_materials(monkeypatch: pytest.MonkeyPatch) -> None:
    now = timezone.now()
    config = mock_sources(monkeypatch, [
        slot(id=1, code='expired', end_time=now - timedelta(seconds=1)),
        slot(id=2, code='future', start_time=now + timedelta(seconds=20)),
        slot(id=3, code='offline', status=0),
        slot(id=4, code='deleted', deleted=1),
        slot(id=5, code='targeted', target_user_type=2),
        slot(id=6, code='live', end_time=now + timedelta(seconds=30)),
    ])
    result = await share_service.catalog(None)
    assert [item.code for item in result.materials] == ['live']
    assert result.materials[0].scene == 'bank'
    assert 1 <= result.cache_seconds <= 60
    config.assert_awaited_once()


@pytest.mark.parametrize('scene,title', [
    ('share.invite', '{{brand}} 邀请你'),
    ('share.resource', '一起学「{{resource_title}}」'),
    ('share.group_buy', '{{people}} 人拼 {{product_name}}'),
])
def test_existing_scenes_still_accept_their_variables(scene: str, title: str) -> None:
    result = normalize_share_slot({'slot_type': 'share', 'scene': scene, 'title': title})
    assert result['scene'] == scene
    assert result['title'] == title


@pytest.mark.parametrize('scene', ['share.invite', 'share.group_buy'])
def test_existing_scenes_still_allow_poster(scene: str) -> None:
    result = normalize_share_slot({
        'slot_type': 'share',
        'scene': scene,
        'extra': {'share': {'poster_mode': 'template'}},
    })
    assert result['extra']['share']['poster_mode'] == 'template'


async def test_existing_catalog_scenes_not_regressed(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_sources(monkeypatch, [
        slot(id=1, code='invite', scene='share.invite'),
        slot(id=2, code='resource', scene='share.resource'),
        slot(id=3, code='group_buy', scene='share.group_buy'),
        slot(id=4, code='bank', scene='share.bank'),
    ])
    result = await share_service.catalog(None)
    assert {item.scene for item in result.materials} == {'invite', 'resource', 'group_buy', 'bank'}
