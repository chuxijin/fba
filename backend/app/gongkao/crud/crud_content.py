from sqlalchemy import Select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkContent
from backend.app.gongkao.schema.content import ContentParam, CreateContentParam, UpdateContentParam


class CRUDContent(CRUDPlus[GkContent]):
    """Content CRUD."""

    async def get(self, db: AsyncSession, pk: int) -> GkContent | None:
        """
        Get content by primary key.

        :param db: database session
        :param pk: primary key
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_slug(self, db: AsyncSession, slug: str) -> GkContent | None:
        """
        Get content by slug.

        :param db: database session
        :param slug: content slug
        :return:
        """
        return await self.select_model_by_column(db, slug=slug)

    async def get_select(self, params: ContentParam) -> Select:
        """
        Build content list select.

        :param params: query params
        :return:
        """
        from sqlalchemy import select

        se = select(self.model).order_by(
            self.model.sort_order.desc(),
            self.model.created_time.desc(),
        )

        if params.category_ids:
            se = se.where(self.model.category_id.in_(params.category_ids))
        elif params.category_id is not None:
            se = se.where(self.model.category_id == params.category_id)
        if params.is_pinned is not None:
            se = se.where(self.model.is_pinned == params.is_pinned)
        if params.is_public is not None:
            se = se.where(self.model.is_public == params.is_public)
        if params.is_published is not None:
            se = se.where(self.model.is_published == params.is_published)
        if params.content_type:
            se = se.where(self.model.extra.contains({'content_type': params.content_type}))
        if params.daily_date is not None:
            se = se.where(self.model.extra.contains({'daily_date': params.daily_date.isoformat()}))
        if params.title:
            se = se.where(self.model.title.ilike(f'%{params.title}%'))
        if params.tag:
            se = se.where(self.model.tags.contains([params.tag]))

        return se

    async def create(self, db: AsyncSession, obj: CreateContentParam, created_by: int) -> GkContent:
        """
        Create content.

        :param db: database session
        :param obj: create payload
        :param created_by: user id
        :return:
        """
        content = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(content)
        return content

    async def update(self, db: AsyncSession, pk: int, obj: UpdateContentParam, updated_by: int) -> int:
        """
        Update content.

        :param db: database session
        :param pk: primary key
        :param obj: update payload
        :param updated_by: user id
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        Delete contents by ids.

        :param db: database session
        :param pks: id list
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def increment_view_count(self, db: AsyncSession, pk: int) -> int:
        """
        Increment view count.

        :param db: database session
        :param pk: primary key
        :return:
        """
        content = await self.get(db, pk)
        if content:
            return await self.update_model(db, pk, {'view_count': content.view_count + 1})
        return 0

    async def get_all_tags(self, db: AsyncSession, limit: int = 50) -> list[str]:
        """
        Get published distinct tags.

        :param db: database session
        :param limit: result limit
        :return:
        """
        from sqlalchemy import select, text

        stmt = select(
            func.jsonb_array_elements_text(GkContent.tags).label('tag')
        ).where(
            GkContent.tags.isnot(None),
            GkContent.is_published.is_(True),
        ).group_by(
            text('tag')
        ).order_by(
            func.count().desc()
        ).limit(limit)
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]


content_dao: CRUDContent = CRUDContent(GkContent)
