from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank_v2.model.user import QbUserPracticePreference


class CRUDPracticePreference(CRUDPlus[QbUserPracticePreference]):
    """用户练习偏好数据库操作类"""

    async def get_by_user_id(self, db: AsyncSession, user_id: int) -> QbUserPracticePreference | None:
        """通过用户 ID 获取练习偏好"""
        stmt = select(QbUserPracticePreference).where(
            QbUserPracticePreference.user_id == user_id,
            QbUserPracticePreference.deleted == 0,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, user_id: int, data: dict[str, Any]) -> QbUserPracticePreference:
        """创建用户练习偏好"""
        preference = QbUserPracticePreference(user_id=user_id, created_by=user_id, **data)
        db.add(preference)
        await db.flush()
        return preference

    async def update(self, db: AsyncSession, pk: int, *, user_id: int, data: dict[str, Any]) -> int:
        """更新用户练习偏好"""
        data['updated_by'] = user_id
        return await self.update_model_by_column(db, data, id=pk, deleted=0)


practice_preference_dao: CRUDPracticePreference = CRUDPracticePreference(QbUserPracticePreference)
