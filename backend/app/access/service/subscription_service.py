#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import SubscriptionSource, SubscriptionStatus
from backend.app.access.crud.crud_subscription import subscription_dao
from backend.app.access.crud.crud_template import subscription_template_dao
from backend.app.access.model.subscription import Subscription
from backend.app.access.schema.subscription import (
    CancelSubscriptionParam,
    CreateSubscriptionParam,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone


class SubscriptionService:
    """用户订阅服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> Any:
        """
        获取订阅详情 (带关联的用户名和模板信息)

        :param db: 数据库会话
        :param pk: 订阅 ID
        :return:
        """
        sub = await subscription_dao.get_detail(db, pk)
        if not sub:
            raise errors.NotFoundError(msg='订阅不存在')
        return sub

    @staticmethod
    async def list_active(
        db: AsyncSession, *, user_id: int, ts: datetime | None = None
    ) -> Sequence[Subscription]:
        """
        列出用户当前有效订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        return await subscription_dao.list_active_for_user(db, user_id, ts or timezone.now())

    @staticmethod
    async def list_for_user(
        db: AsyncSession,
        *,
        user_id: int,
        status: SubscriptionStatus | None = None,
    ) -> Sequence[Subscription]:
        """
        列出用户的所有订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态过滤
        :return:
        """
        return await subscription_dao.list_for_user(db, user_id, status=status)

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateSubscriptionParam) -> Subscription:
        """
        创建订阅(显式指定 valid_period)

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        template = await subscription_template_dao.get_by_code(db, obj.template_code)
        if not template:
            raise errors.NotFoundError(msg=f'订阅模板不存在: {obj.template_code}')

        sub = Subscription(
            user_id=obj.user_id,
            template_id=template.id,
            valid_period=obj.valid_period.to_range(),
            source=obj.source,
            source_ref=obj.source_ref,
            parent_subscription_id=obj.parent_subscription_id,
            metadata_=obj.metadata,
        )
        db.add(sub)
        await db.flush()
        await SubscriptionService._invalidate_user_access_cache(obj.user_id)

        # 发送用户消息通知
        try:
            from backend.app.question_bank.schema.user_message import CreateUserMessageParam
            from backend.app.question_bank.service.user_message_service import user_message_service
            from backend.common.log import log

            lower_str = sub.valid_period.lower.strftime("%Y-%m-%d %H:%M:%S") if sub.valid_period.lower else "-"
            upper_str = sub.valid_period.upper.strftime("%Y-%m-%d %H:%M:%S") if sub.valid_period.upper else "永久"

            await user_message_service.create(
                db=db,
                obj_in=CreateUserMessageParam(
                    title="订阅开通通知",
                    content=f"恭喜！您的「{template.name}」订阅已成功开通，有效期为 {lower_str} 至 {upper_str}。",
                    target_type="user",
                    user_id=obj.user_id,
                    message_type="personal",
                    status=1,
                    publish_time=timezone.now()
                )
            )
        except Exception as e:
            log.error(f"发送订阅消息通知失败: {e}", exc_info=True)

        return sub

    @staticmethod
    async def create_from_template(
        db: AsyncSession,
        *,
        user_id: int,
        template_code: str,
        source: SubscriptionSource,
        source_ref: str | None = None,
        start_at: datetime | None = None,
        parent_subscription_id: int | None = None,
    ) -> Subscription:
        """
        基于模板自动开通订阅(自动计算 valid_period)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param template_code: 模板编码
        :param source: 来源
        :param source_ref: 来源引用
        :param start_at: 开始时间, 空则取当前
        :param parent_subscription_id: 父订阅 ID
        :return:
        """
        template = await subscription_template_dao.get_by_code(db, template_code)
        if not template:
            raise errors.NotFoundError(msg=f'订阅模板不存在: {template_code}')

        start = start_at or timezone.now()
        end = start + timedelta(days=template.duration_days) if template.duration_days else None
        period = Range(start, end, bounds='[)')

        sub = Subscription(
            user_id=user_id,
            template_id=template.id,
            valid_period=period,
            source=source,
            source_ref=source_ref,
            parent_subscription_id=parent_subscription_id,
        )
        db.add(sub)
        await db.flush()
        await SubscriptionService._invalidate_user_access_cache(user_id)

        # 发送用户消息通知
        try:
            from backend.app.question_bank.schema.user_message import CreateUserMessageParam
            from backend.app.question_bank.service.user_message_service import user_message_service
            from backend.common.log import log

            lower_str = start.strftime("%Y-%m-%d %H:%M:%S")
            upper_str = end.strftime("%Y-%m-%d %H:%M:%S") if end else "永久"

            await user_message_service.create(
                db=db,
                obj_in=CreateUserMessageParam(
                    title="订阅开通通知",
                    content=f"恭喜！您的「{template.name}」订阅已成功开通，有效期为 {lower_str} 至 {upper_str}。",
                    target_type="user",
                    user_id=user_id,
                    message_type="personal",
                    status=1,
                    publish_time=timezone.now()
                )
            )
        except Exception as e:
            log.error(f"发送订阅模板消息通知失败: {e}", exc_info=True)

        return sub

    @staticmethod
    async def cancel(
        db: AsyncSession, *, pk: int, obj: CancelSubscriptionParam
    ) -> int:
        """
        取消订阅(标记 status=cancelled)

        :param db: 数据库会话
        :param pk: 订阅 ID
        :param obj: 取消参数
        :return:
        """
        sub = await subscription_dao.select_model(db, pk)
        if not sub:
            raise errors.NotFoundError(msg='订阅不存在')
        count = await subscription_dao.update_model(
            db, pk, {'status': SubscriptionStatus.CANCELLED, 'cancel_reason': obj.cancel_reason}
        )
        if count > 0:
            await SubscriptionService._invalidate_user_access_cache(sub.user_id)
        return count

    @staticmethod
    async def revoke_by_source(
        db: AsyncSession,
        *,
        user_id: int,
        source: SubscriptionSource | str,
        source_ref: str,
        reason: str | None = None,
    ) -> int:
        """
        按来源标识撤销订阅(用于退款链路)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param source: 来源标识
        :param source_ref: 来源引用
        :param reason: 撤销原因
        :return:
        """
        from sqlalchemy import select as sa_select

        source_value = source.value if isinstance(source, SubscriptionSource) else source
        stmt = sa_select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.source == source_value,
            Subscription.source_ref == source_ref,
            Subscription.status == SubscriptionStatus.ACTIVE,
        )
        rows = (await db.execute(stmt)).scalars().all()
        for sub in rows:
            sub.status = SubscriptionStatus.REFUNDED
            sub.cancel_reason = reason or '退款撤销'
        if rows:
            await SubscriptionService._invalidate_user_access_cache(user_id)
        return len(rows)

    @staticmethod
    async def extend_by_days(
        db: AsyncSession,
        *,
        user_id: int,
        template_code: str,
        days: int,
        source: SubscriptionSource,
        source_ref: str | None = None,
    ) -> Subscription:
        """
        续期, 找当前同模板的 active 订阅 valid_to 加 days, 无则新建

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param template_code: 模板编码
        :param days: 增加天数
        :param source: 来源
        :param source_ref: 来源引用
        :return:
        """
        if days <= 0:
            raise errors.RequestError(msg='续期天数必须大于 0')

        from sqlalchemy import select as sa_select

        from backend.app.access.model.template import SubscriptionTemplate

        template_stmt = sa_select(SubscriptionTemplate).where(SubscriptionTemplate.code == template_code)
        template = (await db.execute(template_stmt)).scalars().first()
        if not template:
            raise errors.NotFoundError(msg=f'订阅模板不存在: {template_code}')

        existing_stmt = (
            sa_select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.template_id == template.id,
                Subscription.status == SubscriptionStatus.ACTIVE,
            )
            .order_by(Subscription.id.desc())
        )
        existing = (await db.execute(existing_stmt)).scalars().first()

        if existing is not None:
            current_upper = existing.valid_period.upper or timezone.now()
            new_upper = current_upper + timedelta(days=days)
            existing.valid_period = Range(existing.valid_period.lower, new_upper, bounds='[)')
            await SubscriptionService._invalidate_user_access_cache(user_id)

            # 发送用户订阅续期消息通知
            try:
                from backend.app.question_bank.schema.user_message import CreateUserMessageParam
                from backend.app.question_bank.service.user_message_service import user_message_service
                from backend.common.log import log

                upper_str = new_upper.strftime("%Y-%m-%d %H:%M:%S")

                await user_message_service.create(
                    db=db,
                    obj_in=CreateUserMessageParam(
                        title="订阅续期通知",
                        content=f"您的「{template.name}」订阅已成功延期 {days} 天，到期时间更新为 {upper_str}。",
                        target_type="user",
                        user_id=user_id,
                        message_type="personal",
                        status=1,
                        publish_time=timezone.now()
                    )
                )
            except Exception as e:
                log.error(f"发送订阅续期消息通知失败: {e}", exc_info=True)

            return existing

        return await SubscriptionService.create_from_template(
            db,
            user_id=user_id,
            template_code=template_code,
            source=source,
            source_ref=source_ref,
        )

    @staticmethod
    async def expire_due_subscriptions(db: AsyncSession) -> int:
        """
        批量将已过期的 active 订阅标记为 expired

        :param db: 数据库会话
        :return:
        """
        return await subscription_dao.expire_due(db)

    @staticmethod
    async def get_max_grade(db: AsyncSession, *, user_id: int) -> str:
        """
        获取用户当前最高档次(用于 cms 插槽过滤等场景)

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        from backend.app.access.crud.crud_pack import entitlement_pack_dao
        from backend.app.access.crud.crud_template import template_pack_dao

        subs = await subscription_dao.list_active_for_user(db, user_id, timezone.now())
        if not subs:
            return 'basic'

        relations = await template_pack_dao.get_by_templates(db, [s.template_id for s in subs])
        pack_ids = list({r.pack_id for r in relations})
        if not pack_ids:
            return 'basic'

        packs = await entitlement_pack_dao.select_models(db, id__in=pack_ids)
        ranking = ['elite', 'premium', 'standard', 'basic']
        seen = {(getattr(p.grade, 'value', p.grade)) for p in packs}
        for grade in ranking:
            if grade in seen:
                return grade
        return 'basic'

    @staticmethod
    async def _invalidate_user_access_cache(user_id: int) -> None:
        """
        删除用户权益汇总缓存

        :param user_id: 用户 ID
        :return:
        """
        from backend.app.access.service.my_service import my_access_service

        await my_access_service.invalidate_summary_cache(user_id)


subscription_service: SubscriptionService = SubscriptionService()
