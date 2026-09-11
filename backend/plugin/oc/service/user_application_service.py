from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.oc.crud.crud_recruit_announcement import recruit_announcement_dao
from backend.plugin.oc.crud.crud_user_application import user_application_dao
from backend.plugin.oc.model import UserApplication
from backend.plugin.oc.schema.user_application import CreateUserApplicationParam, UpdateUserApplicationParam


class UserApplicationService:
    """用户投递记录服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, application_id: int) -> UserApplication:
        """
        获取用户投递记录详情（含公告与公司信息）

        :param db: 数据库会话
        :param application_id: 投递记录 ID
        :return:
        """
        application = await user_application_dao.get(db, application_id)
        if not application:
            raise errors.NotFoundError(msg='投递记录不存在')
        return application

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int | None,
        application_status: str | None,
    ) -> dict[str, Any]:
        """
        获取用户投递记录列表（含公告与公司信息）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param application_status: 投递状态
        :return:
        """
        application_select = await user_application_dao.get_select(
            user_id=user_id,
            application_status=application_status,
        )
        return await paging_data(db, application_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateUserApplicationParam) -> None:
        """
        创建用户投递记录

        :param db: 数据库会话
        :param obj: 创建投递记录参数
        :return:
        """
        announcement = await recruit_announcement_dao.get(db, obj.announcement_id)
        if not announcement:
            raise errors.NotFoundError(msg='公告不存在')
        existing = await user_application_dao.get_by_user_and_announcement(
            db, obj.user_id, obj.announcement_id
        )
        if existing:
            raise errors.ConflictError(msg='已存在该公告的投递记录')
        await user_application_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, application_id: int, obj: UpdateUserApplicationParam) -> int:
        """
        更新用户投递记录

        :param db: 数据库会话
        :param application_id: 投递记录 ID
        :param obj: 更新投递记录参数
        :return:
        """
        application = await user_application_dao.get(db, application_id)
        if not application:
            raise errors.NotFoundError(msg='投递记录不存在')
        count = await user_application_dao.update(db, application_id, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, application_ids: list[int]) -> int:
        """
        批量删除用户投递记录

        :param db: 数据库会话
        :param application_ids: 投递记录 ID 列表
        :return:
        """
        count = await user_application_dao.delete(db, application_ids)
        return count


user_application_service: UserApplicationService = UserApplicationService()
