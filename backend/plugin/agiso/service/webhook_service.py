#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from sqlalchemy.exc import IntegrityError

from backend.app.actcode.crud.crud_actcode import actcode_batch_dao, actcode_dao, actcode_usage_dao
from backend.app.actcode.model import Actcode
from backend.app.actcode.service.activate_service import activate_service
from backend.app.membership.service.membership_service import membership_service
from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.agiso.schema.push_log import CreatePushLog
from backend.plugin.agiso.service.push_log_service import push_log_service
from backend.plugin.agiso.utils.signature import verify_agiso_signature
from backend.plugin.notify.service.notify_service import notify_service

# 平台 -> 推送类型映射
PLATFORM_AOPIC: dict[str, dict[str, int]] = {
    'TbAlds': {'payment': 2097152, 'delivery': 2048},
    'AldsXhs': {'payment': 4, 'delivery': 1, 'refund': 16},
}


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
        处理阿奇索推送：验签 → 解析 → 去重 → 存库 → 业务处理

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

        # 3. 根据平台提取字段
        log_obj = WebhookService._extract_fields(data, json_str, platform, timestamp, aopic)
        order_no = log_obj.order_no

        # 4. 去重：同一 order_no + push_type 只保留一条
        existing = await push_log_service.get_by_order_no_and_type(order_no, aopic)
        if existing:
            log.info(f'重复推送已忽略: order_no={order_no}, aopic={aopic}, platform={platform}')
            return {'success': 'true', 'message': f'重复推送已忽略: {order_no}'}

        # 5. 存库（唯一约束兜底并发去重）
        try:
            push_log = await push_log_service.create_log(log_obj)
        except IntegrityError:
            log.info(f'并发重复推送已忽略: order_no={order_no}, aopic={aopic}, platform={platform}')
            return {'success': 'true', 'message': f'重复推送已忽略: {order_no}'}
        log.info(f'阿奇索推送已入库: order_no={order_no}, aopic={aopic}, platform={platform}, id={push_log.id}')

        # 6. 根据平台和推送类型处理业务逻辑
        platform_map = PLATFORM_AOPIC.get(platform or '', {})
        push_action = None
        for action, code in platform_map.items():
            if code == aopic:
                push_action = action
                break

        if push_action == 'payment':
            log.info(f'收到买家付款推送: order_no={order_no}, platform={platform}')
            await push_log_service.update_log_status(
                push_log.id, process_status=1, process_result='付款推送已记录，等待发货推送'
            )
            return {'success': 'true', 'message': f'付款推送已接收: {order_no}'}

        elif push_action == 'delivery':
            log.info(f'收到自动发货成功推送: order_no={order_no}, platform={platform}')
            result = await WebhookService._handle_delivery(order_no, push_log.id, platform, data)
            return result

        elif push_action == 'refund':
            log.info(f'收到退款推送: order_no={order_no}, platform={platform}')
            result = await WebhookService._handle_refund(order_no, push_log.id, platform, data)
            return result

        else:
            log.warning(f'未知推送类型: aopic={aopic}, order_no={order_no}, platform={platform}')
            await push_log_service.update_log_status(
                push_log.id, process_status=1, process_result=f'未知推送类型({aopic})已记录'
            )
            return {'success': 'true', 'message': f'推送已接收: {order_no}'}

    @staticmethod
    def _extract_fields(
        data: dict,
        json_str: str,
        platform: str | None,
        timestamp: str,
        aopic: int | None,
    ) -> CreatePushLog:
        """
        根据平台类型提取字段

        :param data: 解析后的 JSON 数据
        :param json_str: 原始 JSON 字符串
        :param platform: 来源平台
        :param timestamp: 推送时间戳
        :param aopic: 推送类型
        :return: CreatePushLog 对象
        """
        if platform == 'AldsXhs':
            return WebhookService._extract_xhs(data, json_str, platform, timestamp, aopic)
        else:
            # 淘宝(TbAlds)及其他平台，使用原有解析逻辑
            return WebhookService._extract_taobao(data, json_str, platform, timestamp, aopic)

    @staticmethod
    def _extract_taobao(
        data: dict,
        json_str: str,
        platform: str | None,
        timestamp: str,
        aopic: int | None,
    ) -> CreatePushLog:
        """淘宝平台(TbAlds)字段提取"""
        return CreatePushLog(
            order_no=str(data.get('Tid', '')),
            raw_json=json_str,
            order_status=data.get('Status'),
            buyer_nick=data.get('BuyerNick'),
            payment=data.get('Payment'),
            platform=platform,
            push_timestamp=timestamp,
            push_type=aopic,
            seller_nick=data.get('SellerNick'),
            seller_id=data.get('SellerOpenUid'),
            buyer_id=data.get('BuyerOpenUid'),
            trade_type=data.get('Type'),
        )

    @staticmethod
    def _extract_xhs(
        data: dict,
        json_str: str,
        platform: str | None,
        timestamp: str,
        aopic: int | None,
    ) -> CreatePushLog:
        """
        小红书平台(AldsXhs)字段提取

        买家付款 JSON:
          {"sellerId": "...", "orderId": "P786...", "orderStatus": 4, "updateTime": 1771086554138}

        发货成功 JSON:
          {"Tid": "P786...", "PlatformShopId": "...", "AldsType": 1, "Status": "4",
           "Orders": [{"GoodsName": "...", "SpecName": "...", ...}]}
        """
        # 付款推送用 orderId，发货推送用 Tid
        order_no = str(data.get('orderId') or data.get('Tid', ''))
        order_status = str(data.get('orderStatus') or data.get('Status', ''))
        seller_id = data.get('sellerId') or data.get('PlatformShopId')

        # 从 Orders 数组里提取商品信息（发货推送才有）
        goods_name = None
        spec_name = None
        orders = data.get('Orders', [])
        if orders and len(orders) > 0:
            first_order = orders[0]
            goods_name = first_order.get('GoodsName')
            spec_name = first_order.get('SpecName')

        return CreatePushLog(
            order_no=order_no,
            raw_json=json_str,
            order_status=order_status,
            platform=platform,
            push_timestamp=timestamp,
            push_type=aopic,
            seller_id=str(seller_id) if seller_id else None,
            goods_name=goods_name,
            spec_name=spec_name,
        )

    @staticmethod
    async def _handle_delivery(
        order_no: str,
        push_log_id: int,
        platform: str | None,
        data: dict,
    ) -> dict[str, str]:
        """
        处理发货成功推送：匹配批次规则后将订单号写入激活码表

        :param order_no: 订单编号（作为激活码使用）
        :param push_log_id: 推送日志ID
        :param platform: 来源平台
        :param data: 解析后的 JSON 数据
        :return:
        """
        try:
            # 从推送数据中提取商品信息
            goods_name = None
            spec_name = None
            orders = data.get('Orders', [])
            if orders:
                first_order = orders[0]
                goods_name = first_order.get('GoodsName')
                spec_name = first_order.get('SpecName')

            # 根据平台和商品信息匹配批次
            batch_id = WebhookService._resolve_batch_id(platform, goods_name, spec_name)
            if batch_id is None:
                msg = f'未匹配到激活批次: platform={platform}, goods_name={goods_name}, spec_name={spec_name}'
                log.warning(msg)
                await push_log_service.update_log_status(push_log_id, process_status=1, process_result=msg)
                return {'success': 'true', 'message': f'发货推送已记录(无匹配批次): {order_no}'}

            over_capacity = False
            batch_snapshot: dict[str, int | str] = {}

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
                batch = await actcode_batch_dao.select_model(db, batch_id)
                if not batch:
                    raise errors.NotFoundError(msg=f'激活码批次不存在(batch_id={batch_id})')

                # 容量软告警预检：total_count>0 且已用 >= 上限时仅记录，不阻断写入
                if batch.total_count > 0 and batch.used_count >= batch.total_count:
                    over_capacity = True
                    batch_snapshot = {
                        'batch_id': batch.id,
                        'batch_name': batch.name,
                        'used_count': batch.used_count,
                        'total_count': batch.total_count,
                    }

                # 创建激活码：code = 订单号
                actcode = Actcode(
                    batch_id=batch_id,
                    code=order_no,
                )
                db.add(actcode)

                # 批次已使用数量 +1
                await actcode_batch_dao.increment_used_count(db, batch_id)

            log.info(f'激活码创建成功: {order_no}, batch_id={batch_id}, platform={platform}')
            result_msg = f'激活码已创建: {order_no}, batch_id={batch_id}'

            if over_capacity:
                log.warning(
                    f'激活码批次已超额仍写入: batch_id={batch_snapshot["batch_id"]}, '
                    f'used={batch_snapshot["used_count"]}, total={batch_snapshot["total_count"]}, order_no={order_no}'
                )
                await notify_service.send(
                    title='激活码批次已超额',
                    content=(
                        f'批次ID: {batch_snapshot["batch_id"]}\n'
                        f'批次名称: {batch_snapshot["batch_name"]}\n'
                        f'已用数量: {batch_snapshot["used_count"]}\n'
                        f'总数上限: {batch_snapshot["total_count"]}\n'
                        f'本次订单仍已写入: {order_no}\n'
                        f'建议运营尽快扩容 total_count 或下架活动'
                    ),
                    options={'tags': '阿奇索|批次超额'},
                    source='agiso_webhook',
                )
                result_msg = f'{result_msg}; 批次已超额, 已发告警'

            await push_log_service.update_log_status(
                push_log_id, process_status=1, process_result=result_msg
            )
            return {'success': 'true', 'message': f'激活码已创建: {order_no}'}

        except Exception as e:
            log.error(f'处理发货推送失败: {e}')
            await push_log_service.update_log_status(
                push_log_id, process_status=2, process_result=f'处理失败: {str(e)}'
            )
            await notify_service.send(
                title='阿奇索发货处理失败',
                content=f'订单号: {order_no}\n平台: {platform}\n错误: {str(e)}',
                options={'tags': '阿奇索|发货失败'},
                source='agiso_webhook',
            )
            raise

    @staticmethod
    async def _handle_refund(
        order_no: str,
        push_log_id: int,
        platform: str | None,
        data: dict,
    ) -> dict[str, str]:
        """
        处理退款推送：未使用激活码直接删除；已使用激活码反向回收会员时长

        :param order_no: 订单编号
        :param push_log_id: 推送日志ID
        :param platform: 来源平台
        :param data: 解析后的 JSON 数据
        :return:
        """
        try:
            outcome: str = ''
            outcome_msg: str = ''
            need_alert: bool = False
            alert_payload: dict[str, str] = {}

            async with async_db_session.begin() as db:
                actcode = await actcode_dao.get_by_code(db, order_no)
                if not actcode:
                    outcome = 'no_code'
                    outcome_msg = f'退款订单无对应激活码: {order_no}'
                elif actcode.status != 1:
                    # 未使用，直接删除
                    await actcode_dao.delete_model(db, actcode.id)
                    outcome = 'deleted'
                    outcome_msg = f'退款激活码已删除: {order_no}'
                else:
                    # 已使用，定位绑定用户后反向回收
                    usage = await actcode_usage_dao.get_by_code_id(db, actcode.id)
                    if not usage:
                        outcome = 'revoke_failed'
                        outcome_msg = f'激活码标记已使用但无使用记录: {order_no}, actcode_id={actcode.id}'
                        need_alert = True
                    else:
                        try:
                            user_id = int(usage.user_id)
                        except (TypeError, ValueError):
                            outcome = 'revoke_failed'
                            outcome_msg = (
                                f'退款订单激活码绑定 user_id 异常: {order_no}, user_id={usage.user_id}'
                            )
                            need_alert = True
                        else:
                            revoked = await membership_service.revoke_by_source_key(
                                db,
                                user_id=user_id,
                                source=activate_service.ORDER_SOURCE,
                                original_source_key=activate_service._build_source_key(order_no),
                                revoke_source_key=activate_service._build_refund_source_key(order_no),
                                source_detail=f'refund order_no={order_no}',
                                remark='退款撤销',
                            )
                            if revoked is None:
                                outcome = 'revoke_failed'
                                outcome_msg = (
                                    f'未定位到原发放流水，无法撤销会员: {order_no}, user_id={user_id}'
                                )
                                need_alert = True
                                alert_payload = {'user_id': str(user_id)}
                            else:
                                outcome = 'revoked'
                                outcome_msg = (
                                    f'退款已撤销会员: {order_no}, user_id={user_id}, '
                                    f'new_valid_to={revoked.valid_to}, status={revoked.status}'
                                )

            if outcome == 'no_code':
                log.info(outcome_msg)
            elif outcome == 'revoke_failed':
                log.warning(outcome_msg)
            else:
                log.info(outcome_msg)

            await push_log_service.update_log_status(push_log_id, process_status=1, process_result=outcome_msg)

            if need_alert:
                await notify_service.send(
                    title='退款撤销会员失败',
                    content=(
                        f'订单号: {order_no}\n'
                        f'平台: {platform}\n'
                        f'用户ID: {alert_payload.get("user_id", "未知")}\n'
                        f'原因: {outcome_msg}\n'
                        f'需人工处理'
                    ),
                    options={'tags': '阿奇索|退款告警'},
                    source='agiso_webhook',
                )

            return {'success': 'true', 'message': outcome_msg}

        except Exception as e:
            log.error(f'处理退款推送失败: {e}')
            await push_log_service.update_log_status(
                push_log_id, process_status=2, process_result=f'处理失败: {str(e)}'
            )
            await notify_service.send(
                title='阿奇索退款处理失败',
                content=f'订单号: {order_no}\n平台: {platform}\n错误: {str(e)}',
                options={'tags': '阿奇索|退款失败'},
                source='agiso_webhook',
            )
            raise

    @staticmethod
    def _resolve_batch_id(platform: str | None, goods_name: str | None, spec_name: str | None) -> int | None:
        """
        根据平台和商品信息匹配激活码批次 ID

        按 AGISO_BATCH_RULES 规则列表顺序匹配，keyword 在 goods_name 或 spec_name 中出现即命中，
        无匹配返回 None

        :param platform: 来源平台
        :param goods_name: 商品名称
        :param spec_name: 规格名称
        :return:
        """
        search_text = f'{goods_name or ""} {spec_name or ""}'
        for rule in settings.AGISO_BATCH_RULES:
            rule_platform = rule.get('platform')
            keyword = rule.get('keyword')
            batch_id = rule.get('batch_id')
            if not rule_platform or not keyword or batch_id is None:
                continue
            if platform != rule_platform:
                continue
            if keyword in search_text:
                log.info(f'批次匹配命中: platform={platform}, keyword={keyword}, batch_id={batch_id}')
                return batch_id
        return None

    # TODO: 付款推送后30秒内若未收到发货推送，需要发出警告


webhook_service = WebhookService()
