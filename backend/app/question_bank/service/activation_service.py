#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.actcode.schema.actcode import RedeemCodeParam, RedeemCodeResult
from backend.app.actcode.service.actcode_service import actcode_service


class ActivationService:
    """题库激活码服务（精简版，会员权益创建后续补充）"""

    @staticmethod
    async def query_code_info(*, db: AsyncSession, code: str) -> RedeemCodeResult:
        """
        查询激活码信息（不实际激活）

        :param db: 数据库会话
        :param code: 激活码
        :return:
        """
        return await actcode_service.query_code_info(db=db, code=code, app_id='question_bank')

    @staticmethod
    async def redeem_code_for_qbank(
        *, db: AsyncSession, user_id: int, code: str, ip_address: str | None = None
    ) -> RedeemCodeResult:
        """
        题库系统兑换激活码

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param code: 激活码
        :param ip_address: IP 地址
        :return:
        """
        redeem_param = RedeemCodeParam(
            app_id='question_bank',
            code=code,
            user_id=str(user_id),
            ip_address=ip_address,
        )

        result = await actcode_service.redeem_code(db=db, obj=redeem_param)

        if not result.success:
            return result

        # TODO: 兑换成功后创建会员权益（会员系统后续补充）

        return result


activation_service: ActivationService = ActivationService()
