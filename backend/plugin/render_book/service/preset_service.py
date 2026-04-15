#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.plugin.render_book.crud import render_book_template_preset_dao
from backend.plugin.render_book.model import RenderBookTemplatePreset
from backend.plugin.render_book.schema.render import (
    RenderTemplatePresetCreate,
    RenderTemplatePresetPayload,
    RenderTemplatePresetRead,
    RenderTemplatePresetUpdate,
)
from backend.plugin.render_book.utils import get_template_registry


class RenderTemplatePresetService:
    def __init__(self) -> None:
        self._template_registry = get_template_registry()

    async def list_presets(
        self,
        *,
        db: AsyncSession,
        template_key: str | None = None,
        is_active: bool | None = None,
    ) -> list[RenderTemplatePresetRead]:
        presets = await render_book_template_preset_dao.list_presets(
            db,
            template_key=template_key,
            is_active=is_active,
        )
        return [self._to_read(item) for item in presets]

    async def get_preset(self, *, db: AsyncSession, preset_id: int) -> RenderTemplatePresetRead:
        preset = await render_book_template_preset_dao.get_by_id(db, preset_id)
        if preset is None:
            raise errors.NotFoundError(msg='模板预设不存在')
        return self._to_read(preset)

    async def create_preset(self, *, db: AsyncSession, payload: RenderTemplatePresetCreate) -> RenderTemplatePresetRead:
        self._validate_template_key(payload.template_key)
        if payload.is_default:
            await render_book_template_preset_dao.clear_default_flag(db, template_key=payload.template_key)
        preset = await render_book_template_preset_dao.create_preset(
            db,
            data={
                'template_key': payload.template_key,
                'preset_name': payload.preset_name.strip(),
                'description': self._clean_optional_text(payload.description),
                'is_active': payload.is_active,
                'is_default': payload.is_default,
                'sort_order': payload.sort_order,
                'payload_json': payload.payload.model_dump(mode='json'),
                'remark': self._clean_optional_text(payload.remark),
            },
        )
        await db.commit()
        return self._to_read(preset)

    async def update_preset(
        self,
        *,
        db: AsyncSession,
        preset_id: int,
        payload: RenderTemplatePresetUpdate,
    ) -> RenderTemplatePresetRead:
        preset = await render_book_template_preset_dao.get_by_id(db, preset_id)
        if preset is None:
            raise errors.NotFoundError(msg='模板预设不存在')

        update_data: dict = {}
        if payload.preset_name is not None:
            update_data['preset_name'] = payload.preset_name.strip()
        if payload.description is not None:
            update_data['description'] = self._clean_optional_text(payload.description)
        if payload.is_active is not None:
            update_data['is_active'] = payload.is_active
        if payload.is_default is not None:
            update_data['is_default'] = payload.is_default
        if payload.sort_order is not None:
            update_data['sort_order'] = payload.sort_order
        if payload.payload is not None:
            update_data['payload_json'] = payload.payload.model_dump(mode='json')
        if payload.remark is not None:
            update_data['remark'] = self._clean_optional_text(payload.remark)

        if payload.is_default:
            await render_book_template_preset_dao.clear_default_flag(
                db,
                template_key=preset.template_key,
                exclude_id=preset.id,
            )

        updated = await render_book_template_preset_dao.update_preset(db, preset=preset, data=update_data)
        await db.commit()
        return self._to_read(updated)

    async def delete_preset(self, *, db: AsyncSession, preset_id: int) -> None:
        deleted = await render_book_template_preset_dao.delete_preset(db, preset_id=preset_id)
        if deleted <= 0:
            raise errors.NotFoundError(msg='模板预设不存在')
        await db.commit()

    def _validate_template_key(self, template_key: str) -> None:
        if template_key not in self._template_registry:
            raise errors.RequestError(msg='模板不存在，请选择有效模板。')

    @staticmethod
    def _clean_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @staticmethod
    def _to_read(preset: RenderBookTemplatePreset) -> RenderTemplatePresetRead:
        return RenderTemplatePresetRead(
            id=preset.id,
            template_key=preset.template_key,
            preset_name=preset.preset_name,
            description=preset.description,
            is_active=preset.is_active,
            is_default=preset.is_default,
            sort_order=preset.sort_order,
            payload=RenderTemplatePresetPayload.model_validate(preset.payload_json or {}),
            remark=preset.remark,
            created_at=preset.created_time,
            updated_at=preset.updated_time or preset.created_time,
        )


preset_service = RenderTemplatePresetService()
