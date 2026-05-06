#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy import Select

from backend.app.social.crud.crud_metric import social_work_metric_dao
from backend.app.social.crud.crud_work import social_work_dao
from backend.app.social.model.account import SocialAccount
from backend.app.social.model.work import SocialWork
from backend.app.social.schema.work import (
    CreateSocialWorkParam,
    UpdateSocialWorkParam,
)
from backend.app.social.service.metrics_provider import fetch_metrics_for_work
from backend.common.exception import errors
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


class SocialWorkService:
    """作品服务类"""

    @staticmethod
    async def get(*, pk: int) -> SocialWork:
        """获取作品详情"""
        async with async_db_session() as db:
            work = await social_work_dao.get(db, pk)
            if not work:
                raise errors.NotFoundError(msg='作品不存在')
            return work

    @staticmethod
    async def get_list(*, account_id: int | None, external_id: str | None) -> Select:
        """获取作品列表查询语句"""
        return await social_work_dao.get_list(account_id=account_id, external_id=external_id)

    @staticmethod
    async def create(*, obj: CreateSocialWorkParam, current_user_id: int) -> SocialWork:
        """创建作品"""
        async with async_db_session() as db:
            existed = await social_work_dao.get_by_external(db, account_id=obj.account_id, external_id=obj.external_id)
            if existed:
                raise errors.ConflictError(msg='作品已存在')
            work = await social_work_dao.create(db, obj, current_user_id)
            # 默认发布时间为当前时间
            if getattr(work, 'published_at', None) is None:
                work.published_at = timezone.now()
                await db.commit()

            # 创建后尝试拉取首帧指标并写入快照
            account = await db.get(SocialAccount, obj.account_id)
            metrics = await fetch_metrics_for_work(account=account, work=work) if account else None
            metric_data = metrics or { 'view_count': 0, 'like_count': 0, 'favorite_count': 0, 'comment_count': 0 }
            # 直接构造 dict 交给 CRUD，内部走 model_dump 兼容
            await social_work_metric_dao.create(db, obj=type('obj', (), {
                'model_dump': lambda self=None: {
                    'work_id': work.id,
                    'view_count': metric_data.get('view_count', 0),
                    'like_count': metric_data.get('like_count', 0),
                    'favorite_count': metric_data.get('favorite_count', 0),
                    'comment_count': metric_data.get('comment_count', 0),
                    'share_count': metric_data.get('share_count', 0),
                }
            })(), current_user_id=current_user_id)
            return work

    @staticmethod
    async def update(*, pk: int, obj: UpdateSocialWorkParam, current_user_id: int) -> int:
        """更新作品"""
        async with async_db_session() as db:
            count = await social_work_dao.update(db, pk, obj, current_user_id)
            if count == 0:
                raise errors.NotFoundError(msg='作品不存在')
            return count

    @staticmethod
    async def delete(*, pks: list[int]) -> int:
        """删除作品"""
        async with async_db_session() as db:
            return await social_work_dao.delete(db, pks)


