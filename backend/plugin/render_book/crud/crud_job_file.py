#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.render_book.model import RenderBookJobFile


class CRUDRenderBookJobFile(CRUDPlus[RenderBookJobFile]):
    """题本渲染文件 CRUD"""

    async def create_file(self, db: AsyncSession, *, data: dict[str, Any]) -> RenderBookJobFile:
        file_record = self.model(**data)
        db.add(file_record)
        await db.flush()
        return file_record

    async def list_by_render_job_id(
        self,
        db: AsyncSession,
        *,
        render_job_id: int,
    ) -> list[RenderBookJobFile]:
        stmt = (
            select(self.model)
            .where(self.model.render_job_id == render_job_id)
            .order_by(self.model.created_time, self.model.id)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_identity(
        self,
        db: AsyncSession,
        *,
        render_job_id: int,
        file_kind: str,
        render_variant: str | None = None,
    ) -> RenderBookJobFile | None:
        stmt = select(self.model).where(
            self.model.render_job_id == render_job_id,
            self.model.file_kind == file_kind,
        )
        if render_variant is None:
            stmt = stmt.where(self.model.render_variant.is_(None))
        else:
            stmt = stmt.where(self.model.render_variant == render_variant)
        stmt = stmt.order_by(self.model.id.desc())
        result = await db.execute(stmt)
        return result.scalars().first()

    async def update_file(
        self,
        db: AsyncSession,
        *,
        file_record: RenderBookJobFile,
        data: dict[str, Any],
    ) -> RenderBookJobFile:
        for key, value in data.items():
            setattr(file_record, key, value)
        await db.flush()
        return file_record


render_book_job_file_dao: CRUDRenderBookJobFile = CRUDRenderBookJobFile(RenderBookJobFile)
