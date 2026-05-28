"""反馈 Service"""

from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.crud.crud_feedback import feedback_dao
from backend.plugin.oc.schema.feedback import FeedbackCreate


class FeedbackService:
    """反馈服务"""

    @staticmethod
    async def create(
        db: AsyncSession,
        obj: FeedbackCreate,
        user_id: int,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """创建反馈"""
        await feedback_dao.create(
            db=db,
            obj=obj,
            created_by=user_id,
            ip=ip,
            user_agent=user_agent
        )
        await db.commit()


feedback_service = FeedbackService()
