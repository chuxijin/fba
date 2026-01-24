#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.agiso.schema.webhook import AgisoDeliveryPushData, AgisoPaymentPushData
from backend.plugin.agiso.service.push_log_service import push_log_service
from backend.plugin.agiso.utils.signature import verify_agiso_signature
from backend.plugin.app_auth.crud.crud_order import order_dao
from backend.utils.timezone import timezone


class WebhookService:
    """Webhook 服务"""

    @staticmethod
    async def handle_unified_push(
        json_str: str,
        timestamp: str,
        sign: str,
        platform: str | None = None,
        aopic: int | None = None,
    ) -> dict[str, str]:
        """
        统一处理阿奇索推送，自动识别推送类型

        :param json_str: JSON 字符串
        :param timestamp: 时间戳
        :param sign: 签名
        :param platform: 来源平台
        :param aopic: 推送类型
        :return:
        """
        if not settings.AGISO_APP_SECRET:
            raise errors.ForbiddenError(msg='阿奇索 AppSecret 未配置')

        if not verify_agiso_signature(json_str, timestamp, sign, settings.AGISO_APP_SECRET):
            raise errors.AuthorizationError(msg='签名验证失败')

        try:
            push_data_dict = json.loads(json_str)
        except Exception as e:
            log.error(f'解析推送 JSON 失败: {e}')
            raise errors.RequestError(msg='推送数据格式错误')

        if 'Cards' in push_data_dict and push_data_dict['Cards']:
            log.info(f'识别为发卡推送: {push_data_dict.get("Tid")}')
            return await webhook_service.handle_delivery_push(json_str, timestamp, sign, platform)
        elif 'Payment' in push_data_dict:
            log.info(f'识别为支付推送: {push_data_dict.get("Tid")}, aopic={aopic}')
            return await webhook_service.handle_payment_push(json_str, timestamp, sign, platform)
        else:
            log.warning(f'无法识别推送类型: {json_str}')
            raise errors.RequestError(msg='无法识别推送类型，请检查推送数据格式')

    @staticmethod
    async def handle_payment_push(
        json_str: str,
        timestamp: str,
        sign: str,
        platform: str | None = None,
    ) -> dict[str, str]:
        """
        处理支付推送（内部方法）

        :param json_str: JSON 字符串
        :param timestamp: 时间戳
        :param sign: 签名
        :param platform: 来源平台
        :return:
        """
        try:
            push_data = AgisoPaymentPushData.model_validate_json(json_str)
        except Exception as e:
            log.error(f'解析支付推送数据失败: {e}')
            raise errors.RequestError(msg='支付推送数据格式错误')

        order_no = str(push_data.Tid)
        push_log = await push_log_service.create_log(
            push_type='payment',
            order_no=order_no,
            push_data=json_str,
            platform=platform,
        )

        async with async_db_session.begin() as db:
            try:
                existing_order = await order_dao.get_by_order_no(db, order_no)

                if existing_order:
                    await webhook_service._update_order_payment(db, existing_order, push_data)
                    result = f'更新订单支付状态成功: {order_no}'
                else:
                    await webhook_service._create_order_from_push(db, push_data)
                    result = f'创建订单成功: {order_no}'

                await push_log_service.update_log_success(db, push_log.id, result)
                log.info(f'阿奇索支付推送处理成功: {result}')

                return {'success': 'true', 'message': result}

            except Exception as e:
                log.error(f'处理支付推送失败: {e}')
                await push_log_service.update_log_failed(db, push_log.id, str(e))
                raise

    @staticmethod
    async def _create_order_from_push(db: AsyncSession, push_data: AgisoPaymentPushData) -> None:
        """
        从推送数据创建订单

        :param db: 数据库会话
        :param push_data: 推送数据
        :return:
        """
        order_no = str(push_data.Tid)
        payment_amount = Decimal(push_data.Payment)

        order_data = {
            'order_no': order_no,
            'package_id': 1,
            'total_amount': payment_amount,
            'paid_amount': payment_amount,
            'payment_method': 'agiso',
            'payment_status': 1,
            'order_status': 0,
            'username': push_data.BuyerNick,
            'contact_info': push_data.BuyerOpenUid,
            'remark': f'阿奇索订单推送 - {push_data.Status}',
            'paid_time': timezone.now(),
        }

        await order_dao.create_model(db, order_data)

    @staticmethod
    async def _update_order_payment(
        db: AsyncSession,
        order: AppOrder,
        push_data: AgisoPaymentPushData,
    ) -> None:
        """
        更新订单支付状态

        :param db: 数据库会话
        :param order: 订单对象
        :param push_data: 推送数据
        :return:
        """
        payment_amount = Decimal(push_data.Payment)

        await order_dao.update_model(
            db,
            order.id,
            {
                'paid_amount': payment_amount,
                'payment_status': 1,
                'paid_time': timezone.now(),
            },
        )

    @staticmethod
    async def handle_delivery_push(
        json_str: str,
        timestamp: str,
        sign: str,
        platform: str | None = None,
    ) -> dict[str, str]:
        """
        处理发卡推送（内部方法）

        :param json_str: JSON 字符串
        :param timestamp: 时间戳
        :param sign: 签名
        :param platform: 来源平台
        :return:
        """
        try:
            push_data = AgisoDeliveryPushData.model_validate_json(json_str)
        except Exception as e:
            log.error(f'解析发卡推送数据失败: {e}')
            raise errors.RequestError(msg='发卡推送数据格式错误')

        order_no = str(push_data.Tid)
        push_log = await push_log_service.create_log(
            push_type='delivery',
            order_no=order_no,
            push_data=json_str,
            platform=platform,
        )

        async with async_db_session.begin() as db:
            try:
                cards_info = [
                    {
                        'card_no': card.card_no,
                        'card_pwd': card.card_pwd,
                        'card_value': card.card_value,
                    }
                    for card in push_data.Cards
                ]

                result = f'收到发卡推送: {order_no}, 卡密数量: {len(cards_info)}'
                await push_log_service.update_log_success(db, push_log.id, json.dumps(cards_info, ensure_ascii=False))

                log.info(f'阿奇索发卡推送处理成功: {result}')

                return {'success': 'true', 'message': result, 'cards': cards_info}

            except Exception as e:
                log.error(f'处理发卡推送失败: {e}')
                await push_log_service.update_log_failed(db, push_log.id, str(e))
                raise


webhook_service = WebhookService()
