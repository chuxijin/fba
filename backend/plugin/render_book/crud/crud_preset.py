#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.render_book.model import RenderBookTemplatePreset


class CRUDRenderBookTemplatePreset(CRUDPlus[RenderBookTemplatePreset]):
    """题本模板预设 CRUD"""

    async def list_presets(
        self,
        db: AsyncSession,
        *,
        template_key: str | None = None,
        is_active: bool | None = None,
    ) -> list[RenderBookTemplatePreset]:
        stmt = select(self.model)
        if template_key:
            stmt = stmt.where(self.model.template_key == template_key)
        if is_active is not None:
            stmt = stmt.where(self.model.is_active == is_active)
        stmt = stmt.order_by(
            self.model.template_key.asc(),
            self.model.is_default.desc(),
            self.model.sort_order.asc(),
            self.model.created_time.desc(),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, db: AsyncSession, preset_id: int) -> RenderBookTemplatePreset | None:
        stmt = select(self.model).where(self.model.id == preset_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create_preset(self, db: AsyncSession, *, data: dict[str, Any]) -> RenderBookTemplatePreset:
        preset = self.model(**data)
        db.add(preset)
        await db.flush()
        return preset

    async def update_preset(
        self,
        db: AsyncSession,
        *,
        preset: RenderBookTemplatePreset,
        data: dict[str, Any],
    ) -> RenderBookTemplatePreset:
        for key, value in data.items():
            setattr(preset, key, value)
        await db.flush()
        return preset

    async def clear_default_flag(
        self,
        db: AsyncSession,
        *,
        template_key: str,
        exclude_id: int | None = None,
    ) -> None:
        stmt = update(self.model).where(self.model.template_key == template_key).values(is_default=False)
        if exclude_id is not None:
            stmt = stmt.where(self.model.id != exclude_id)
        await db.execute(stmt)
        await db.flush()

    async def delete_preset(self, db: AsyncSession, *, preset_id: int) -> int:
        stmt = delete(self.model).where(self.model.id == preset_id)
        result = await db.execute(stmt)
        await db.flush()
        return result.rowcount or 0


render_book_template_preset_dao: CRUDRenderBookTemplatePreset = CRUDRenderBookTemplatePreset(RenderBookTemplatePreset)
