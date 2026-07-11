#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import string

from decimal import Decimal
from typing import Any

import httpx

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import CommonStatus
from backend.app.access.crud.crud_template import subscription_template_dao
from backend.app.access.model.template import SubscriptionTemplate
from backend.app.payment.crud.crud_pay_order import pay_order_dao
from backend.app.payment.schema.pay import (
    CreatePrepayParam,
    PaymentConfirmResult,
    SubscriptionPaymentConfirmParam,
    SubscriptionPrepayParam,
    SubscriptionPrepayResult,
)
from backend.app.payment.service.pay_service import pay_service
from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.oauth2.crud.crud_user_social import user_social_dao
from backend.plugin.oauth2.enums import UserSocialType
from backend.utils.timezone import timezone


class PayOrderService:
    """支付业务订单服务"""

    @staticmethod
    def _generate_order_no() -> str:
        """生成业务订单号"""
        now = timezone.now()
        timestamp = now.strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices(string.digits, k=6))
        return f'PO{timestamp}{random_suffix}'

    @staticmethod
    async def _exchange_wx_code(wx_code: str) -> dict[str, Any]:
        """
        通过微信 code 换取支付所需会话信息

        :param wx_code: 微信小程序登录 code
        :return:
        """
        appid = getattr(settings, 'WX_MINIAPP_APPID', '')
        secret = getattr(settings, 'WX_MINIAPP_SECRET', '')
        if not appid or not secret:
            raise errors.ServerError(msg='微信小程序配置缺失')

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                'https://api.weixin.qq.com/sns/jscode2session',
                params={
                    'appid': appid,
                    'secret': secret,
                    'js_code': wx_code,
                    'grant_type': 'authorization_code',
                },
            )
        data = response.json()
        if data.get('errcode'):
            raise errors.AuthorizationError(msg=f'微信会话获取失败: {data.get("errmsg", "未知错误")}')
        return data

    @staticmethod
    async def _resolve_miniapp_session(db: AsyncSession, *, user_id: int, wx_code: str) -> tuple[str, str]:
        """
        获取并校验当前用户的小程序支付会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param wx_code: 微信小程序登录 code
        :return:
        """
        wx_data = await PayOrderService._exchange_wx_code(wx_code)
        openid = wx_data.get('openid')
        session_key = wx_data.get('session_key')
        if not openid or not session_key:
            raise errors.AuthorizationError(msg='微信会话缺少 openid 或 session_key')

        social = await user_social_dao.get_by_openid(db, openid, UserSocialType.wechat_miniapp.value)
        if not social or social.user_id != user_id:
            raise errors.ForbiddenError(msg='微信支付身份与当前登录用户不一致')

        return openid, session_key

    @staticmethod
    def _ensure_template_saleable(template: SubscriptionTemplate) -> None:
        """
        校验订阅模板可购买

        :param template: 订阅模板
        :return:
        """
        if template.status != CommonStatus.ACTIVE:
            raise errors.ForbiddenError(msg='该套餐暂不可购买')
        if int(template.price_cents or 0) <= 0:
            raise errors.ForbiddenError(msg='该套餐暂不支持在线支付')

        sale_period = template.sale_period
        if sale_period is None:
            return

        now = timezone.now()
        if sale_period.lower is not None and now < sale_period.lower:
            raise errors.ForbiddenError(msg='该套餐尚未开售')
        if sale_period.upper is not None and now >= sale_period.upper:
            raise errors.ForbiddenError(msg='该套餐已结束售卖')

    @staticmethod
    async def create_subscription_prepay(
        *, db: AsyncSession, user_id: int, obj: SubscriptionPrepayParam
    ) -> SubscriptionPrepayResult:
        """
        创建订阅套餐虚拟支付预下单

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 预下单参数
        :return:
        """
        template = await subscription_template_dao.get_by_code(db, obj.template_code)
        if not template:
            raise errors.NotFoundError(msg='订阅套餐不存在')
        PayOrderService._ensure_template_saleable(template)
        product_id = str((template.metadata_ or {}).get('virtual_product_id') or template.code)

        openid, session_key = await PayOrderService._resolve_miniapp_session(
            db,
            user_id=user_id,
            wx_code=obj.wx_code,
        )

        amount = Decimal(int(template.price_cents)) / Decimal(100)
        order_no = PayOrderService._generate_order_no()
        order = await pay_order_dao.create_from_dict(
            db,
            {
                'order_no': order_no,
                'user_id': user_id,
                'biz_type': 'subscription_template',
                'item_code': template.code,
                'item_name': template.name,
                'amount': amount,
                'pay_type': obj.pay_type,
                'status': 'pending',
                'fulfill_status': 'pending',
                'extra_data': {
                    'template_id': template.id,
                    'duration_days': template.duration_days,
                    'price_cents': template.price_cents,
                    'virtual_product_id': product_id,
                    'env': obj.env,
                    'openid': openid,
                },
                'created_by': user_id,
            },
        )

        prepay = await pay_service.create_prepay(
            db=db,
            params=CreatePrepayParam(
                order_no=order.order_no,
                biz_type=order.biz_type,
                pay_type=obj.pay_type,
                amount=order.amount,
                product_name=order.item_name,
                user_id=user_id,
                openid=openid,
                session_key=session_key,
                product_id=product_id,
                env=obj.env,
            ),
        )
        await pay_order_dao.update_model(db, order.id, {'transaction_no': prepay.transaction_no})

        return SubscriptionPrepayResult(
            order_no=order.order_no,
            transaction_no=prepay.transaction_no,
            pay_params=prepay.pay_params,
        )

    @staticmethod
    async def confirm_subscription_payment(
        *, db: AsyncSession, user_id: int, obj: SubscriptionPaymentConfirmParam
    ) -> PaymentConfirmResult:
        """
        确认订阅支付状态并发放权益

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 支付确认参数
        :return:
        """
        order = await pay_order_dao.get_by_order_no(db, obj.order_no)
        if not order:
            raise errors.NotFoundError(msg='支付订单不存在')
        if order.user_id != user_id:
            raise errors.ForbiddenError(msg='无权确认该支付订单')
        if order.biz_type != 'subscription_template':
            raise errors.ForbiddenError(msg='该订单不是订阅订单')

        openid = str((order.extra_data or {}).get('openid') or '')
        if not openid and obj.wx_code:
            openid, _ = await PayOrderService._resolve_miniapp_session(
                db,
                user_id=user_id,
                wx_code=obj.wx_code,
            )
            await pay_order_dao.update_model(
                db,
                order.id,
                {
                    'extra_data': {
                        **(order.extra_data or {}),
                        'openid': openid,
                    },
                },
            )

        result = await pay_service.sync_payment_status(
            db=db,
            order_no=obj.order_no,
            user_id=user_id,
            openid=openid or None,
        )
        return PaymentConfirmResult(**result)


pay_order_service: PayOrderService = PayOrderService()
