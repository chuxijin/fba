import sqlalchemy as sa

from sqlalchemy import Select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.oc.model import OCCompany, OCRecruitAnnouncement
from backend.plugin.oc.schema.recruit_announcement import (
    CreateRecruitAnnouncementParam,
    UpdateRecruitAnnouncementParam,
)

# 公告关联加载选项：公司（joinedload 单 JOIN，列表按本帖链接渲染无需网站聚合）
ANNOUNCEMENT_COMPANY_OPTIONS = joinedload(OCRecruitAnnouncement.company)


class CRUDOCRecruitAnnouncement(CRUDPlus[OCRecruitAnnouncement]):
    """招聘公告数据库操作类"""

    async def get(self, db: AsyncSession, announcement_id: int) -> OCRecruitAnnouncement | None:
        """
        获取公告详情（含公司信息与网站列表）

        :param db: 数据库会话
        :param announcement_id: 公告 ID
        :return:
        """
        stmt = (
            sa.select(OCRecruitAnnouncement)
            .where(OCRecruitAnnouncement.id == announcement_id)
            .options(ANNOUNCEMENT_COMPANY_OPTIONS)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_select(
        self,
        company_id: int | None,
        company_name: str | None,
        recruitment_type: str | None,
        recruit_target: str | None,
        location: str | None,
        keyword: str | None,
        job_category: str | None,
    ) -> Select:
        """
        获取公告列表查询表达式（含公司信息与网站列表）

        :param company_id: 公司 ID
        :param company_name: 公司名称
        :param recruitment_type: 招聘类型
        :param recruit_target: 招聘对象
        :param location: 工作地点
        :param keyword: 公告标题/岗位关键词
        :param job_category: 岗位大类（campus=校招类 / intern=实习类，按招聘类型是否含"实习"划分）
        :return:
        """
        stmt = sa.select(OCRecruitAnnouncement).options(ANNOUNCEMENT_COMPANY_OPTIONS)
        conditions = []

        if company_id is not None:
            conditions.append(OCRecruitAnnouncement.company_id == company_id)
        if company_name is not None:
            stmt = stmt.join(OCCompany, OCCompany.id == OCRecruitAnnouncement.company_id)
            conditions.append(OCCompany.name.like(f'%{company_name}%'))
        if recruitment_type is not None:
            conditions.append(OCRecruitAnnouncement.recruitment_type == recruitment_type)
        if recruit_target is not None:
            conditions.append(OCRecruitAnnouncement.recruit_target.like(f'%{recruit_target}%'))
        if location is not None:
            conditions.append(OCRecruitAnnouncement.location.like(f'%{location}%'))
        if keyword is not None:
            conditions.append(
                sa.or_(
                    OCRecruitAnnouncement.title.like(f'%{keyword}%'),
                    OCRecruitAnnouncement.positions.like(f'%{keyword}%'),
                )
            )
        if job_category == 'intern':
            conditions.append(OCRecruitAnnouncement.recruitment_type.like('%实习%'))
        elif job_category == 'campus':
            conditions.append(OCRecruitAnnouncement.recruitment_type.not_like('%实习%'))

        if conditions:
            stmt = stmt.where(sa.and_(*conditions))
        return stmt.order_by(desc(OCRecruitAnnouncement.id))

    async def get_by_source_key(self, db: AsyncSession, source_key: str) -> OCRecruitAnnouncement | None:
        """
        通过来源幂等键获取公告（含公司信息）

        :param db: 数据库会话
        :param source_key: 来源幂等键
        :return:
        """
        stmt = (
            sa.select(OCRecruitAnnouncement)
            .where(OCRecruitAnnouncement.source_key == source_key)
            .options(ANNOUNCEMENT_COMPANY_OPTIONS)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, db: AsyncSession, obj: CreateRecruitAnnouncementParam) -> None:
        """
        创建招聘公告

        :param db: 数据库会话
        :param obj: 创建公告参数
        :return:
        """
        await self.create_model(db, obj, flush=True)

    async def update(self, db: AsyncSession, announcement_id: int, obj: UpdateRecruitAnnouncementParam) -> int:
        """
        更新招聘公告

        :param db: 数据库会话
        :param announcement_id: 公告 ID
        :param obj: 更新公告参数
        :return:
        """
        return await self.update_model(db, announcement_id, obj)

    async def delete(self, db: AsyncSession, announcement_ids: list[int]) -> int:
        """
        批量删除招聘公告

        :param db: 数据库会话
        :param announcement_ids: 公告 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=announcement_ids)


recruit_announcement_dao: CRUDOCRecruitAnnouncement = CRUDOCRecruitAnnouncement(OCRecruitAnnouncement)
