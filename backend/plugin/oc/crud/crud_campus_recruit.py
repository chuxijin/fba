from collections.abc import Sequence

from sqlalchemy import Select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.oc.model import CampusRecruit
from backend.plugin.oc.schema.campus_recruit import CreateCampusRecruitParam, UpdateCampusRecruitParam


class CRUDCampusRecruit(CRUDPlus[CampusRecruit]):
    """校招岗位数据库操作类"""

    async def get(self, db: AsyncSession, job_id: int) -> CampusRecruit | None:
        """
        获取校招岗位详情

        :param db: 数据库会话
        :param job_id: 岗位 ID
        :return:
        """
        return await self.select_model(db, job_id)

    async def get_select(
        self,
        company_name: str | None,
        company_type: str | None,
        industry: str | None,
        recruitment_type: str | None,
        recruit_target: str | None,
        location: str | None,
        position: str | None,
        application_status: str | None,
    ) -> Select:
        """
        获取校招岗位列表查询表达式

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
        filters = {}

        if company_name is not None:
            filters['company_name__like'] = f'%{company_name}%'
        if company_type is not None:
            filters['company_type'] = company_type
        if industry is not None:
            filters['industry__like'] = f'%{industry}%'
        if recruitment_type is not None:
            filters['recruitment_type'] = recruitment_type
        if recruit_target is not None:
            filters['recruit_target__like'] = f'%{recruit_target}%'
        if location is not None:
            filters['location__like'] = f'%{location}%'
        if position is not None:
            filters['positions__like'] = f'%{position}%'
        if application_status is not None:
            filters['application_status'] = application_status

        # 先按 update_time 降序，再按 created_time 降序
        select_stmt = await self.select(**filters)
        return select_stmt.order_by(desc(CampusRecruit.update_time), desc(CampusRecruit.created_time))

    async def get_all(self, db: AsyncSession) -> Sequence[CampusRecruit]:
        """
        获取所有校招岗位

        :param db: 数据库会话
        :return:
        """
        return await self.select_models_order(db, 'created_time', 'desc')

    async def create(self, db: AsyncSession, obj: CreateCampusRecruitParam) -> None:
        """
        创建校招岗位

        :param db: 数据库会话
        :param obj: 创建岗位参数
        :return:
        """
        await self.create_model(db, obj)

    async def update(self, db: AsyncSession, job_id: int, obj: UpdateCampusRecruitParam) -> int:
        """
        更新校招岗位

        :param db: 数据库会话
        :param job_id: 岗位 ID
        :param obj: 更新岗位参数
        :return:
        """
        return await self.update_model(db, job_id, obj)

    async def delete(self, db: AsyncSession, job_ids: list[int]) -> int:
        """
        批量删除校招岗位

        :param db: 数据库会话
        :param job_ids: 岗位 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=job_ids)


campus_recruit_dao: CRUDCampusRecruit = CRUDCampusRecruit(CampusRecruit)
