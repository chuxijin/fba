#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta

from sqlalchemy import delete

from backend.app.admin.crud.crud_user_role_expiry import user_role_expiry_dao
from backend.app.admin.model import user_role
from backend.app.admin.schema.user_role_expiry import CreateUserRoleExpiryParam
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

        # 如果已有记录则更新，否则新建
        existing = await user_role_expiry_dao.get_by_user_and_role(db, user_id, role_id)
        if existing:
            await user_role_expiry_dao.update_model(
                db, existing.id, {'valid_from': valid_from, 'valid_to': valid_to, 'status': 1}
            )
            log.info(f'角色有效期已更新: user_id={user_id}, role_id={role_id}, valid_to={valid_to}')
        else:
            obj = CreateUserRoleExpiryParam(
                user_id=user_id,
                role_id=role_id,
                valid_from=valid_from,
                valid_to=valid_to,
            )
            await user_role_expiry_dao.create_model(db, obj)
            log.info(f'角色有效期已创建: user_id={user_id}, role_id={role_id}, valid_to={valid_to}')

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
        await user_role_expiry_dao.update_model(db, record.id, {'valid_to': new_valid_to, 'status': 1})
        log.info(f'角色有效期已延长: user_id={user_id}, role_id={role_id}, new_valid_to={new_valid_to}')

    @staticmethod
    async def check_and_expire_roles() -> int:
        """
        扫描并处理已过期的用户角色

        定时任务调用：查找过期记录 → 标记 status=2 → 删除 sys_user_role 行 → 清除用户缓存

        :return: 处理的过期记录数
        """
        async with async_db_session.begin() as db:
            expired_records = await user_role_expiry_dao.get_expired(db)
            if not expired_records:
                return 0

            expired_ids = []
            affected_user_ids = set()

            for record in expired_records:
                expired_ids.append(record.id)
                affected_user_ids.add(record.user_id)

                # 删除 sys_user_role 中对应的行
                stmt = delete(user_role).where(
                    user_role.c.user_id == record.user_id,
                    user_role.c.role_id == record.role_id,
                )
                await db.execute(stmt)

            # 批量标记为已过期
            await user_role_expiry_dao.mark_expired(db, expired_ids)

        # 清除受影响用户的缓存
        if affected_user_ids:
            await user_cache_manager.clear(list(affected_user_ids))
            log.info(f'已处理 {len(expired_ids)} 条过期角色, 影响用户: {affected_user_ids}')

        return len(expired_ids)


user_role_expiry_service: UserRoleExpiryService = UserRoleExpiryService()
