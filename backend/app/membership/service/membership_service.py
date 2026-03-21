#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import timedelta

from sqlalchemy import Select, insert, select

from backend.app.admin.model import user_role
from backend.app.admin.service.user_role_expiry_service import user_role_expiry_service
from backend.app.admin.utils.cache import user_cache_manager
from backend.app.membership.crud.crud_membership import user_membership_dao
from backend.app.membership.crud.crud_plan import membership_plan_dao
from backend.app.membership.crud.crud_record import membership_record_dao
from backend.app.membership.model.membership import UserMembership
from backend.app.membership.model.record import MembershipRecord
from backend.app.membership.schema.membership import OpenMembershipParam
from backend.common.exception import errors
from backend.common.log import log
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


class MembershipService:
    """会员服务"""

    @staticmethod
    async def _ensure_user_role(db, *, user_id: int, role_id: int) -> None:
        """
        确保用户角色关联存在

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param role_id: 角色 ID
        :return:
        """
        stmt = select(user_role).where(
            user_role.c.user_id == user_id,
            user_role.c.role_id == role_id,
        )
        result = await db.execute(stmt)
        if not result.first():
            await db.execute(insert(user_role).values(user_id=user_id, role_id=role_id))

    @staticmethod
    async def open_membership(
        db,
        *,
        obj: OpenMembershipParam,
    ) -> UserMembership:
        """
        为用户开通会员

        :param db: 数据库会话
        :param obj: 开通参数
        :return:
        """
        # 查询计划
        plan = await membership_plan_dao.select_model(db, obj.plan_id)
        if not plan:
            raise errors.NotFoundError(msg='会员计划不存在')
        if plan.status != 1:
            raise errors.RequestError(msg='该会员计划已下架')

        # 检查是否已有生效中的同计划会员
        existing = await user_membership_dao.get_by_user_and_plan(db, obj.user_id, obj.plan_id)
        if existing and existing.status == 1:
            now = timezone.now()
            if existing.valid_to and existing.valid_to > now:
                raise errors.RequestError(msg='用户已有该会员计划且尚未过期')

        # 计算有效期
        valid_from = timezone.now()
        valid_to = valid_from + timedelta(days=plan.duration_days)

        if existing:
            # 已有记录（可能已过期），重新激活
            await user_membership_dao.update_model(db, existing.id, {
                'valid_from': valid_from,
                'valid_to': valid_to,
                'level': plan.level,
                'plan_name': plan.name,
                'source': obj.source,
                'status': 1,
                'remark': obj.remark,
            })
            membership = existing
            membership.valid_from = valid_from
            membership.valid_to = valid_to
        else:
            # 新建记录
            membership = UserMembership(
                user_id=obj.user_id,
                plan_id=obj.plan_id,
                plan_name=plan.name,
                level=plan.level,
                valid_from=valid_from,
                valid_to=valid_to,
                source=obj.source,
                remark=obj.remark,
            )
            db.add(membership)
            await db.flush()

        # 写入变动记录
        record = MembershipRecord(
            user_id=obj.user_id,
            plan_id=obj.plan_id,
            days=plan.duration_days,
            source=obj.source,
            source_detail=None,
            valid_to_before=None,
            valid_to_after=valid_to,
            remark=obj.remark,
        )
        db.add(record)

        # 确保角色关联存在
        await MembershipService._ensure_user_role(db, user_id=obj.user_id, role_id=plan.role_id)

        # 设置角色有效期
        await user_role_expiry_service.assign_with_expiry(
            db, user_id=obj.user_id, role_id=plan.role_id, duration_days=plan.duration_days
        )

        log.info(f'会员开通成功: user_id={obj.user_id}, plan={plan.name}, valid_to={valid_to}')

        # 清除用户缓存
        await user_cache_manager.clear([obj.user_id])

        return membership

    @staticmethod
    async def add_days(
        db,
        *,
        user_id: int,
        plan_id: int,
        days: int,
        source: str,
        source_detail: str | None = None,
        remark: str | None = None,
    ) -> UserMembership:
        """
        为用户增加会员天数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param plan_id: 会员计划 ID
        :param days: 增加天数
        :param source: 来源标识
        :param source_detail: 来源详情
        :param remark: 备注
        :return:
        """
        # 查询计划
        plan = await membership_plan_dao.select_model(db, plan_id)
        if not plan:
            raise errors.NotFoundError(msg='会员计划不存在')

        # 查询会员记录
        membership = await user_membership_dao.get_by_user_and_plan(db, user_id, plan_id)
        now = timezone.now()

        if not membership:
            # 无记录，自动创建（等同于开通）
            valid_from = now
            valid_to = now + timedelta(days=days)
            membership = UserMembership(
                user_id=user_id,
                plan_id=plan_id,
                plan_name=plan.name,
                level=plan.level,
                valid_from=valid_from,
                valid_to=valid_to,
                source=source,
            )
            db.add(membership)
            await db.flush()

            valid_to_before = None

            # 确保角色关联存在
            await MembershipService._ensure_user_role(db, user_id=user_id, role_id=plan.role_id)

            # 设置角色有效期
            await user_role_expiry_service.assign_with_expiry(
                db, user_id=user_id, role_id=plan.role_id, duration_days=days
            )
        else:
            # 已有记录，延长有效期
            valid_to_before = membership.valid_to
            base_time = (
                membership.valid_to
                if membership.valid_to and membership.valid_to > now
                else now
            )
            valid_to = base_time + timedelta(days=days)

            # 如果之前已过期，重新设置 valid_from
            update_data: dict = {'valid_to': valid_to, 'status': 1}
            if membership.status == 2:
                update_data['valid_from'] = now
                update_data['source'] = source

            await user_membership_dao.update_model(db, membership.id, update_data)
            membership.valid_to = valid_to

            # 确保角色关联存在
            await MembershipService._ensure_user_role(db, user_id=user_id, role_id=plan.role_id)

            # 延长角色有效期
            await user_role_expiry_service.extend_expiry(
                db, user_id=user_id, role_id=plan.role_id, extra_days=days
            )

        # 写入变动记录
        record = MembershipRecord(
            user_id=user_id,
            plan_id=plan_id,
            days=days,
            source=source,
            source_detail=source_detail,
            valid_to_before=valid_to_before,
            valid_to_after=valid_to,
            remark=remark,
        )
        db.add(record)

        log.info(
            f'会员天数增加: user_id={user_id}, plan={plan.name}, '
            f'days=+{days}, source={source}, valid_to={valid_to}'
        )

        # 清除用户缓存
        await user_cache_manager.clear([user_id])

        return membership

    @staticmethod
    async def get_user_membership_info(
        db,
        *,
        user_id: int,
    ) -> Sequence[UserMembership]:
        """
        获取用户当前生效的会员信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await user_membership_dao.get_active_by_user(db, user_id)

    @staticmethod
    async def get_user_records(
        db,
        *,
        user_id: int,
        plan_id: int | None = None,
    ) -> Select:
        """
        获取用户会员变动记录分页查询语句

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param plan_id: 会员计划 ID
        :return:
        """
        return await membership_record_dao.get_select(user_id=user_id, plan_id=plan_id)

    @staticmethod
    async def check_and_expire_memberships() -> int:
        """同步处理已过期的会员记录状态"""
        async with async_db_session.begin() as db:
            expired_records = await user_membership_dao.get_expired(db)
            if not expired_records:
                return 0

            expired_ids = [record.id for record in expired_records]
            await user_membership_dao.mark_expired(db, expired_ids)

        log.info(f'已处理 {len(expired_ids)} 条过期会员记录')
        return len(expired_ids)


membership_service: MembershipService = MembershipService()
