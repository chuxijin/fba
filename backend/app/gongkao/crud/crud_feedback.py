from sqlalchemy_crud_plus import CRUDPlus
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.model.feedback import GkFeedback
from backend.app.gongkao.schema.feedback import CreateFeedbackParam, UpdateFeedbackParam, FeedbackParam


class CRUDFeedback(CRUDPlus[GkFeedback]):
    async def get_select(self, params: FeedbackParam):
        filters = {}
        if params.type is not None:
            filters['type'] = params.type
        if params.status is not None:
            filters['status'] = params.status
        if params.content is not None:
            filters['content__like'] = f'%{params.content}%'
        if params.contact is not None:
            filters['contact__like'] = f'%{params.contact}%'
        if params.view_status is not None:
            filters['view_status'] = params.view_status
            
        return await self.select_order('created_time', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateFeedbackParam, ip_address: str | None = None) -> GkFeedback:
        # 转换 obj 为 dict 并添加 ip_address
        obj_dict = obj.dict()
        if ip_address:
            obj_dict['ip_address'] = ip_address
        
        feedback = await self.create_model(db, obj_dict)
        return feedback

    async def update(self, db: AsyncSession, pk: int, obj: UpdateFeedbackParam) -> int:
        return await self.update_model(db, pk, obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)


feedback_dao = CRUDFeedback(GkFeedback)
