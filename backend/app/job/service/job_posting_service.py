from typing import Sequence, Any

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Request

from backend.app.job.crud.crud_job_posting import crud_job_posting
from backend.app.job.model.job_posting import JobPosting
from backend.app.job.schema.job_posting import CreateJobPosting, UpdateJobPosting, JobPostingSchema
from backend.common.pagination import paging_list_data, _CustomPageParams, PageData


class JobPostingService:
    """招聘信息服务"""

    @staticmethod
    async def get(request: Request, _id: int) -> JobPosting | None:
        async with request.state.async_db_session() as db:
            return await crud_job_posting.get(db, _id)

    @staticmethod
    async def get_list(
        request: Request,
        company_name: str | None = None,
        position: str | None = None,
        industry: str | None = None,
        recruitment_type: str | None = None,
        page_params: _CustomPageParams = None,
    ) -> PageData[JobPostingSchema]:
        async with request.state.async_db_session() as db:
            raw_data = await crud_job_posting.get_list(db, company_name, position, industry, recruitment_type)
            # 将 SQLAlchemy 模型转换为 Pydantic Schema
            converted_data = [JobPostingSchema.model_validate(item) for item in raw_data.items]
            return paging_list_data(converted_data, page_params)

    @staticmethod
    async def get_all(request: Request) -> Sequence[JobPosting]:
        async with request.state.async_db_session() as db:
            return await crud_job_posting.get_all(db)

    @staticmethod
    async def create(request: Request, obj_in: CreateJobPosting, user_id: int) -> JobPosting:
        async with request.state.async_db_session.begin() as db:
            return await crud_job_posting.create(db, obj_in, user_id)

    @staticmethod
    async def update(request: Request, obj_in: UpdateJobPosting, _id: int, user_id: int) -> JobPosting | None:
        async with request.state.async_db_session.begin() as db:
            return await crud_job_posting.update(db, obj_in, _id, user_id)

    @staticmethod
    async def delete(request: Request, _id: int) -> int | None:
        async with request.state.async_db_session.begin() as db:
            return await crud_job_posting.delete(db, _id)


job_posting_service = JobPostingService()
