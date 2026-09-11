from datetime import timedelta
from typing import Any

import sqlalchemy as sa

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.oc.crud.crud_company import oc_company_dao
from backend.plugin.oc.crud.crud_recruit_announcement import recruit_announcement_dao
from backend.plugin.oc.model import OCCompany, OCRecruitAnnouncement
from backend.plugin.oc.schema.recruit_announcement import (
    CreateRecruitAnnouncementParam,
    UpdateRecruitAnnouncementParam,
)
from backend.utils.timezone import timezone


class OCRecruitAnnouncementService:
    """招聘公告服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, announcement_id: int) -> OCRecruitAnnouncement:
        """
        获取公告详情（含公司信息）

        :param db: 数据库会话
        :param announcement_id: 公告 ID
        :return:
        """
        announcement = await recruit_announcement_dao.get(db, announcement_id)
        if not announcement:
            raise errors.NotFoundError(msg='公告不存在')
        return announcement

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        company_id: int | None,
        company_name: str | None,
        recruitment_type: str | None,
        recruit_target: str | None,
        location: str | None,
        keyword: str | None,
        job_category: str | None,
    ) -> dict[str, Any]:
        """
        获取公告列表（含公司信息与网站列表）

        :param db: 数据库会话
        :param company_id: 公司 ID
        :param company_name: 公司名称
        :param recruitment_type: 招聘类型
        :param recruit_target: 招聘对象
        :param location: 工作地点
        :param keyword: 公告标题/岗位关键词
        :param job_category: 岗位大类（campus=校招类 / intern=实习类）
        :return:
        """
        announcement_select = await recruit_announcement_dao.get_select(
            company_id=company_id,
            company_name=company_name,
            recruitment_type=recruitment_type,
            recruit_target=recruit_target,
            location=location,
            keyword=keyword,
            job_category=job_category,
        )
        return await paging_data(db, announcement_select)

    @staticmethod
    async def get_stats(
        *,
        db: AsyncSession,
        recruitment_type: str | None = None,
        job_category: str | None = None,
    ) -> dict[str, Any]:
        """
        获取公告统计数据

        :param db: 数据库会话
        :param recruitment_type: 招聘类型（精确匹配，为空统计全部）
        :param job_category: 岗位大类（campus=校招类 / intern=实习类，优先于 recruitment_type）
        :return:
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        recent_3_days_start = today_start - timedelta(days=2)
        today_str = today_start.strftime('%Y-%m-%d')
        in_1_day_str = (today_start + timedelta(days=1)).strftime('%Y-%m-%d')
        in_3_days_str = (today_start + timedelta(days=3)).strftime('%Y-%m-%d')

        conditions = []
        if job_category == 'intern':
            conditions.append(OCRecruitAnnouncement.recruitment_type.like('%实习%'))
        elif job_category == 'campus':
            conditions.append(OCRecruitAnnouncement.recruitment_type.not_like('%实习%'))
        elif recruitment_type is not None:
            conditions.append(OCRecruitAnnouncement.recruitment_type == recruitment_type)

        stats_query = select(
            func.count(case((OCRecruitAnnouncement.created_time >= today_start, 1))).label('today_count'),
            func.count(case((OCRecruitAnnouncement.created_time >= recent_3_days_start, 1))).label(
                'recent_3_days_count'
            ),
            func.count(
                case((
                    and_(
                        OCRecruitAnnouncement.end_time.isnot(None),
                        OCRecruitAnnouncement.end_time != '',  # noqa: PLC1901
                        OCRecruitAnnouncement.end_time >= today_str,
                        OCRecruitAnnouncement.end_time <= in_1_day_str,
                    ),
                    1,
                ))
            ).label('deadline_1_day_count'),
            func.count(
                case((
                    and_(
                        OCRecruitAnnouncement.end_time.isnot(None),
                        OCRecruitAnnouncement.end_time != '',  # noqa: PLC1901
                        OCRecruitAnnouncement.end_time >= today_str,
                        OCRecruitAnnouncement.end_time <= in_3_days_str,
                    ),
                    1,
                ))
            ).label('deadline_3_days_count'),
            func.count(
                case((
                    or_(
                        OCRecruitAnnouncement.end_time.is_(None),
                        OCRecruitAnnouncement.end_time == '',  # noqa: PLC1901
                        OCRecruitAnnouncement.end_time >= today_str,
                    ),
                    1,
                ))
            ).label('valid_count'),
            func.count(OCRecruitAnnouncement.id).label('total_count'),
        ).select_from(OCRecruitAnnouncement)
        if conditions:
            stats_query = stats_query.where(sa.and_(*conditions))

        company_count_query = select(func.count(OCCompany.id))

        stats_result = await db.execute(stats_query)
        stats_row = stats_result.one()
        company_count_result = await db.execute(company_count_query)
        company_count = company_count_result.scalar() or 0

        return {
            'today_count': stats_row.today_count or 0,
            'recent_3_days_count': stats_row.recent_3_days_count or 0,
            'deadline_1_day_count': stats_row.deadline_1_day_count or 0,
            'deadline_3_days_count': stats_row.deadline_3_days_count or 0,
            'valid_count': stats_row.valid_count or 0,
            'total_count': stats_row.total_count or 0,
            'company_count': company_count,
        }

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateRecruitAnnouncementParam) -> None:
        """
        创建招聘公告

        :param db: 数据库会话
        :param obj: 创建公告参数
        :return:
        """
        company = await oc_company_dao.get(db, obj.company_id)
        if not company:
            raise errors.NotFoundError(msg='公司不存在')
        await recruit_announcement_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, announcement_id: int, obj: UpdateRecruitAnnouncementParam) -> int:
        """
        更新招聘公告

        :param db: 数据库会话
        :param announcement_id: 公告 ID
        :param obj: 更新公告参数
        :return:
        """
        announcement = await recruit_announcement_dao.get(db, announcement_id)
        if not announcement:
            raise errors.NotFoundError(msg='公告不存在')
        if obj.company_id is not None and obj.company_id != announcement.company_id:
            company = await oc_company_dao.get(db, obj.company_id)
            if not company:
                raise errors.NotFoundError(msg='公司不存在')
        return await recruit_announcement_dao.update(db, announcement_id, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, announcement_ids: list[int]) -> int:
        """
        批量删除招聘公告

        :param db: 数据库会话
        :param announcement_ids: 公告 ID 列表
        :return:
        """
        return await recruit_announcement_dao.delete(db, announcement_ids)


recruit_announcement_service: OCRecruitAnnouncementService = OCRecruitAnnouncementService()
