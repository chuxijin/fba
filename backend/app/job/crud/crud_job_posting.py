from typing import Sequence, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.job.model.job_posting import JobPosting
from backend.app.job.schema.job_posting import CreateJobPosting, UpdateJobPosting
from backend.common.pagination import paging_data


class CRUDJobPosting(CRUDPlus[JobPosting]):
    """招聘信息 CRUD"""

    async def get(self, db: AsyncSession, _id: int) -> JobPosting | None:
        return await self.get_by_id(db, _id)

    async def get_by_company_name(self, db: AsyncSession, company_name: str) -> JobPosting | None:
        return await self.get_by_field(db, "company_name", company_name)

    async def get_list(
        self,
        db: AsyncSession,
        company_name: str | None = None,
        position: str | None = None,
        industry: str | None = None,
        recruitment_type: str | None = None,
    ) -> dict[str, Any]:
        query = select(self.model)
        if company_name:
            query = query.where(self.model.company_name.like(f"%{company_name}%"))
        if position:
            query = query.where(self.model.position.like(f"%{position}%"))
        if industry:
            query = query.where(self.model.industry.like(f"%{industry}%"))
        if recruitment_type:
            query = query.where(self.model.recruitment_type == recruitment_type)
        return await paging_data(db, query)

    async def get_all(self, db: AsyncSession) -> Sequence[JobPosting]:
        return await self.get_multi(db)

    async def create(self, db: AsyncSession, obj_in: CreateJobPosting, created_by: int) -> JobPosting:
        db_obj = self.model(**obj_in.model_dump(), created_by=created_by)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, obj_in: UpdateJobPosting, _id: int, updated_by: int) -> JobPosting | None:
        db_obj = await self.get(db, _id)
        if db_obj:
            for field, value in obj_in.model_dump(exclude_unset=True).items():
                setattr(db_obj, field, value)
            db_obj.updated_by = updated_by
            await db.flush()
            await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, _id: int) -> int | None:
        return await self.remove(db, _id)


crud_job_posting = CRUDJobPosting(JobPosting)
