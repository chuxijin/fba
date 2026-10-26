#!/usr/bin/env python3
import json
import re

from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.cms.crud.crud_slot import cms_slot_dao
from backend.app.cms.schema.share import (
    SHARE_SCENES,
    SHARE_VARIABLES,
    ShareCatalog,
    ShareMaterial,
    ShareSettings,
    validate_image_url,
)
from backend.common.exception import errors
from backend.plugin.config.crud.crud_config import config_dao
from backend.plugin.config.enums import ConfigType
from backend.utils.timezone import timezone

TEMPLATE_VARIABLE = re.compile(r'\{\{\s*([a-z_]+)\s*\}\}')


def normalize_share_slot(data: dict[str, Any]) -> dict[str, Any]:
    """创建及部分更新均校验合并后的数据，避免切换类型/清空字段绕过校验。"""
    if data.get('slot_type') != 'share':
        return data
    scene = str(data.get('scene', '')).removeprefix('share.')
    if data.get('scene') != f'share.{scene}' or scene not in SHARE_SCENES:
        raise errors.RequestError(msg='请选择有效的分享场景')
    try:
        extra = dict(data.get('extra') or {})
        settings = ShareSettings.model_validate(extra.get('share') or {})
        data['image_url'] = validate_image_url(data.get('image_url'))
        for field in ('title', 'subtitle'):
            text = (data.get(field) or '').strip()
            variables = set(TEMPLATE_VARIABLE.findall(text))
            remaining = TEMPLATE_VARIABLE.sub('', text)
            if variables - SHARE_VARIABLES[scene] or '{{' in remaining or '}}' in remaining:
                raise ValueError(f'该场景支持的变量：{", ".join(sorted(SHARE_VARIABLES[scene]))}')
            data[field] = text or None
        if settings.poster_mode != 'disabled' and scene not in {'invite', 'group_buy'}:
            raise ValueError('海报入口适用于邀请和拼团场景')
        if data.get('start_time') and data.get('end_time') and data['end_time'] <= data['start_time']:
            raise ValueError('投放结束时间必须晚于开始时间')
    except (ValueError, TypeError) as exc:
        raise errors.RequestError(msg=str(exc)) from exc
    extra['share'] = settings.model_dump(mode='json')
    data.update(
        extra=extra,
        target_user_type=0,
        target_min_member_level=0,
        target_extra=None,
        max_show_per_user=0,
        max_show_per_day_per_user=0,
        close_dismiss_count=0,
        can_close=False,
        jump_type='none',
        jump_target=None,
        jump_extra=None,
    )
    return data


def legacy_material(item: Any) -> ShareMaterial | None:
    """只迁移旧接口公开过的素材；坏数据不影响其他素材和分享兜底。"""
    if not item.is_frontend:
        return None
    try:
        value = json.loads(item.value)
    except (ValueError, TypeError):
        value = {'title': item.value}
    if not isinstance(value, dict):
        return None
    title = value.get('title')
    image = value.get('image')
    if not isinstance(title, str):
        title = ''
    try:
        image = validate_image_url(image) if isinstance(image, str) else None
    except ValueError:
        image = None
    if not title.strip() and not image:
        return None
    # 旧素材没有模板语义，避免将旧文本中的占位符作为新模板下发。
    title = title.replace('{{', '').replace('}}', '').strip()[:255]
    return ShareMaterial(scene='invite', code=f'share_invite_legacy_{item.id}', title=title or None, image_url=image)


async def first_legacy_invite(db: AsyncSession) -> ShareMaterial | None:
    configs = await config_dao.get_all(db, type=ConfigType.invite)
    for item in sorted(configs, key=lambda entry: entry.id):
        material = legacy_material(item)
        if material:
            return material
    return None


class ShareService:
    @staticmethod
    async def catalog(db: AsyncSession) -> ShareCatalog:
        now = timezone.now()
        slots = await cms_slot_dao.get_share_slots(db)
        materials: dict[str, ShareMaterial] = {}
        cache_seconds = 60
        for slot in slots:
            if slot.deleted != 0 or slot.status != 1 or slot.target_user_type != 0:
                continue
            if slot.start_time and slot.start_time > now:
                cache_seconds = min(cache_seconds, max(1, int((slot.start_time - now).total_seconds())))
                continue
            if slot.end_time and slot.end_time <= now:
                continue
            scene = slot.scene.removeprefix('share.')
            if scene in materials:
                continue
            try:
                settings = ShareSettings.model_validate((slot.extra or {}).get('share') or {})
                image_url = validate_image_url(slot.image_url)
            except (ValidationError, ValueError, TypeError):
                continue
            materials[scene] = ShareMaterial(
                scene=scene,
                code=slot.code,
                title=slot.title,
                description=slot.subtitle,
                image_url=image_url,
                settings=settings,
                valid_until=slot.end_time,
            )
            if slot.end_time:
                cache_seconds = min(cache_seconds, max(1, int((slot.end_time - now).total_seconds())))

        # 已由 CMS 接管的场景即使下线，也不能让旧系统参数重新复活。
        if not any(slot.scene == 'share.invite' for slot in slots):
            legacy = await first_legacy_invite(db)
            if legacy:
                materials['invite'] = legacy
        return ShareCatalog(materials=list(materials.values()), cache_seconds=cache_seconds, server_time=now)

    @staticmethod
    async def legacy_invite_config(db: AsyncSession) -> list[dict[str, str]]:
        catalog = await ShareService.catalog(db)
        material = next((m for m in catalog.materials if m.scene == 'invite'), None)
        if material is None:
            material = next((m for m in catalog.materials if m.scene == 'default'), None)
        title = material.title if material and material.title else '邀请你一起学习，一起进步'
        title = TEMPLATE_VARIABLE.sub(lambda match: '一知行卷' if match[1] == 'brand' else '', title)
        return [{'title': title, 'image': material.image_url or '' if material else ''}]


share_service = ShareService()
