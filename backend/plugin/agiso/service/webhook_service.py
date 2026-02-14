#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from backend.app.actcode.crud.crud_actcode import actcode_batch_dao, actcode_dao
from backend.app.actcode.model import Actcode
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.agiso.schema.push_log import CreatePushLog
from backend.plugin.agiso.service.push_log_service import push_log_service
from backend.plugin.agiso.utils.signature import verify_agiso_signature

# 阿奇索推送类型常量
AOPIC_PAYMENT = 2097152  # 买家付款
AOPIC_DELIVERY = 2048  # 自动发货成功

# 激活码批次ID
ACTCODE_BATCH_ID = 5  # 公考会员激活批次ID


class WebhookService:
    """Webhook 服务"""

    @staticmethod
    async def handle_push(
        json_str: str,
        timestamp: str,
        sign: str,
        platform: str | None = None,
        aopic: int | None = None,
    ) -> dict[str, str]:
        """
        处理阿奇索推送：验签 → 解析 → 存库

        :param json_str: 推送 JSON 数据
        :param timestamp: 时间戳
        :param sign: 签名
        :param platform: 来源平台(fromPlatform)
        :param aopic: 推送类型(2097152:买家付款 2048:自动发货成功)
        :return:
        """
        # 1. 验签
        if not settings.AGISO_APP_SECRET:
            raise errors.ForbiddenError(msg='阿奇索 AppSecret 未配置')

        if not verify_agiso_signature(json_str, timestamp, sign, settings.AGISO_APP_SECRET):
            raise errors.AuthorizationError(msg='签名验证失败')

        # 2. 解析 JSON
        try:
            data = json.loads(json_str)
        except Exception as e:
            log.error(f'解析推送 JSON 失败: {e}')
            raise errors.RequestError(msg='推送数据格式错误')

        # 3. 提取字段
        order_no = str(data.get('Tid', ''))

        # 4. 去重：同一 order_no + push_type 只保留一条
        existing = await push_log_service.get_by_order_no_and_type(order_no, aopic)
        if existing:
            log.info(f'重复推送已忽略: order_no={order_no}, aopic={aopic}')
            return {'success': 'true', 'message': f'重复推送已忽略: {order_no}'}

        # 5. 存库
        log_obj = CreatePushLog(
            order_no=order_no,
            order_status=data.get('Status', ''),
            buyer_nick=data.get('BuyerNick', ''),
            payment=data.get('Payment', '0'),
            raw_json=json_str,
            platform=platform,
            push_timestamp=timestamp,
            push_type=aopic,
            seller_nick=data.get('SellerNick'),
            seller_id=data.get('SellerOpenUid'),
            buyer_id=data.get('BuyerOpenUid'),
            trade_type=data.get('Type'),
        )

        push_log = await push_log_service.create_log(log_obj)
        log.info(f'阿奇索推送已入库: order_no={order_no}, aopic={aopic}, id={push_log.id}')


        # 4. 根据推送类型处理业务逻辑
        if aopic == AOPIC_PAYMENT:
            # 买家付款推送 —— 仅记录，等待发货成功推送
            log.info(f'收到买家付款推送: order_no={order_no}')
            await push_log_service.update_log_status(
                push_log.id, process_status=1, process_result='付款推送已记录，等待发货推送'
            )
            return {'success': 'true', 'message': f'付款推送已接收: {order_no}'}

        elif aopic == AOPIC_DELIVERY:
            # 自动发货成功推送 —— 写入激活码
            log.info(f'收到自动发货成功推送: order_no={order_no}')
            result = await WebhookService._handle_delivery(order_no, push_log.id)
            return result

        else:
            # 未知推送类型，仅记录
            log.warning(f'未知推送类型: aopic={aopic}, order_no={order_no}')
            await push_log_service.update_log_status(
                push_log.id, process_status=1, process_result=f'未知推送类型({aopic})已记录'
            )
            return {'success': 'true', 'message': f'推送已接收: {order_no}'}

    @staticmethod
    async def _handle_delivery(order_no: str, push_log_id: int) -> dict[str, str]:
        """
        处理发货成功推送：将订单号写入激活码表

        :param order_no: 订单编号（作为激活码使用）
        :param push_log_id: 推送日志ID
        :return:
        """
        try:
            async with async_db_session.begin() as db:
                # 检查激活码是否已存在（去重）
                existing = await actcode_dao.get_by_code(db, order_no)
                if existing:
                    log.info(f'激活码已存在，跳过: {order_no}')
                    await push_log_service.update_log_status(
                        push_log_id, process_status=1, process_result=f'激活码已存在(重复推送): {order_no}'
                    )
                    return {'success': 'true', 'message': f'激活码已存在: {order_no}'}

                # 检查批次是否存在
                batch = await actcode_batch_dao.select_model(db, ACTCODE_BATCH_ID)
                if not batch:
                    raise errors.NotFoundError(msg=f'激活码批次不存在(batch_id={ACTCODE_BATCH_ID})')

                # 创建激活码：code = 订单号
                actcode = Actcode(
                    batch_id=ACTCODE_BATCH_ID,
                    code=order_no,
                )
                db.add(actcode)

                # 批次已使用数量 +1
                await actcode_batch_dao.increment_used_count(db, ACTCODE_BATCH_ID)

            log.info(f'激活码创建成功: {order_no}')
            await push_log_service.update_log_status(
                push_log_id, process_status=1, process_result=f'激活码已创建: {order_no}'
            )
            return {'success': 'true', 'message': f'激活码已创建: {order_no}'}

        except Exception as e:
            log.error(f'处理发货推送失败: {e}')
            await push_log_service.update_log_status(
                push_log_id, process_status=2, process_result=f'处理失败: {str(e)}'
            )
            raise

    # TODO: 付款推送后30秒内若未收到发货推送，需要发出警告
    # 目前尚未确定警告方式（邮件/日志/第三方通知），暂不实现


webhook_service = WebhookService()
