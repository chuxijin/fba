#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select, exists
from sqlalchemy.sql import select as sa_select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.job.model.internship_application import InternshipApplication
from backend.app.job.model.internship_posting import InternshipPosting
from backend.app.job.schema.internship_posting import CreateInternshipPosting, UpdateInternshipPosting
from backend.common.enums import ApplicationStatus


class CRUDJobPosting(CRUDPlus[InternshipPosting]):
    """实习信息数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> InternshipPosting | None:
        """
        获取招聘信息详情

        :param db: 数据库会话
        :param pk: 招聘信息 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_company_name(self, db: AsyncSession, company_name: str) -> InternshipPosting | None:
        """
        通过公司名称获取招聘信息

        :param db: 数据库会话
        :param company_name: 公司名称
        :return:
        """
        return await self.select_model_by_column(db, company_name=company_name)

    async def get_list(
        self, 
        company_name: str | None, 
        position: str | None, 
        industry: str | None, 
        recruitment_type: str | None,
        company_type: str | None,
        work_location: str | None,
        recruitment_object: str | None,
        application_status: 'ApplicationStatus | None' = None,
        user_id: int | None = None,
    ) -> Select:
        """
        获取招聘信息列表

        :param company_name: 公司名称
        :param position: 岗位
        :param industry: 所属行业
        :param recruitment_type: 招聘类型
        :return:
        """
        filters = {}

        if company_name is not None:
            filters['company_name__like'] = f'%{company_name}%'
        if position is not None:
            filters['position__like'] = f'%{position}%'
        if industry is not None:
            filters['industry__like'] = f'%{industry}%'
        if recruitment_type is not None:
            filters['recruitment_type'] = recruitment_type
        if company_type is not None:
            filters['company_type__like'] = f'%{company_type}%'
        if work_location is not None:
            filters['work_location__like'] = f'%{work_location}%'
        if recruitment_object is not None:
            filters['recruitment_object__like'] = f'%{recruitment_object}%'

        # 应用“我的投递状态”过滤在最终语句中添加 exists 条件（不能作为 filters 键）
        if application_status is not None and user_id is not None:
            pass

        stmt = await self.select_order(
            'id',
            'desc',
            load_options=[selectinload(self.model.job_applications)],
            **filters,
        )

        if application_status is not None and user_id is not None:
            subq = sa_select(InternshipApplication.id).where(
                InternshipApplication.job_posting_id == self.model.id,
                InternshipApplication.created_by == user_id,
                InternshipApplication.application_status == application_status,
            ).limit(1)
            stmt = stmt.where(exists(subq))

        return stmt

    async def get_all(self, db: AsyncSession) -> Sequence[InternshipPosting]:
        """
        获取所有招聘信息

        :param db: 数据库会话
        :return:
        """
        return await self.select_models(db)

    async def create(self, db: AsyncSession, obj: CreateInternshipPosting, created_by: int) -> None:
        """
        创建招聘信息

        :param db: 数据库会话
        :param obj: 创建招聘信息参数
        :param created_by: 创建者用户 ID
        :return:
        """
        data = obj.model_dump()
        new_obj = InternshipPosting(created_by=created_by, **data)
        db.add(new_obj)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateInternshipPosting) -> int:
        """
        更新招聘信息

        :param db: 数据库会话
        :param pk: 招聘信息 ID
        :param obj: 更新招聘信息参数
        :return:
        """
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, job_posting_ids: list[int]) -> int:
        """
        批量删除招聘信息

        :param db: 数据库会话
        :param job_posting_ids: 招聘信息 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=job_posting_ids)


internship_posting_dao: CRUDJobPosting = CRUDJobPosting(InternshipPosting)
