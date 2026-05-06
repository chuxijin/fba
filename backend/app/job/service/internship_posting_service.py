#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy.sql import Select

from backend.app.job.crud.crud_internship_posting import internship_posting_dao
from backend.app.job.model.internship_posting import InternshipPosting
from backend.app.job.schema.internship_posting import (
    CreateInternshipPosting,
    DeleteInternshipPostingParam,
    UpdateInternshipPosting,
)
from backend.common.enums import ApplicationStatus
from backend.common.exception import errors
from backend.database.db import async_db_session


class JobPostingService:
    """招聘信息服务类"""

    @staticmethod
    async def get(*, pk: int) -> InternshipPosting:
        """
        获取招聘信息详情

        :param pk: 招聘信息 ID
        :return:
        """
        async with async_db_session() as db:
            job_posting = await internship_posting_dao.get(db, pk)
            if not job_posting:
                raise errors.NotFoundError(msg='招聘信息不存在')
            return job_posting

    @staticmethod
    async def get_all() -> Sequence[InternshipPosting]:
        """获取所有招聘信息"""
        async with async_db_session() as db:
            job_postings = await internship_posting_dao.get_all(db)
            return job_postings

    @staticmethod
    async def get_select(
        *, 
        company_name: str | None, 
        position: str | None, 
        industry: str | None, 
        recruitment_type: str | None,
        company_type: str | None,
        work_location: str | None,
        recruitment_object: str | None,
        application_status: 'ApplicationStatus | None',
        user_id: int | None = None,
    ) -> Select:
        """
        获取招聘信息列表查询条件
        
        :param company_name: 公司名称
        :param position: 岗位
        :param industry: 所属行业
        :param recruitment_type: 招聘类型
        :return:
        """
        return await internship_posting_dao.get_list(
            company_name=company_name,
            position=position,
            industry=industry,
            recruitment_type=recruitment_type,
            company_type=company_type,
            work_location=work_location,
            recruitment_object=recruitment_object,
            application_status=application_status,
            user_id=user_id,
        )

    @staticmethod
    async def create(*, obj: CreateInternshipPosting, created_by: int) -> None:
        """
        创建招聘信息

        :param obj: 招聘信息创建参数
        :param created_by: 创建者用户 ID
        :return:
        """
        async with async_db_session.begin() as db:
            await internship_posting_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, pk: int, obj: UpdateInternshipPosting) -> int:
        """
        更新招聘信息

        :param pk: 招聘信息 ID
        :param obj: 招聘信息更新参数
        :return:
        """
        async with async_db_session.begin() as db:
            job_posting = await internship_posting_dao.get(db, pk)
            if not job_posting:
                raise errors.NotFoundError(msg='招聘信息不存在')
            count = await internship_posting_dao.update(db, pk, obj)
            return count

    @staticmethod
    async def delete(*, obj: DeleteInternshipPostingParam) -> int:
        """
        批量删除招聘信息

        :param obj: 招聘信息 ID 列表
        :return:
        """
        async with async_db_session.begin() as db:
            count = await internship_posting_dao.delete(db, obj.pks)
            return count


internship_posting_service = JobPostingService()
