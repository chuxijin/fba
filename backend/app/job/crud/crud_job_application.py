from typing import Sequence, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.job.model.job_application import JobApplication
from backend.app.job.schema.job_application import CreateJobApplication, UpdateJobApplication
from backend.common.enums import ApplicationStatus
from backend.common.pagination import paging_data


class CRUDJobApplication(CRUDPlus[JobApplication]):
    """用户岗位投递记录 CRUD"""

    async def get(self, db: AsyncSession, _id: int, user_id: int) -> JobApplication | None:
        query = select(self.model).where(self.model.id == _id, self.model.created_by == user_id)
        return (await db.execute(query)).scalar_one_or_none()

    async def get_by_job_posting_id(self, db: AsyncSession, job_posting_id: int) -> JobApplication | None:
        return await self.get_by_field(db, "job_posting_id", job_posting_id)

    async def get_list(
        self,
        db: AsyncSession,
        user_id: int,
        job_posting_id: int | None = None,
        application_status: ApplicationStatus | None = None,
    ) -> dict[str, Any]:
        query = select(self.model).where(self.model.created_by == user_id)
        if job_posting_id:
            query = query.where(self.model.job_posting_id == job_posting_id)
        if application_status:
            query = query.where(self.model.application_status == application_status)
        return await paging_data(db, query)

    async def get_all(self, db: AsyncSession) -> Sequence[JobApplication]:
        # 此方法仅供管理员使用，或者后期根据需求增加用户筛选
        return await self.get_multi(db)

    async def create(self, db: AsyncSession, obj_in: CreateJobApplication, created_by: int) -> JobApplication:
        db_obj = self.model(**obj_in.model_dump(), created_by=created_by)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self, db: AsyncSession, obj_in: UpdateJobApplication, _id: int, user_id: int
    ) -> JobApplication | None:
        db_obj = await self.get(db, _id, user_id)
        if db_obj:
            for field, value in obj_in.model_dump(exclude_unset=True).items():
                setattr(db_obj, field, value)
            db_obj.updated_by = user_id
            await db.flush()
            await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, _id: int, user_id: int) -> int | None:
        return await self.remove(db, _id, created_by=user_id)


crud_job_application = CRUDJobApplication(JobApplication)
