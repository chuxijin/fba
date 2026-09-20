from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.plugin.oc.crud.crud_company import oc_company_dao, oc_company_website_dao
from backend.plugin.oc.model import OCCompany
from backend.plugin.oc.schema.company import (
    CreateCompanyParam,
    CreateWebsiteParam,
    GetWebsiteListDetail,
    UpdateCompanyParam,
    UpdateWebsiteParam,
)


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

    @staticmethod
    async def get_website_list(
        *,
        db: AsyncSession,
        company_name: str | None,
        name: str | None,
        url: str | None,
    ) -> dict[str, Any]:
        """
        获取网站列表（含所属公司名称）

        :param db: 数据库会话
        :param company_name: 公司名称（模糊）
        :param name: 网站名称（模糊）
        :param url: 网站链接（模糊）
        :return:
        """
        website_select = await oc_company_website_dao.get_website_select(
            company_name=company_name,
            name=name,
            url=url,
        )
        return await paging_data(db, website_select, schema_cls=GetWebsiteListDetail)

    @staticmethod
    async def create_website(*, db: AsyncSession, obj: CreateWebsiteParam) -> None:
        """
        创建网站

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        company = await oc_company_dao.get(db, obj.company_id)
        if not company:
            raise errors.NotFoundError(msg='公司不存在')
        existing = await oc_company_website_dao.get_website_by_url(db, obj.company_id, obj.url)
        if existing:
            raise errors.ConflictError(msg='该公司下已存在相同链接的网站')
        await oc_company_website_dao.create_website(db, obj)

    @staticmethod
    async def update_website(*, db: AsyncSession, website_id: int, obj: UpdateWebsiteParam) -> int:
        """
        更新网站

        :param db: 数据库会话
        :param website_id: 网站 ID
        :param obj: 更新参数
        :return:
        """
        website = await oc_company_website_dao.get_website(db, website_id)
        if not website:
            raise errors.NotFoundError(msg='网站不存在')
        company_id = obj.company_id if obj.company_id is not None else website.company_id
        url = obj.url if obj.url is not None else website.url
        if company_id != website.company_id:
            company = await oc_company_dao.get(db, company_id)
            if not company:
                raise errors.NotFoundError(msg='公司不存在')
        if company_id != website.company_id or url != website.url:
            existing = await oc_company_website_dao.get_website_by_url(db, company_id, url)
            if existing and existing.id != website_id:
                raise errors.ConflictError(msg='该公司下已存在相同链接的网站')
        return await oc_company_website_dao.update_website(db, website_id, obj)

    @staticmethod
    async def delete_website(*, db: AsyncSession, website_ids: list[int]) -> int:
        """
        批量删除网站

        :param db: 数据库会话
        :param website_ids: 网站 ID 列表
        :return:
        """
        return await oc_company_website_dao.delete_website(db, website_ids)


oc_company_service: OCCompanyService = OCCompanyService()
