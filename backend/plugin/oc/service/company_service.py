from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.oc.crud.crud_company import oc_company_dao
from backend.plugin.oc.model import OCCompany
from backend.plugin.oc.schema.company import CreateCompanyParam, UpdateCompanyParam


class OCCompanyService:
    """公司信息服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, company_id: int) -> OCCompany:
        """
        获取公司详情（含网站列表）

        :param db: 数据库会话
        :param company_id: 公司 ID
        :return:
        """
        company = await oc_company_dao.get(db, company_id)
        if not company:
            raise errors.NotFoundError(msg='公司不存在')
        return company

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        name: str | None,
        company_type: str | None,
        industry: str | None,
        location: str | None,
    ) -> dict[str, Any]:
        """
        获取公司列表

        :param db: 数据库会话
        :param name: 公司名称
        :param company_type: 公司类型
        :param industry: 所属行业
        :param location: 地点
        :return:
        """
        company_select = await oc_company_dao.get_select(
            name=name,
            company_type=company_type,
            industry=industry,
            location=location,
        )
        return await paging_data(db, company_select)

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateCompanyParam) -> None:
        """
        创建公司

        :param db: 数据库会话
        :param obj: 创建公司参数
        :return:
        """
        existing = await oc_company_dao.get_by_name(db, obj.name)
        if existing:
            raise errors.ConflictError(msg='公司已存在')
        await oc_company_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, company_id: int, obj: UpdateCompanyParam) -> int:
        """
        更新公司

        :param db: 数据库会话
        :param company_id: 公司 ID
        :param obj: 更新公司参数
        :return:
        """
        company = await oc_company_dao.get(db, company_id)
        if not company:
            raise errors.NotFoundError(msg='公司不存在')
        if obj.name is not None and obj.name != company.name:
            existing = await oc_company_dao.get_by_name(db, obj.name)
            if existing:
                raise errors.ConflictError(msg='公司名称已存在')
        return await oc_company_dao.update(db, company_id, obj)

    @staticmethod
    async def delete(*, db: AsyncSession, company_ids: list[int]) -> int:
        """
        批量删除公司（级联删除网站与公告）

        :param db: 数据库会话
        :param company_ids: 公司 ID 列表
        :return:
        """
        return await oc_company_dao.delete(db, company_ids)


oc_company_service: OCCompanyService = OCCompanyService()
