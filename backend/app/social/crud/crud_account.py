#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.social.model.account import DomainEnum, PlatformEnum, SocialAccount
from backend.app.social.schema.account import (
    CreateSocialAccountParam,
    UpdateSocialAccountParam,
)


class CRUDSocialAccount(CRUDPlus[SocialAccount]):
    """账号数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> SocialAccount | None:
        """
        获取账号详情

        :param db: 数据库会话
        :param pk: 账号 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_platform_name(self, db: AsyncSession, *, platform: str, name: str) -> SocialAccount | None:
        """通过平台与名称获取账号"""
        return await self.select_model_by_column(db, platform=platform, name=name)

    async def get_list(self, *, platform: str | None, name: str | None, domain: str | None = None) -> Select:
        """获取账号列表查询语句"""
        filters: dict[str, object] = {}
        if platform is not None:
            try:
                filters['platform'] = PlatformEnum(platform).name
            except Exception:
                filters['platform'] = platform
        if name is not None:
            filters['name__like'] = f'%{name}%'
        if domain is not None:
            try:
                filters['domain'] = DomainEnum(domain).name
            except Exception:
                filters['domain'] = domain
        # 显式禁用关系加载，避免异步上下文外 await
        return await self.select_order('id', 'desc', load_strategies={'works': 'noload'}, **filters)

    async def create(
        self, db: AsyncSession, obj: CreateSocialAccountParam, current_user_id: int | None = None
    ) -> SocialAccount:
        """
        创建账号

        :param db: 数据库会话
        :param obj: 创建参数
        :param current_user_id: 当前用户 ID
        :return:
        """
        data = obj.model_dump()
        # 归一化枚举存储为名称
        if isinstance(data.get('platform'), PlatformEnum):
            data['platform'] = data['platform'].name
        elif isinstance(data.get('platform'), str):
            try:
                data['platform'] = PlatformEnum(data['platform']).name
            except Exception:
                pass

        if isinstance(data.get('domain'), DomainEnum):
            data['domain'] = data['domain'].name
        elif isinstance(data.get('domain'), str):
            try:
                data['domain'] = DomainEnum(data['domain']).name
            except Exception:
                pass

        # 归一化 account_info 为 dict
        ai = data.get('account_info')
        if isinstance(ai, str):
            try:
                import json

                data['account_info'] = json.loads(ai)
            except Exception:
                data['account_info'] = None

        if 'created_by' not in data:
            data['created_by'] = current_user_id or 0
        account = self.model(**data)
        db.add(account)
        await db.commit()
        await db.refresh(account)
        return account

    async def update(
        self, db: AsyncSession, pk: int, obj: UpdateSocialAccountParam, current_user_id: int | None = None
    ) -> int:
        """
        更新账号

        :param db: 数据库会话
        :param pk: 主键 ID
        :param obj: 更新参数
        :param current_user_id: 当前用户 ID
        :return:
        """
        update_data = obj.model_dump(exclude_unset=True)
        if isinstance(update_data.get('platform'), PlatformEnum):
            update_data['platform'] = update_data['platform'].name
        elif isinstance(update_data.get('platform'), str):
            try:
                update_data['platform'] = PlatformEnum(update_data['platform']).name
            except Exception:
                pass

        if isinstance(update_data.get('domain'), DomainEnum):
            update_data['domain'] = update_data['domain'].name
        elif isinstance(update_data.get('domain'), str):
            try:
                update_data['domain'] = DomainEnum(update_data['domain']).name
            except Exception:
                pass

        # 归一化 account_info 为 dict
        ai2 = update_data.get('account_info')
        if isinstance(ai2, str):
            try:
                import json

                update_data['account_info'] = json.loads(ai2)
            except Exception:
                update_data['account_info'] = None
        if current_user_id:
            update_data['updated_by'] = current_user_id
        count = await self.update_model_by_column(db, update_data, id=pk)
        await db.commit()
        return count

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """删除账号"""
        count = await self.delete_model_by_column(db, allow_multiple=True, id__in=pks)
        await db.commit()
        return count


# 实例
social_account_dao = CRUDSocialAccount(SocialAccount)
