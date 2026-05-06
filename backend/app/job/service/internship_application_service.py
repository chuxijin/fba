#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Sequence

from sqlalchemy.sql import Select

from backend.app.job.crud.crud_internship_application import internship_application_dao
from backend.app.job.crud.crud_internship_posting import internship_posting_dao
from backend.app.job.model.internship_application import InternshipApplication
from backend.app.job.schema.internship_application import (
    CreateInternshipApplication,
    DeleteInternshipApplicationParam,
    UpdateInternshipApplication,
)
from backend.common.enums import ApplicationStatus
from backend.common.exception import errors
from backend.database.db import async_db_session


class JobApplicationService:
    """投递记录服务类"""

    @staticmethod
    async def get(*, pk: int, user_id: int) -> InternshipApplication:
        """
        获取投递记录详情

        :param pk: 投递记录 ID
        :param user_id: 用户 ID
        :return:
        """
        async with async_db_session() as db:
            job_application = await internship_application_dao.select_model_by_column(db, id=pk, created_by=user_id)
            if not job_application:
                raise errors.NotFoundError(msg='投递记录不存在')
            return job_application

    @staticmethod
    async def get_all() -> Sequence[InternshipApplication]:
        """获取所有投递记录"""
        async with async_db_session() as db:
            internship_applications = await internship_application_dao.get_all(db)
            return internship_applications

    @staticmethod
    async def get_select(
        *, 
        user_id: int, 
        job_posting_id: int | None, 
        application_status: ApplicationStatus | None
    ) -> Select:
        """
        获取投递记录列表查询条件
        
        :param user_id: 用户 ID
        :param job_posting_id: 招聘信息 ID
        :param application_status: 投递状态
        :return:
        """
        return await internship_application_dao.get_list(
            user_id=user_id,
            job_posting_id=job_posting_id,
            application_status=application_status
        )

    @staticmethod
    async def create(*, obj: CreateInternshipApplication, user_id: int) -> None:
        """
        创建投递记录

        :param obj: 投递记录创建参数
        :param user_id: 用户 ID
        :return:
        """
        async with async_db_session.begin() as db:
            job_posting = await internship_posting_dao.get(db, obj.job_posting_id)
            if not job_posting:
                raise errors.NotFoundError(msg='招聘信息不存在')
            
            # 创建数据库模型实例，并设置创建者
            job_application = InternshipApplication(
                job_posting_id=obj.job_posting_id,
                application_status=obj.application_status,
                created_by=user_id
            )
            db.add(job_application)

    @staticmethod
    async def update(*, pk: int, obj: UpdateInternshipApplication, user_id: int) -> int:
        """
        更新投递记录

        :param pk: 投递记录 ID
        :param obj: 投递记录更新参数
        :param user_id: 用户 ID
        :return:
        """
        async with async_db_session.begin() as db:
            job_application = await internship_application_dao.select_model_by_column(db, id=pk, created_by=user_id)
            if not job_application:
                raise errors.NotFoundError(msg='投递记录不存在')
            count = await internship_application_dao.update(db, pk, obj)
            return count

    @staticmethod
    async def delete(*, obj: DeleteInternshipApplicationParam, user_id: int) -> int:
        """
        批量删除投递记录

        :param obj: 投递记录 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        async with async_db_session.begin() as db:
            # 验证所有投递记录都属于当前用户
            for pk in obj.pks:
                job_application = await internship_application_dao.select_model_by_column(db, id=pk, created_by=user_id)
                if not job_application:
                    raise errors.NotFoundError(msg=f'投递记录 {pk} 不存在或无权限')
            count = await internship_application_dao.delete(db, obj.pks)
            return count


internship_application_service = JobApplicationService()
