from collections.abc import Sequence

import sqlalchemy as sa

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.oc.model import OCRecruitAnnouncement, UserApplication
from backend.plugin.oc.schema.user_application import CreateUserApplicationParam, UpdateUserApplicationParam


class CRUDUserApplication(CRUDPlus[UserApplication]):
    """用户投递记录数据库操作类"""

    async def get(self, db: AsyncSession, application_id: int) -> UserApplication | None:
        """
        获取用户投递记录详情（含公告与公司信息）

        :param db: 数据库会话
        :param application_id: 投递记录 ID
        :return:
        """
        stmt = (
            sa.select(UserApplication)
            .where(UserApplication.id == application_id)
            .options(
                selectinload(UserApplication.announcement).joinedload(OCRecruitAnnouncement.company),
            )
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_user_and_announcement(
        self, db: AsyncSession, user_id: int, announcement_id: int
    ) -> UserApplication | None:
        """
        通过用户ID和公告ID获取投递记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param announcement_id: 公告 ID
        :return:
        """
        return await self.select_model_by_column(
            db, user_id=user_id, announcement_id=announcement_id
        )

    async def get_select(
        self,
        user_id: int | None,
        application_status: str | None,
    ) -> Select:
        """
        获取用户投递记录列表查询表达式（含公告与公司信息）

        :param user_id: 用户 ID
        :param application_status: 投递状态
        :return:
        """
        filters = {}

        if user_id is not None:
            filters['user_id'] = user_id
        if application_status is not None:
            filters['application_status'] = application_status

        select_stmt = await self.select_order('created_time', 'desc', **filters)
        return select_stmt.options(
            selectinload(UserApplication.announcement).joinedload(OCRecruitAnnouncement.company),
        )

    async def get_by_user(self, db: AsyncSession, user_id: int) -> Sequence[UserApplication]:
        """
        获取用户的所有投递记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_models_order(db, 'created_time', 'desc', user_id=user_id)

    async def create(self, db: AsyncSession, obj: CreateUserApplicationParam) -> None:
        """
        创建用户投递记录

        :param db: 数据库会话
        :param obj: 创建投递记录参数
        :return:
        """
        await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, application_id: int, obj: UpdateUserApplicationParam) -> int:
        """
        更新用户投递记录

        :param db: 数据库会话
        :param application_id: 投递记录 ID
        :param obj: 更新投递记录参数
        :return:
        """
        return await self.update_model(db, application_id, obj)

    async def delete(self, db: AsyncSession, application_ids: list[int]) -> int:
        """
        批量删除用户投递记录

        :param db: 数据库会话
        :param application_ids: 投递记录 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=application_ids)


user_application_dao: CRUDUserApplication = CRUDUserApplication(UserApplication)
