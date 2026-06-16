
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.content.crud.crud_content import content_dao
from backend.app.content.model.content import Content
from backend.app.content.schema.content import CreateContentParam, UpdateContentParam
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


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
                obj.publish_time = timezone.now()

        return await content_dao.update_model(db, pk, obj)

    @staticmethod
    async def get_by_slug(*, db: AsyncSession, slug: str) -> Content:
        content = await content_dao.get_by_slug(db, slug)
        if not content:
            raise errors.NotFoundError(msg='内容不存在')
        return content

    @staticmethod
    async def delete(*, db: AsyncSession, pk: list[int]) -> int:
        return await content_dao.delete_model(db, pk)

    @staticmethod
    async def get_list_paged(
        *,
        db: AsyncSession,
        app_code: str = None,
        category_id: int = None,
        is_published: bool = None,
        keyword: str | None = None,
    ):
        """支持分页的列表查询"""
        stmt = select(Content)
        if app_code:
            stmt = stmt.where(Content.app_code == app_code)
        if category_id:
            # 引入 category_dao 获取此分类下的所有子分类 ID
            from backend.app.admin.crud.crud_category import category_dao
            children_ids = await category_dao.get_all_children_ids(db, category_id)
            if children_ids:
                stmt = stmt.where(Content.category_id.in_(children_ids))
            else:
                stmt = stmt.where(Content.category_id == category_id)
        if is_published is not None:
            stmt = stmt.where(Content.is_published == is_published)
        if keyword:
            keyword_like = f'%{keyword.strip()}%'
            stmt = stmt.where(Content.title.ilike(keyword_like))

        stmt = stmt.order_by(Content.is_pinned.desc(), Content.sort_order.desc(), Content.created_time.desc())
        
        # 使用项目标准的分页处理函数
        return await paging_data(db, stmt)

    @staticmethod
    async def get_related_list(*, db: AsyncSession, pk: int, limit: int = 5) -> list[Content]:
        """获取相关文章（按标签重合度倒排 + 同分类热度保底）"""
        current_content = await content_dao.select_model(db, pk)
        if not current_content:
            return []

        items: list[Content] = []
        exclude_ids = [pk]

        # 1. 策略 1：标签重合度查询
        if current_content.tags and len(current_content.tags) > 0:
            from sqlalchemy.dialects.postgresql import array
            stmt = (
                select(Content)
                .where(
                    Content.id != pk,
                    Content.is_published.is_(True),
                    Content.tags.op('?|')(array(current_content.tags))
                )
                .order_by(Content.view_count.desc())
                .limit(30)  # 查出一批最近或最热的有重合标签的文章，再在内存精细排序
            )
            result = await db.execute(stmt)
            tag_matches = result.scalars().all()

            if tag_matches:
                target_tags = set(current_content.tags)

                def overlap_score(c: Content) -> int:
                    c_tags = set(c.tags) if c.tags else set()
                    return len(target_tags & c_tags)

                # 按重合标签数量降序，再按浏览量降序
                sorted_matches = sorted(tag_matches, key=lambda c: (overlap_score(c), c.view_count), reverse=True)
                items.extend(sorted_matches[:limit])
                exclude_ids.extend([i.id for i in items])

        # 2. 策略 2：如果标签相关的文章不足，从同分类提取热门倒排补充
        if len(items) < limit and current_content.category_id:
            remaining = limit - len(items)
            stmt2 = (
                select(Content)
                .where(
                    Content.id.notin_(exclude_ids),
                    Content.is_published.is_(True),
                    Content.category_id == current_content.category_id
                )
                .order_by(Content.view_count.desc(), Content.created_time.desc())
                .limit(remaining)
            )
            res2 = await db.execute(stmt2)
            cat_matches = res2.scalars().all()
            items.extend(cat_matches)

        return items


content_service = ContentService()
