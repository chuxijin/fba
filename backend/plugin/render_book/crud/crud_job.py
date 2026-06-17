#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy import Select, cast, delete, or_, select
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
        cat_id: int | None = None,
        kp_cat_id: int | None = None,
        bank_ids: set[int] | None = None,
        with_files: bool = True,
        include_deleted: bool = False,
    ) -> Select[tuple[RenderBookJob]]:
        stmt = select(self.model)
        if with_files:
            stmt = stmt.options(selectinload(self.model.files)).execution_options(populate_existing=True)

        if not include_deleted:
            stmt = stmt.where(self.model.del_flag.is_(False))
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
        if cat_id is not None or kp_cat_id is not None:
            conditions = []
            if cat_id is not None:
                conditions.append(cast(self.model.metadata_json['cat_id'].as_string(), sa.BigInteger) == cat_id)
            if kp_cat_id is not None:
                conditions.append(cast(self.model.metadata_json['kp_cat_id'].as_string(), sa.BigInteger) == kp_cat_id)
            if bank_ids:
                conditions.append(cast(self.model.metadata_json['bank_id'].as_string(), sa.BigInteger).in_(bank_ids))
            if conditions:
                stmt = stmt.where(or_(*conditions))

        return stmt.order_by(self.model.created_time.desc(), self.model.id.desc())

    async def soft_delete_by_job_id(self, db: AsyncSession, *, job_id: str) -> int:
        """
        软删除题本任务（仅标记 del_flag，文件保留待 Celery 清理）

        :param db: 数据库会话
        :param job_id: 外部任务 ID
        :return:
        """
        return await self.delete_model_by_column(
            db,
            job_id=job_id,
            logical_deletion=True,
            deleted_flag_column='del_flag',
        )

    async def list_expired_jobs(
        self,
        db: AsyncSession,
        *,
        threshold: datetime,
        limit: int = 200,
    ) -> list[RenderBookJob]:
        """
        查询创建时间早于阈值的题本任务（用于过期清理）

        :param db: 数据库会话
        :param threshold: 时间阈值
        :param limit: 每次取出的最大行数
        :return:
        """
        stmt = (
            select(self.model)
            .options(selectinload(self.model.files))
            .where(self.model.created_time < threshold)
            .order_by(self.model.created_time.asc(), self.model.id.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def hard_delete_by_id(self, db: AsyncSession, *, job_pk: int) -> int:
        """
        物理删除题本任务（级联删除 render_book_job_file）

        :param db: 数据库会话
        :param job_pk: 任务主键 ID
        :return:
        """
        stmt = delete(self.model).where(self.model.id == job_pk)
        result = await db.execute(stmt)
        return result.rowcount or 0


render_book_job_dao: CRUDRenderBookJob = CRUDRenderBookJob(RenderBookJob)
