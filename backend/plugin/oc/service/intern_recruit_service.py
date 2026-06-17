from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.crud.crud_intern_recruit import intern_recruit_dao
from backend.plugin.oc.model import InternRecruit
from backend.plugin.oc.schema.intern_recruit import CreateInternRecruitParam, UpdateInternRecruitParam
from backend.common.exception import errors
from backend.common.pagination import paging_data


class InternRecruitService:
    """实习岗位服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, job_id: int) -> InternRecruit:
        """
        获取实习岗位详情

        :param db: 数据库会话
        :param job_id: 岗位 ID
        :return:
        """
        job = await intern_recruit_dao.get(db, job_id)
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
        获取实习岗位列表

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
        job_select = await intern_recruit_dao.get_select(
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

        # 计算今日更新数量
        today = date.today()
        today_count_query = select(func.count(InternRecruit.id)).where(InternRecruit.update_time == today)
        today_count_result = await db.execute(today_count_query)
        today_count = today_count_result.scalar() or 0

        # 计算岗位总数
        total_count_query = select(func.count(InternRecruit.id))
        total_count_result = await db.execute(total_count_query)
        total_count = total_count_result.scalar() or 0

        # 添加统计数据
        page_data['stats'] = {'today_count': today_count, 'total_count': total_count}

        return page_data

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateInternRecruitParam) -> None:
        """
        创建实习岗位

        :param db: 数据库会话
        :param obj: 创建岗位参数
        :return:
        """
        await intern_recruit_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, job_id: int, obj: UpdateInternRecruitParam) -> int:
        """
        更新实习岗位

        :param db: 数据库会话
        :param job_id: 岗位 ID
        :param obj: 更新岗位参数
        :return:
        """
        job = await intern_recruit_dao.get(db, job_id)
        if not job:
            raise errors.NotFoundError(msg='岗位不存在')
        count = await intern_recruit_dao.update(db, job_id, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, job_ids: list[int]) -> int:
        """
        批量删除实习岗位

        :param db: 数据库会话
        :param job_ids: 岗位 ID 列表
        :return:
        """
        count = await intern_recruit_dao.delete(db, job_ids)
        return count


intern_recruit_service: InternRecruitService = InternRecruitService()
