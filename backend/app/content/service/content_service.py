from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.content.crud.crud_content import content_dao
from backend.app.content.model.content import Content
from backend.app.content.schema.content import CreateContentParam, UpdateContentParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class ContentService:
    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Content:
        content = await content_dao.select_model(db, pk)
        if not content:
            raise errors.NotFoundError(msg='内容不存在')
        return content

    @staticmethod
    async def get_with_incr_view(*, db: AsyncSession, pk: int) -> Content:
        content = await content_dao.select_model(db, pk)
        if not content:
            raise errors.NotFoundError(msg='内容不存在')
        # 增加浏览量
        content.view_count += 1
        await db.commit()
        return content

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateContentParam) -> None:
        if obj.slug:
            content = await content_dao.get_by_slug(db, obj.slug)
            if content:
                raise errors.ForbiddenError(msg='别名已存在')
        
        await content_dao.create_model(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateContentParam) -> int:
        content = await content_dao.select_model(db, pk)
        if not content:
            raise errors.NotFoundError(msg='内容不存在')
        
        if obj.slug and obj.slug != content.slug:
            content_slug = await content_dao.get_by_slug(db, obj.slug)
            if content_slug:
                raise errors.ForbiddenError(msg='别名已存在')
        
        # 如果是发布操作且之前未发布过，设置发布时间
        if obj.is_published and not content.is_published:
            if not obj.publish_time:
                obj.publish_time = datetime.now()

        return await content_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, pk: list[int]) -> int:
        return await content_dao.delete_model(db, pk)

    @staticmethod
    async def get_list_paged(*, db: AsyncSession, app_code: str = None, category_id: int = None, is_published: bool = None):
        """支持分页的列表查询"""
        stmt = select(Content)
        if app_code:
            stmt = stmt.where(Content.app_code == app_code)
        if category_id:
            stmt = stmt.where(Content.category_id == category_id)
        if is_published is not None:
            stmt = stmt.where(Content.is_published == is_published)
        
        stmt = stmt.order_by(Content.is_pinned.desc(), Content.sort_order.desc(), Content.created_time.desc())
        
        # 使用项目标准的分页处理函数
        return await paging_data(db, stmt)


content_service = ContentService()
