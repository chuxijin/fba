#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.job.model.internship_application import InternshipApplication
from backend.app.job.schema.internship_application import CreateInternshipApplication, UpdateInternshipApplication
from backend.common.enums import ApplicationStatus


class CRUDInternshipApplication(CRUDPlus[InternshipApplication]):
    """投递记录数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> InternshipApplication | None:
        """
        获取投递记录详情

        :param db: 数据库会话
        :param pk: 投递记录 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_job_posting_id(self, db: AsyncSession, job_posting_id: int) -> InternshipApplication | None:
        """
        通过招聘信息 ID 获取投递记录

        :param db: 数据库会话
        :param job_posting_id: 招聘信息 ID
        :return:
        """
        return await self.select_model_by_column(db, job_posting_id=job_posting_id)

    async def get_list(
        self, 
        user_id: int,
        job_posting_id: int | None, 
        application_status: ApplicationStatus | None
    ) -> Select:
        """
        获取投递记录列表

        :param user_id: 用户 ID
        :param job_posting_id: 招聘信息 ID
        :param application_status: 投递状态
        :return:
        """
        filters = {'created_by': user_id}

        if job_posting_id is not None:
            filters['job_posting_id'] = job_posting_id
        if application_status is not None:
            filters['application_status'] = application_status

        return await self.select_order(
            'id',
            'desc',
            load_options=[noload(self.model.job_posting)],
            **filters,
        )

    async def get_all(self, db: AsyncSession) -> Sequence[InternshipApplication]:
        """
        获取所有投递记录

        :param db: 数据库会话
        :return:
        """
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateInternshipApplication) -> None:
        """
        创建投递记录

        :param db: 数据库会话
        :param obj: 创建投递记录参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateInternshipApplication) -> int:
        """
        更新投递记录

        :param db: 数据库会话
        :param pk: 投递记录 ID
        :param obj: 更新投递记录参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, job_application_ids: list[int]) -> int:
        """
        批量删除投递记录

        :param db: 数据库会话
        :param job_application_ids: 投递记录 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=job_application_ids)


internship_application_dao: CRUDInternshipApplication = CRUDInternshipApplication(InternshipApplication)


