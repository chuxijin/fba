from datetime import date, timedelta
from typing import Any

from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.crud.crud_campus_recruit import campus_recruit_dao
from backend.plugin.oc.model import CampusRecruit
from backend.plugin.oc.schema.campus_recruit import CreateCampusRecruitParam, UpdateCampusRecruitParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class CampusRecruitService:
    """校招岗位服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, job_id: int) -> CampusRecruit:
        """
        获取校招岗位详情

        :param db: 数据库会话
        :param job_id: 岗位 ID
        :return:
        """
        job = await campus_recruit_dao.get(db, job_id)
        if not job:
            raise errors.NotFoundError(msg='岗位不存在')
        return job

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        company_name: str | None,
        company_type: str | None,
        industry: str | None,
        recruitment_type: str | None,
        recruit_target: str | None,
        location: str | None,
        position: str | None,
        application_status: str | None,
    ) -> dict[str, Any]:
        """
        获取校招岗位列表

        :param db: 数据库会话
        :param company_name: 公司名称
        :param company_type: 公司类型
        :param industry: 所属行业
        :param recruitment_type: 招聘类型
        :param recruit_target: 招聘对象
        :param location: 工作地点
        :param position: 岗位
        :param application_status: 投递进度
        :return:
        """
        job_select = await campus_recruit_dao.get_select(
            company_name=company_name,
            company_type=company_type,
            industry=industry,
            recruitment_type=recruitment_type,
            recruit_target=recruit_target,
            location=location,
            position=position,
            application_status=application_status,
        )
        page_data = await paging_data(db, job_select)
        return page_data

    @staticmethod
    async def get_stats(*, db: AsyncSession) -> dict[str, Any]:
        """
        获取校招岗位统计数据
        """
        today = date.today()
        today_str = today.strftime('%Y-%m-%d')
        recent_3_days = today - timedelta(days=2)
        in_1_day_str = (today + timedelta(days=1)).strftime('%Y-%m-%d')
        in_3_days_str = (today + timedelta(days=3)).strftime('%Y-%m-%d')

        stats_query = select(
            func.count(distinct(case((CampusRecruit.update_time == today, CampusRecruit.company_name)))).label(
                'today_count'
            ),
            func.count(distinct(case((CampusRecruit.update_time >= recent_3_days, CampusRecruit.company_name)))).label(
                'recent_3_days_count'
            ),
            func.count(
                distinct(
                    case((
                        and_(
                            CampusRecruit.deadline.isnot(None),
                            CampusRecruit.deadline != '',
                            CampusRecruit.deadline >= today_str,
                            CampusRecruit.deadline <= in_1_day_str,
                        ),
                        CampusRecruit.company_name,
                    ))
                )
            ).label('deadline_1_day_count'),
            func.count(
                distinct(
                    case((
                        and_(
                            CampusRecruit.deadline.isnot(None),
                            CampusRecruit.deadline != '',
                            CampusRecruit.deadline >= today_str,
                            CampusRecruit.deadline <= in_3_days_str,
                        ),
                        CampusRecruit.company_name,
                    ))
                )
            ).label('deadline_3_days_count'),
            func.count(
                distinct(
                    case((
                        or_(
                            CampusRecruit.deadline.is_(None),
                            CampusRecruit.deadline == '',
                            CampusRecruit.deadline >= today_str,
                        ),
                        CampusRecruit.company_name,
                    ))
                )
            ).label('valid_count'),
            func.count(distinct(CampusRecruit.company_name)).label('total_count'),
            func.count(CampusRecruit.id).label('total_job_count'),
        ).select_from(CampusRecruit)
        
        stats_result = await db.execute(stats_query)
        stats_row = stats_result.one()

        return {
            'today_count': stats_row.today_count or 0,
            'recent_3_days_count': stats_row.recent_3_days_count or 0,
            'deadline_1_day_count': stats_row.deadline_1_day_count or 0,
            'deadline_3_days_count': stats_row.deadline_3_days_count or 0,
            'valid_count': stats_row.valid_count or 0,
            'total_count': stats_row.total_count or 0,
            'total_job_count': stats_row.total_job_count or 0,
        }

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateCampusRecruitParam) -> None:
        """
        创建校招岗位

        :param db: 数据库会话
        :param obj: 创建岗位参数
        :return:
        """
        await campus_recruit_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, job_id: int, obj: UpdateCampusRecruitParam) -> int:
        """
        更新校招岗位

        :param db: 数据库会话
        :param job_id: 岗位 ID
        :param obj: 更新岗位参数
        :return:
        """
        job = await campus_recruit_dao.get(db, job_id)
        if not job:
            raise errors.NotFoundError(msg='岗位不存在')
        count = await campus_recruit_dao.update(db, job_id, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, job_ids: list[int]) -> int:
        """
        批量删除校招岗位

        :param db: 数据库会话
        :param job_ids: 岗位 ID 列表
        :return:
        """
        count = await campus_recruit_dao.delete(db, job_ids)
        return count


campus_recruit_service: CampusRecruitService = CampusRecruitService()
