#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus
from backend.app.access.crud.crud_tier import membership_tier_dao
from backend.app.access.model.template import SubscriptionTemplate
from backend.app.access.model.tier import MembershipTier
from backend.app.access.schema.tier import CreateMembershipTierParam, UpdateMembershipTierParam
from backend.common.exception import errors


class MembershipTierService:
    """商业会员档位服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> MembershipTier:
        tier = await membership_tier_dao.select_model(db, pk)
        if not tier:
            raise errors.NotFoundError(msg='会员档位不存在')
        return tier

    @staticmethod
    async def get_by_code(db: AsyncSession, *, code: str) -> MembershipTier:
        tier = await membership_tier_dao.get_by_code(db, code)
        if not tier:
            raise errors.NotFoundError(msg=f'会员档位不存在: {code}')
        return tier

    @staticmethod
    async def get_select(
        *,
        keyword: str | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        return await membership_tier_dao.get_select(keyword=keyword, status=status)

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateMembershipTierParam) -> None:
        code = obj.code.strip().upper()
        if await membership_tier_dao.get_by_code(db, code):
            raise errors.ConflictError(msg='会员档位编码已存在')
        data = obj.model_dump()
        data['code'] = code
        db.add(MembershipTier(**data))

    @staticmethod
    async def update(db: AsyncSession, *, pk: int, obj: UpdateMembershipTierParam) -> int:
        await MembershipTierService.get(db, pk=pk)
        data = obj.model_dump(exclude_unset=True)
        return await membership_tier_dao.update_model(db, pk, data)

    @staticmethod
    async def delete(db: AsyncSession, *, pk: int) -> int:
        await MembershipTierService.get(db, pk=pk)
        stmt = select(SubscriptionTemplate.id).where(SubscriptionTemplate.tier_id == pk).limit(1)
        if (await db.execute(stmt)).scalar_one_or_none() is not None:
            raise errors.ConflictError(msg='该会员档位已被订阅模板使用，不能删除')
        return await membership_tier_dao.delete_model(db, pk)


membership_tier_service: MembershipTierService = MembershipTierService()
