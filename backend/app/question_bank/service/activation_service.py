#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.actcode.schema.actcode import RedeemCodeParam, RedeemCodeResult
from backend.app.actcode.service.actcode_service import actcode_service
from backend.app.question_bank.crud.crud_membership import membership_dao
from backend.app.question_bank.schema.membership import CreateMembershipParam
from backend.common.exception import errors
from backend.utils.timezone import timezone


class ActivationService:
    """题库激活码服务"""

    @staticmethod
    async def query_code_info(*, db: AsyncSession, code: str) -> RedeemCodeResult:
        """
        查询激活码信息（不实际激活）

        :param db: 数据库会话
        :param code: 激活码
        :return: 激活码信息
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
        :return: 兑换结果
        """
        # 调用激活码系统的兑换接口
        redeem_param = RedeemCodeParam(
            app_id='question_bank',
            code=code,
            user_id=str(user_id),
            ip_address=ip_address,
        )

        result = await actcode_service.redeem_code(db=db, obj=redeem_param)

        if not result.success:
            return result

        # 兑换成功，根据 reward_data 创建会员权益
        try:
            await ActivationService._create_membership_from_reward(
                db=db, user_id=user_id, code=code, reward_data=result.reward_data
            )
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise errors.ServerError(msg=f'创建会员权益失败: {str(e)}')

        return result

    @staticmethod
    async def _create_membership_from_reward(
        *, db: AsyncSession, user_id: int, code: str, reward_data: dict
    ) -> None:
        """
        根据激活码权益数据创建会员记录

        reward_data 示例：
        {
            "category": 1,  # 1=题库
            "res_type": "category",  # category=整个分类, single=单个资源
            "res_id": 1,  # 分类ID或题库ID
            "res_name": "公务员考试",
            "duration_days": 365  # 有效天数
        }

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param code: 激活码
        :param reward_data: 权益数据
        """
        # 提取权益参数
        category = reward_data.get('category', 1)
        res_type = reward_data.get('res_type', 'single')
        res_id = reward_data.get('res_id')
        res_name = reward_data.get('res_name')
        duration_days = reward_data.get('duration_days', 365)

        # 计算生效时间和到期时间
        start_time = timezone.now()
        end_time = start_time + timedelta(days=duration_days)

        # 创建会员记录
        membership_param = CreateMembershipParam(
            user_id=user_id,
            category=category,
            res_type=res_type,
            res_id=res_id,
            res_name=res_name,
            method='code',  # 激活码开通
            start_time=start_time,
            end_time=end_time,
        )

        # 保存激活码到会员记录
        await membership_dao.create(db, membership_param)

        # 更新会员表中的 act_code 字段
        # 注意：这需要在 create 后手动更新，因为 CreateMembershipParam 中没有 act_code 字段
        # 这里可以扩展 CreateMembershipParam 或者单独更新


activation_service: ActivationService = ActivationService()
