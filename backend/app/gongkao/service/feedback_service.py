from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_feedback import feedback_dao
from backend.app.gongkao.model.feedback import GkFeedback
from backend.app.gongkao.schema.feedback import CreateFeedbackParam, UpdateFeedbackParam, FeedbackParam, DeleteFeedbackParam
from backend.common.pagination import paging_data


class FeedbackService:
    async def create(self, db: AsyncSession, obj: CreateFeedbackParam, ip_address: str | None = None) -> GkFeedback:
        # 这里可以加入额外的逻辑，比如根据 ip 限制提交频率
        return await feedback_dao.create(db=db, obj=obj, ip_address=ip_address)

    async def get_list(self, db: AsyncSession, params: FeedbackParam) -> dict[str, Any]:
        select_stmt = await feedback_dao.get_select(params=params)
        return await paging_data(db, select_stmt)

    async def get(self, db: AsyncSession, pk: int) -> GkFeedback | None:
        return await feedback_dao.get(db=db, pk=pk)
    
    async def update(self, db: AsyncSession, pk: int, obj: UpdateFeedbackParam) -> int:
        return await feedback_dao.update(db=db, pk=pk, obj=obj)
        
    async def delete(self, db: AsyncSession, obj: DeleteFeedbackParam) -> int:
        return await feedback_dao.delete(db=db, pks=obj.ids)


feedback_service = FeedbackService()
