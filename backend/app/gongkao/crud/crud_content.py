from sqlalchemy import Select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkContent
from backend.app.gongkao.schema.content import ContentParam, CreateContentParam, UpdateContentParam


class CRUDContent(CRUDPlus[GkContent]):
    """公考内容数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkContent | None:
        """
        获取详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_slug(self, db: AsyncSession, slug: str) -> GkContent | None:
        """
        通过别名获取详情

        :param db: 数据库会话
        :param slug: 别名
        :return:
        """
        return await self.select_model_by_column(db, slug=slug)

    async def get_select(self, params: ContentParam) -> Select:
        """
        获取列表查询表达式

        :param params: 查询参数
        :return:
        """
        from sqlalchemy import select

        se = select(self.model).order_by(
            self.model.sort_order.desc(),
            self.model.created_time.desc(),
        )

        if params.category_id is not None:
            se = se.where(self.model.category_id == params.category_id)
        if params.is_pinned is not None:
            se = se.where(self.model.is_pinned == params.is_pinned)
        if params.is_public is not None:
            se = se.where(self.model.is_public == params.is_public)
        if params.is_published is not None:
            se = se.where(self.model.is_published == params.is_published)

        # 标题模糊搜索
        if params.title:
            se = se.where(self.model.title.ilike(f'%{params.title}%'))

        # JSONB 标签包含查询
        if params.tag:
            se = se.where(self.model.tags.contains([params.tag]))

        return se

    async def create(self, db: AsyncSession, obj: CreateContentParam, created_by: int) -> GkContent:
        """
        创建

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        content = await self.create_model(db, obj, created_by=created_by)
        await db.flush()
        await db.refresh(content)
        return content

    async def update(self, db: AsyncSession, pk: int, obj: UpdateContentParam, updated_by: int) -> int:
        """
        更新

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        删除（支持批量）

        :param db: 数据库会话
        :param pks: 主键 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)

    async def increment_view_count(self, db: AsyncSession, pk: int) -> int:
        """
        增加浏览量

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        content = await self.get(db, pk)
        if content:
            return await self.update_model(db, pk, {'view_count': content.view_count + 1})
        return 0

    async def get_all_tags(self, db: AsyncSession, limit: int = 50) -> list[str]:
        """
        获取所有标签（去重聚合）

        :param db: 数据库会话
        :param limit: 限制数量
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
