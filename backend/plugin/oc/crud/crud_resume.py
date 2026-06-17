"""简历 CRUD"""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.model.user_resume import UserResume
from backend.plugin.oc.schema.resume import SaveResumeParam


class CRUDResume:
    """简历数据操作"""

    @staticmethod
    async def get_by_user_id(db: AsyncSession, user_id: int) -> UserResume | None:
        """根据用户ID获取简历"""
        stmt = select(UserResume).where(UserResume.user_id == user_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def create(db: AsyncSession, user_id: int, obj: SaveResumeParam) -> UserResume:
        """创建简历"""
        resume = UserResume(user_id=user_id, encrypted_data=obj.encrypted_data, data_hash=obj.data_hash)
        db.add(resume)
        await db.flush()
        return resume

    @staticmethod
    async def update(db: AsyncSession, resume: UserResume, obj: SaveResumeParam) -> UserResume:
        """更新简历"""
        resume.encrypted_data = obj.encrypted_data
        resume.data_hash = obj.data_hash
        await db.flush()
        return resume

    @staticmethod
    async def delete_by_user_id(db: AsyncSession, user_id: int) -> int:
        """删除用户简历"""
        stmt = delete(UserResume).where(UserResume.user_id == user_id)
        result = await db.execute(stmt)
        return result.rowcount


resume_dao: CRUDResume = CRUDResume()
