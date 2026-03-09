from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_content import content_dao
from backend.app.gongkao.model import GkContent
from backend.app.gongkao.schema.content import (
    ContentParam,
    CreateContentParam,
    DeleteContentParam,
    UpdateContentParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class ContentService:
    """公考内容服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> GkContent:
        """
        获取详情

        :param db: 数据库会话
        :param pk: ID
        :return:
        """
        content = await content_dao.get(db, pk)
        if not content:
            raise errors.NotFoundError(msg='内容不存在')
        return content

    @staticmethod
    async def get_by_slug(*, db: AsyncSession, slug: str) -> GkContent:
        """
        通过别名获取详情

        :param db: 数据库会话
        :param slug: 别名
        :return:
        """
        content = await content_dao.get_by_slug(db, slug)
        if not content:
            raise errors.NotFoundError(msg='内容不存在')
        return content

    @staticmethod
    async def get_list(*, db: AsyncSession, params: ContentParam) -> dict[str, Any]:
        """
        获取列表（分页）

        :param db: 数据库会话
        :param params: 查询参数
        :return:
        """
        content_select = await content_dao.get_select(params)
        return await paging_data(db, content_select)

    @staticmethod
    async def get_tags(*, db: AsyncSession, limit: int = 50) -> list[str]:
        """
        获取所有标签

        :param db: 数据库会话
        :param limit: 限制数量
        :return:
        """
        return await content_dao.get_all_tags(db, limit)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateContentParam, created_by: int) -> GkContent:
        """
        创建

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者 ID
        :return:
        """
        # 检查 slug 是否已存在
        existing = await content_dao.get_by_slug(db, obj.slug)
        if existing:
            raise errors.ForbiddenError(msg=f'别名 "{obj.slug}" 已存在')
        return await content_dao.create(db, obj, created_by)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateContentParam, updated_by: int) -> int:
        """
        更新

        :param db: 数据库会话
        :param pk: ID
        :param obj: 更新参数
        :param updated_by: 修改者 ID
        :return:
        """
        content = await content_dao.get(db, pk)
        if not content:
            raise errors.NotFoundError(msg='内容不存在')
        # 若更新 slug，检查唯一性
        if obj.slug and obj.slug != content.slug:
            existing = await content_dao.get_by_slug(db, obj.slug)
            if existing:
                raise errors.ForbiddenError(msg=f'别名 "{obj.slug}" 已存在')
        return await content_dao.update(db, pk, obj, updated_by)

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteContentParam) -> int:
        """
        删除

        :param db: 数据库会话
        :param obj: 删除参数
        :return:
        """
        return await content_dao.delete(db, obj.ids)

    @staticmethod
    async def increment_view(*, db: AsyncSession, pk: int) -> int:
        """
        增加浏览量

        :param db: 数据库会话
        :param pk: ID
        :return:
        """
        content = await content_dao.get(db, pk)
        if not content:
            raise errors.NotFoundError(msg='内容不存在')
        return await content_dao.increment_view_count(db, pk)


content_service: ContentService = ContentService()
