#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.render_book.model import RenderBookJob


class CRUDRenderBookJob(CRUDPlus[RenderBookJob]):
    """题本渲染任务 CRUD"""

    async def create_job(self, db: AsyncSession, *, data: dict[str, Any]) -> RenderBookJob:
        job = self.model(**data)
        db.add(job)
        await db.flush()
        return job

    async def get_by_job_id(
        self,
        db: AsyncSession,
        job_id: str,
        *,
        with_files: bool = False,
    ) -> RenderBookJob | None:
        stmt = select(self.model).where(self.model.job_id == job_id)
        if with_files:
            stmt = stmt.options(selectinload(self.model.files)).execution_options(populate_existing=True)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def update_by_job_id(
        self,
        db: AsyncSession,
        *,
        job_id: str,
        data: dict[str, Any],
    ) -> RenderBookJob | None:
        job = await self.get_by_job_id(db, job_id)
        if job is None:
            return None

        for key, value in data.items():
            setattr(job, key, value)
        await db.flush()
        return job

    def build_list_stmt(
        self,
        *,
        job_id: str | None = None,
        status: str | None = None,
        template_key: str | None = None,
        mode: str | None = None,
        user_id: int | None = None,
        keyword: str | None = None,
        with_files: bool = True,
    ) -> Select[tuple[RenderBookJob]]:
        stmt = select(self.model)
        if with_files:
            stmt = stmt.options(selectinload(self.model.files)).execution_options(populate_existing=True)

        if job_id:
            stmt = stmt.where(self.model.job_id == job_id)
        if status:
            stmt = stmt.where(self.model.status == status)
        if template_key:
            stmt = stmt.where(self.model.template_key == template_key)
        if mode:
            stmt = stmt.where(self.model.mode == mode)
        if user_id is not None:
            stmt = stmt.where(self.model.user_id == user_id)
        if keyword:
            like_keyword = f'%{keyword.strip()}%'
            stmt = stmt.where(
                self.model.title.ilike(like_keyword)
                | self.model.subtitle.ilike(like_keyword)
                | self.model.job_id.ilike(like_keyword)
            )

        return stmt.order_by(self.model.created_time.desc(), self.model.id.desc())


render_book_job_dao: CRUDRenderBookJob = CRUDRenderBookJob(RenderBookJob)
