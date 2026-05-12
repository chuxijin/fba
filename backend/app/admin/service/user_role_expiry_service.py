#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta

from backend.app.admin.crud.crud_user_role_expiry import user_role_expiry_dao
from backend.app.admin.utils.cache import user_cache_manager
from backend.common.log import log
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


class UserRoleExpiryService:
    """用户角色有效期服务"""

    @staticmethod
    async def assign_with_expiry(
        db,
        *,
        user_id: int,
        role_id: int,
        duration_days: int,
    ) -> None:
        """
        为用户角色分配创建有效期记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_id: 角色 ID
        :param duration_days: 有效天数
        :return:
        """
        valid_from = timezone.now()
        valid_to = valid_from + timedelta(days=duration_days)

        await user_role_expiry_dao.upsert_expiry(
            db,
            user_id=user_id,
            role_id=role_id,
            valid_from=valid_from,
            valid_to=valid_to,
            status=1,
        )
        log.info(f'角色有效期已写入: user_id={user_id}, role_id={role_id}, valid_to={valid_to}')

    @staticmethod
    async def extend_expiry(
        db,
        *,
        user_id: int,
        role_id: int,
        extra_days: int,
    ) -> None:
        """
        延长用户角色有效期

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_id: 角色 ID
        :param extra_days: 延长天数
        :return:
        """
        record = await user_role_expiry_dao.get_by_user_and_role(db, user_id, role_id)
        if not record:
            log.warning(f'角色有效期记录不存在: user_id={user_id}, role_id={role_id}')
            return

        base_time = record.valid_to if record.valid_to and record.valid_to > timezone.now() else timezone.now()
        new_valid_to = base_time + timedelta(days=extra_days)
        await user_role_expiry_dao.upsert_expiry(
            db,
            user_id=user_id,
            role_id=role_id,
            valid_from=record.valid_from,
            valid_to=new_valid_to,
            status=1,
        )
        log.info(f'角色有效期已延长: user_id={user_id}, role_id={role_id}, new_valid_to={new_valid_to}')

    @staticmethod
    async def reduce_expiry(
        db,
        *,
        user_id: int,
        role_id: int,
        reduce_days: int,
    ) -> None:
        """
        扣减用户角色有效期，扣减后若已过期则标记停用

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_id: 角色 ID
        :param reduce_days: 扣减天数(正数)
        :return:
        """
        if reduce_days <= 0:
            return

        record = await user_role_expiry_dao.get_by_user_and_role(db, user_id, role_id)
        if not record or not record.valid_to:
            log.warning(f'角色有效期记录缺失或无 valid_to，跳过扣减: user_id={user_id}, role_id={role_id}')
            return

        now = timezone.now()
        new_valid_to = record.valid_to - timedelta(days=reduce_days)
        if record.valid_from and new_valid_to < record.valid_from:
            new_valid_to = record.valid_from

        new_status = 2 if new_valid_to <= now else (record.status or 1)
        await user_role_expiry_dao.upsert_expiry(
            db,
            user_id=user_id,
            role_id=role_id,
            valid_from=record.valid_from,
            valid_to=new_valid_to,
            status=new_status,
        )
        log.info(
            f'角色有效期已扣减: user_id={user_id}, role_id={role_id}, '
            f'reduce_days={reduce_days}, new_valid_to={new_valid_to}, status={new_status}'
        )

    @staticmethod
    async def check_and_expire_roles() -> int:
        """
        扫描并处理已过期的用户角色

        :return:
        """
        async with async_db_session.begin() as db:
            expired_records = await user_role_expiry_dao.get_expired(db)
            if not expired_records:
                return 0

            expired_ids = [record.id for record in expired_records]
            affected_user_ids = {record.user_id for record in expired_records}
            await user_role_expiry_dao.mark_expired(db, expired_ids)

        if affected_user_ids:
            await user_cache_manager.clear(list(affected_user_ids))
            log.info(f'已处理 {len(expired_ids)} 条过期角色记录, 影响用户: {affected_user_ids}')

        return len(expired_ids)


user_role_expiry_service: UserRoleExpiryService = UserRoleExpiryService()
