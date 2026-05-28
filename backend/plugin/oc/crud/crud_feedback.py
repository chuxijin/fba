"""反馈 CRUD"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.oc.model.feedback import OCFeedback as Feedback
from backend.plugin.oc.schema.feedback import FeedbackCreate


class CRUDFeedback(CRUDPlus[Feedback]):
    """反馈 CRUD"""

    async def create(
        self,
        db: AsyncSession,
        obj: FeedbackCreate,
        created_by: int,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """创建反馈"""
        await self.create_model(
            db,
            obj,
            created_by=created_by,
            ip=ip,
            user_agent=user_agent
        )


feedback_dao = CRUDFeedback(Feedback)
