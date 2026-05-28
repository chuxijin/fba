"""内推码 Service"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.oc.crud.crud_referral_code import referral_code_dao
from backend.plugin.oc.schema.referral_code import CreateReferralCodeParam, UpdateReferralCodeParam
from backend.common.pagination import paging_data


class ReferralCodeService:
    """内推码服务"""

    @staticmethod
    async def get(db: AsyncSession, pk: int):
        """获取内推码详情"""
        return await referral_code_dao.get(db, pk)

    @staticmethod
    async def get_list(db: AsyncSession, company_name: str | None) -> dict[str, Any]:
        """获取内推码分页列表"""
        select_stmt = await referral_code_dao.get_select(company_name)
        return await paging_data(db, select_stmt)

    @staticmethod
    async def create(db: AsyncSession, obj: CreateReferralCodeParam, user_id: int) -> None:
        """创建内推码"""
        await referral_code_dao.create(db, obj, created_by=user_id)
        await db.commit()

    @staticmethod
    async def update(db: AsyncSession, pk: int, obj: UpdateReferralCodeParam, user_id: int) -> int:
        """更新内推码"""
        count = await referral_code_dao.update(db, pk, obj, updated_by=user_id)
        await db.commit()
        return count

    @staticmethod
    async def delete(db: AsyncSession, pk: int) -> int:
        """删除内推码"""
        count = await referral_code_dao.delete(db, pk)
        await db.commit()
        return count


referral_code_service: ReferralCodeService = ReferralCodeService()
