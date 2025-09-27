from typing import Sequence, Any

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from backend.app.job.crud.crud_job_application import crud_job_application
from backend.app.job.crud.crud_job_posting import crud_job_posting
from backend.app.job.model.job_application import JobApplication
from backend.app.job.schema.job_application import CreateJobApplication, UpdateJobApplication, JobApplicationSchema
from backend.common.enums import ApplicationStatus
from backend.common.pagination import paging_list_data, _CustomPageParams, PageData
from backend.common.exception import errors


class JobApplicationService:
    """用户岗位投递记录服务"""

    @staticmethod
    async def get(request: Request, _id: int) -> JobApplication | None:
        async with request.state.async_db_session() as db:
            return await crud_job_application.get(db, _id, user_id=request.user.id)

    @staticmethod
    async def get_list(
        request: Request,
        job_posting_id: int | None = None,
        application_status: ApplicationStatus | None = None,
        page_params: _CustomPageParams = None,
    ) -> PageData[JobApplicationSchema]:
        async with request.state.async_db_session() as db:
            raw_data = await crud_job_application.get_list(db, request.user.id, job_posting_id, application_status)
            # 将 SQLAlchemy 模型转换为 Pydantic Schema
            converted_data = [JobApplicationSchema.model_validate(item) for item in raw_data.items]
            return paging_list_data(converted_data, page_params)

    @staticmethod
    async def create(request: Request, obj_in: CreateJobApplication, user_id: int) -> JobApplication:
        """创建投递记录"""
        async with request.state.async_db_session.begin() as db:
            job_posting = await crud_job_posting.get(db, obj_in.job_posting_id)
            if not job_posting:
                raise errors.NotFoundError(msg='招聘信息不存在')
            job_application = await crud_job_application.create(db, obj_in, request.user.id)
            return job_application

    @staticmethod
    async def update(request: Request, obj_in: UpdateJobApplication, _id: int) -> JobApplication | None:
        async with request.state.async_db_session.begin() as db:
            return await crud_job_application.update(db, obj_in, _id, user_id=request.user.id)

    @staticmethod
    async def delete(request: Request, _id: int) -> int | None:
        async with request.state.async_db_session.begin() as db:
            return await crud_job_application.delete(db, _id, user_id=request.user.id)


job_application_service = JobApplicationService()
