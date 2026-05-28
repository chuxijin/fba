from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.model.resource import OCResource as Resource
from backend.plugin.oc.schema.resource import CreateResourceParam
from backend.common.exception import errors


class ResourceService:
    """资料包服务"""

    @staticmethod
    async def get_select() -> Select:
        """获取查询语句"""
        return Select(Resource).order_by(Resource.id.asc())

    @staticmethod
    async def get(db: AsyncSession, pk: int) -> Resource:
        """获取资料包详情"""
        resource = await db.get(Resource, pk)
        if not resource:
            raise errors.NotFoundError(msg='资料包不存在')
        return resource

    @staticmethod
    async def get_all(db: AsyncSession) -> list[Resource]:
        """获取所有资料包"""
        stmt = await ResourceService.get_select()
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def create(db: AsyncSession, obj: CreateResourceParam) -> Resource:
        """创建资料包"""
        resource = Resource(**obj.model_dump())
        db.add(resource)
        await db.flush()
        return resource
