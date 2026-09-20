from collections.abc import Sequence

import sqlalchemy as sa

from sqlalchemy import Select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.oc.model import OCCompany, OCCompanyWebsite
from backend.plugin.oc.schema.company import (
    CompanyWebsiteParam,
    CreateCompanyParam,
    CreateWebsiteParam,
    UpdateCompanyParam,
    UpdateWebsiteParam,
)


class CRUDOCCompany(CRUDPlus[OCCompany]):
    """公司信息数据库操作类"""

    async def get(self, db: AsyncSession, company_id: int) -> OCCompany | None:
        """
        获取公司详情（含网站列表）

        :param db: 数据库会话
        :param company_id: 公司 ID
        :return:
        """
        stmt = (
            sa.select(OCCompany)
            .where(OCCompany.id == company_id)
            .options(selectinload(OCCompany.websites))
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(self, db: AsyncSession, name: str) -> OCCompany | None:
        """
        通过公司名称获取公司

        :param db: 数据库会话
        :param name: 公司名称
        :return:
        """
        return await self.select_model_by_column(db, name=name)

    async def get_select(
        self,
        name: str | None,
        company_type: str | None,
        industry: str | None,
        location: str | None,
    ) -> Select:
        """
        获取公司列表查询表达式（含网站列表）

        :param name: 公司名称
        :param company_type: 公司类型
        :param industry: 所属行业
        :param location: 地点
        :return:
        """
        filters = {}

        if name is not None:
            filters['name__like'] = f'%{name}%'
        if company_type is not None:
            filters['company_type'] = company_type
        if industry is not None:
            filters['industry__like'] = f'%{industry}%'
        if location is not None:
            filters['location__like'] = f'%{location}%'

        select_stmt = await self.select(**filters)
        return (
            select_stmt.options(selectinload(OCCompany.websites))
            .order_by(desc(OCCompany.id))
        )

    async def create(self, db: AsyncSession, obj: CreateCompanyParam) -> OCCompany:
        """
        创建公司（含网站列表）

        :param db: 数据库会话
        :param obj: 创建公司参数
        :return:
        """
        company = OCCompany(**obj.model_dump(exclude={'websites'}))
        db.add(company)
        await db.flush()
        for website in obj.websites:
            db.add(OCCompanyWebsite(company_id=company.id, **website.model_dump()))
        await db.flush()
        return company

    async def update(self, db: AsyncSession, company_id: int, obj: UpdateCompanyParam) -> int:
        """
        更新公司（websites 传入时全量替换网站列表）

        :param db: 数据库会话
        :param company_id: 公司 ID
        :param obj: 更新公司参数
        :return:
        """
        data = obj.model_dump(exclude={'websites'}, exclude_unset=True)
        count = await self.update_model(db, company_id, data)
        if obj.websites is not None:
            await self.replace_websites(db, company_id, obj.websites)
        return count

    async def replace_websites(
        self, db: AsyncSession, company_id: int, websites: Sequence[CompanyWebsiteParam]
    ) -> None:
        """
        全量替换公司网站列表

        :param db: 数据库会话
        :param company_id: 公司 ID
        :param websites: 网站列表
        :return:
        """
        await db.execute(sa.delete(OCCompanyWebsite).where(OCCompanyWebsite.company_id == company_id))
        for website in websites:
            db.add(OCCompanyWebsite(company_id=company_id, **website.model_dump()))
        await db.flush()

    async def delete(self, db: AsyncSession, company_ids: list[int]) -> int:
        """
        批量删除公司（级联删除网站与公告）

        :param db: 数据库会话
        :param company_ids: 公司 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=company_ids)


class CRUDOCCompanyWebsite(CRUDPlus[OCCompanyWebsite]):
    """公司网站数据库操作类"""

    async def get_website_select(
        self,
        company_name: str | None,
        name: str | None,
        url: str | None,
    ) -> Select:
        """
        获取网站列表查询表达式（含所属公司名称）

        :param company_name: 公司名称（模糊）
        :param name: 网站名称（模糊）
        :param url: 网站链接（模糊）
        :return:
        """
        conditions = []
        if company_name is not None:
            conditions.append(OCCompany.name.like(f'%{company_name}%'))
        if name is not None:
            conditions.append(OCCompanyWebsite.name.like(f'%{name}%'))
        if url is not None:
            conditions.append(OCCompanyWebsite.url.like(f'%{url}%'))

        return (
            sa.select(
                OCCompanyWebsite.id,
                OCCompanyWebsite.company_id,
                OCCompany.name.label('company_name'),
                OCCompanyWebsite.url,
                OCCompanyWebsite.name,
                OCCompanyWebsite.remark,
                OCCompanyWebsite.created_time,
            )
            .join(OCCompany, OCCompany.id == OCCompanyWebsite.company_id)
            .where(*conditions)
            .order_by(desc(OCCompanyWebsite.id))
        )

    async def get_website(self, db: AsyncSession, website_id: int) -> OCCompanyWebsite | None:
        """
        获取网站详情

        :param db: 数据库会话
        :param website_id: 网站 ID
        :return:
        """
        return await self.select_model(db, website_id)

    async def get_website_by_url(self, db: AsyncSession, company_id: int, url: str) -> OCCompanyWebsite | None:
        """
        通过公司 ID 与链接获取网站（唯一约束校验）

        :param db: 数据库会话
        :param company_id: 公司 ID
        :param url: 网站链接
        :return:
        """
        return await self.select_model_by_column(db, company_id=company_id, url=url)

    async def create_website(self, db: AsyncSession, obj: CreateWebsiteParam) -> OCCompanyWebsite:
        """
        创建网站

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        website = OCCompanyWebsite(**obj.model_dump())
        db.add(website)
        await db.flush()
        return website

    async def update_website(self, db: AsyncSession, website_id: int, obj: UpdateWebsiteParam) -> int:
        """
        更新网站

        :param db: 数据库会话
        :param website_id: 网站 ID
        :param obj: 更新参数
        :return:
        """
        return await self.update_model(db, website_id, obj.model_dump(exclude_unset=True))

    async def delete_website(self, db: AsyncSession, website_ids: list[int]) -> int:
        """
        批量删除网站

        :param db: 数据库会话
        :param website_ids: 网站 ID 列表
        :return:
        """
        return await self.delete_model_by_column(db, allow_multiple=True, id__in=website_ids)


oc_company_dao: CRUDOCCompany = CRUDOCCompany(OCCompany)
oc_company_website_dao: CRUDOCCompanyWebsite = CRUDOCCompanyWebsite(OCCompanyWebsite)
