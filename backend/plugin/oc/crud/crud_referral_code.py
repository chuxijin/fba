"""内推码 CRUD"""

from sqlalchemy import Select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.oc.model.referral_code import ReferralCode
from backend.plugin.oc.schema.referral_code import CreateReferralCodeParam, UpdateReferralCodeParam


class CRUDReferralCode(CRUDPlus[ReferralCode]):
    """内推码数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> ReferralCode | None:
        """获取内推码详情"""
        return await self.select_model(db, pk)

    async def get_select(self, company_name: str | None = None) -> Select:
        """获取内推码列表查询表达式"""
        filters = {}

        if company_name:
            filters['company_name__like'] = f'%{company_name}%'

        select_stmt = await self.select(**filters)
        return select_stmt.order_by(desc(ReferralCode.created_time))

    async def create(self, db: AsyncSession, obj: CreateReferralCodeParam, created_by: int) -> None:
        """创建内推码"""
        await self.create_model(db, obj, created_by=created_by)

    async def update(self, db: AsyncSession, pk: int, obj: UpdateReferralCodeParam, updated_by: int) -> int:
        """更新内推码"""
        return await self.update_model(db, pk, obj, updated_by=updated_by)

    async def delete(self, db: AsyncSession, pk: int) -> int:
        """删除内推码"""
        return await self.delete_model(db, pk)


referral_code_dao: CRUDReferralCode = CRUDReferralCode(ReferralCode)
