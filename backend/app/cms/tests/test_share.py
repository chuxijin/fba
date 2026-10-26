from collections.abc import Sequence
from datetime import timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from backend.app.cms.schema.share import ShareSettings
from backend.app.cms.schema.slot import CreateSlotParam, UpdateSlotParam
from backend.app.cms.service.share_service import legacy_material, normalize_share_slot, share_service
from backend.app.cms.service.slot_service import slot_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


def slot(**changes: Any) -> SimpleNamespace:
    return SimpleNamespace(**{
        'id': 1, 'code': 'resource_a', 'scene': 'share.resource', 'status': 1, 'deleted': 0,
        'start_time': None, 'end_time': None, 'target_user_type': 0,
        'title': '一起学「{{resource_title}}」', 'subtitle': '学习有回响',
        'image_url': 'https://cdn.example.com/card.png', 'extra': {},
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


@pytest.mark.parametrize('changes', [
    {'scene': 'share.unknown'},
    {'title': '{{access_token}}'},
    {'title': '{{resource_title'},
    {'image_url': 'http://cdn.example.com/card.png'},
    {'image_url': 'https://cdn.example.com/card.webp'},
    {'extra': {'share': {'poster_mode': 'static'}}},
    {'extra': {'share': {'poster_mode': 'template'}}},
    {'extra': {'share': {'unknown_mode': 'x'}}},
])
def test_share_publish_rejects_bad_templates_and_images(changes: dict[str, Any]) -> None:
    with pytest.raises(errors.RequestError):
        normalize_share_slot({'slot_type': 'share', 'scene': 'share.home', **changes})


def test_share_fields_are_typed_and_do_not_inherit_advertising_controls() -> None:
    result = normalize_share_slot({
        'slot_type': 'share', 'scene': 'share.group_buy', 'title': '{{people}} 人拼 {{product_name}}',
        'target_user_type': 2, 'max_show_per_user': 10, 'close_dismiss_count': 3,
        'extra': {'share': {'cover_mode': 'template', 'poster_mode': 'template'}, 'internal': 'preserved'},
    })
    assert result['target_user_type'] == result['max_show_per_user'] == result['close_dismiss_count'] == 0
    assert result['extra']['internal'] == 'preserved'
    assert ShareSettings.model_validate(result['extra']['share']).poster_mode == 'template'
    assert result['jump_type'] == 'none'


async def test_catalog_filters_lifecycle_and_segments_but_not_advertising_frequency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = timezone.now()
    config = mock_sources(monkeypatch, [
        slot(id=1, end_time=now - timedelta(seconds=1)),
        slot(id=2, start_time=now + timedelta(seconds=20)),
        slot(id=3, target_user_type=2),
        slot(id=4, deleted=4),
        slot(id=5, code='chosen', end_time=now + timedelta(seconds=10)),
        slot(id=6, code='lower_priority'),
    ])
    result = await share_service.catalog(None)
    assert len(result.materials) == 1
    assert result.materials[0].code == 'chosen'
    assert 1 <= result.cache_seconds <= 10
    assert 'target_user_type' not in result.materials[0].model_dump()
    config.assert_awaited_once()


@pytest.mark.parametrize(
    'changes', [{'status': 0}, {'status': 2}, {'deleted': 1}, {'end_time': timezone.now() - timedelta(days=1)}]
)
async def test_retired_cms_invite_never_resurrects_legacy_config(
    monkeypatch: pytest.MonkeyPatch, changes: dict[str, Any]
) -> None:
    config = mock_sources(monkeypatch, [slot(scene='share.invite', **changes)])
    result = await share_service.catalog(None)
    assert not result.materials
    config.assert_not_awaited()


async def test_legacy_compatibility_is_deterministic_and_only_exposes_public_materials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_sources(monkeypatch, [], [
        SimpleNamespace(id=1, is_frontend=False, value='private'),
        SimpleNamespace(id=2, is_frontend=True, value='[]'),
        SimpleNamespace(id=4, is_frontend=True, value='later'),
        SimpleNamespace(
            id=3, is_frontend=True, value='{"title":"一起学习","image":"https://cdn.example.com/card.png"}'
        ),
    ])
    result = await share_service.catalog(None)
    assert [item.code for item in result.materials] == ['share_invite_legacy_3']
    assert await share_service.legacy_invite_config(None) == [
        {'title': '一起学习', 'image': 'https://cdn.example.com/card.png'}
    ]


def test_migration_identity_is_stable_and_bad_legacy_image_does_not_break_text() -> None:
    source = SimpleNamespace(id=123, is_frontend=True, value='{"title":"一起进步","image":"http://old/image.gif"}')
    first = legacy_material(source)
    assert first == legacy_material(source)
    assert first.code == 'share_invite_legacy_123'
    assert first.title == '一起进步'
    assert first.image_url is None


async def test_partial_update_validates_existing_share_settings_and_can_clear_cover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing = CreateSlotParam(
        code='invite', name='邀请', slot_type='share', scene='share.invite', image_url='https://cdn.example.com/a.png'
    )
    monkeypatch.setattr(
        'backend.app.cms.service.slot_service.cms_slot_dao.select_model',
        AsyncMock(return_value=SimpleNamespace(**existing.model_dump())),
    )
    update = AsyncMock(return_value=1)
    monkeypatch.setattr('backend.app.cms.service.slot_service.cms_slot_dao.update_model', update)
    with pytest.raises(errors.RequestError):
        await slot_service.update_slot(db=None, pk=1, obj=UpdateSlotParam(title='{{people}}'))
    update.assert_not_awaited()
    await slot_service.update_slot(db=None, pk=1, obj=UpdateSlotParam(image_url=None))
    assert update.call_args.args[2]['image_url'] is None
    assert update.call_args.args[2]['scene'] == 'share.invite'


async def test_old_invite_endpoint_has_neutral_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_sources(monkeypatch, [])
    assert await share_service.legacy_invite_config(None) == [{'title': '邀请你一起学习，一起进步', 'image': ''}]


async def test_wire_timestamps_keep_timezone_and_iso_separator(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_sources(monkeypatch, [slot(end_time=timezone.now() + timedelta(hours=1))])
    payload = (await share_service.catalog(None)).model_dump(mode='json')
    for value in [payload['server_time'], payload['materials'][0]['valid_until']]:
        assert 'T' in value
        assert '+' in value or value.endswith('Z')


async def test_deleting_share_keeps_takeover_tombstone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        'backend.app.cms.service.slot_service.cms_slot_dao.select_model',
        AsyncMock(return_value=slot(slot_type='share')),
    )
    update = AsyncMock(return_value=1)
    delete = AsyncMock()
    monkeypatch.setattr('backend.app.cms.service.slot_service.cms_slot_dao.update_model', update)
    monkeypatch.setattr('backend.app.cms.service.slot_service.cms_slot_dao.delete_model', delete)
    assert await slot_service.delete_slot(db=None, pk=1) == 1
    assert update.call_args.args[2]['deleted'] == 1
    assert update.call_args.args[2]['status'] == 2
    delete.assert_not_awaited()


def test_public_config_ignores_optional_expired_token_but_qrcode_requires_auth() -> None:
    from starlette.requests import Request

    from backend.core.conf import settings
    from backend.middleware.jwt_auth_middleware import JwtAuthMiddleware

    base = {'type': 'http', 'method': 'GET', 'headers': [(b'authorization', b'Bearer expired-token')]}
    public = Request({**base, 'path': f'{settings.FASTAPI_API_V1_PATH}/cms/share-config'})
    private = Request({**base, 'path': f'{settings.FASTAPI_API_V1_PATH}/invite/codes/mine/qrcode'})
    assert JwtAuthMiddleware.extract_token(public) is None
    assert JwtAuthMiddleware.extract_token(private) == 'expired-token'
