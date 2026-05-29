#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus, GrantSource
from backend.app.access.crud.crud_entitlement import entitlement_dao
from backend.app.access.crud.crud_grant import direct_grant_dao
from backend.app.access.model.grant import DirectGrant
from backend.app.access.schema.grant import CreateDirectGrantParam
from backend.common.exception import errors


class DirectGrantService:
    """直接授予服务"""

    @staticmethod
    async def get(db: AsyncSession, *, pk: int) -> DirectGrant:
        """
        获取授予详情

        :param db: 数据库会话
        :param pk: 授予 ID
        :return:
        """
        grant = await direct_grant_dao.select_model(db, pk)
        if not grant:
            raise errors.NotFoundError(msg='授予记录不存在')
        return grant

    @staticmethod
    async def get_select(
        *,
        user_id: int | None = None,
        entitlement_code: str | None = None,
        source: GrantSource | None = None,
        status: CommonStatus | None = None,
    ) -> Select:
        """
        获取分页查询语句

        :param user_id: 用户 ID
        :param entitlement_code: 权益编码
        :param source: 来源
        :param status: 状态
        :return:
        """
        return await direct_grant_dao.get_select(
            user_id=user_id,
            entitlement_code=entitlement_code,
            source=source,
            status=status,
        )

    @staticmethod
    async def create(db: AsyncSession, *, obj: CreateDirectGrantParam) -> DirectGrant:
        """
        创建直接授予

        :param db: 数据库会话
        :param obj: 创建参数
        :return:
        """
        entitlement = await entitlement_dao.get_by_code(db, obj.entitlement_code)
        if not entitlement:
            raise errors.NotFoundError(msg=f'权益不存在: {obj.entitlement_code}')

        grant = DirectGrant(
            user_id=obj.user_id,
            entitlement_code=obj.entitlement_code,
            valid_period=obj.valid_period.to_range(),
            source=obj.source,
            value_int=obj.value_int,
            value_meta=obj.value_meta,
            source_ref=obj.source_ref,
            reason=obj.reason,
        )
        db.add(grant)
        await db.flush()
        await DirectGrantService._invalidate_user_access_cache(obj.user_id)

        # 发送用户消息通知
        try:
            from backend.app.question_bank.schema.user_message import CreateUserMessageParam
            from backend.app.question_bank.service.user_message_service import user_message_service
            from backend.common.log import log
            from backend.utils.timezone import timezone

            lower_str = grant.valid_period.lower.strftime("%Y-%m-%d %H:%M:%S") if grant.valid_period.lower else "-"
            upper_str = grant.valid_period.upper.strftime("%Y-%m-%d %H:%M:%S") if grant.valid_period.upper else "永久"

            await user_message_service.create(
                db=db,
                obj_in=CreateUserMessageParam(
                    title="权益授予通知",
                    content=f"系统已成功为您授予专属特权「{entitlement.name}」，有效期为 {lower_str} 至 {upper_str}。",
                    target_type="user",
                    user_id=obj.user_id,
                    message_type="personal",
                    status=1,
                    publish_time=timezone.now()
                )
            )
        except Exception as e:
            log.error(f"发送权益授予消息通知失败: {e}", exc_info=True)

        return grant

    @staticmethod
    async def revoke(db: AsyncSession, *, pk: int) -> int:
        """
        撤销授予(标记 status=archived)

        :param db: 数据库会话
        :param pk: 授予 ID
        :return:
        """
        grant = await DirectGrantService.get(db, pk=pk)
        count = await direct_grant_dao.update_model(db, pk, {'status': CommonStatus.ARCHIVED})
        if count > 0:
            await DirectGrantService._invalidate_user_access_cache(grant.user_id)
        return count

    @staticmethod
    async def _invalidate_user_access_cache(user_id: int) -> None:
        """
        删除用户权益汇总缓存

        :param user_id: 用户 ID
        :return:
        """
        from backend.app.access.service.my_service import my_access_service

        await my_access_service.invalidate_summary_cache(user_id)


direct_grant_service: DirectGrantService = DirectGrantService()
