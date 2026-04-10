from sqlalchemy_crud_plus import CRUDPlus

from backend.app.content.model.content import Content


class CRUDContent(CRUDPlus[Content]):
    async def get_by_slug(self, db, slug: str) -> Content | None:
        return await self.select_model_by_column(db, 'slug', slug)

    async def get_by_app_code(self, db, app_code: str) -> list[Content]:
        return await self.select_models_by_column(db, 'app_code', app_code)


content_dao = CRUDContent(Content)
