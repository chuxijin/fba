#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from backend.common.log import log
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.notify.crud.crud_notify_log import notify_log_dao
from backend.plugin.notify.schema.notify import CreateNotifyLog, GetNotifyLogDetail, NotifySendResult
from backend.plugin.notify.utils.channels import CHANNEL_ENABLED_MAP, CHANNEL_HANDLERS


class NotifyService:
    """多渠道通知服务"""

    @staticmethod
    async def send(
        *,
        title: str,
        content: str,
        channels: list[str] | None = None,
        options: dict[str, str] | None = None,
        source: str = 'internal',
    ) -> NotifySendResult:
        """
        按优先级发送通知，首个成功即停止

        :param title: 通知标题
        :param content: 通知内容
        :param channels: 指定渠道列表(为空则使用默认优先级)
        :param options: 渠道扩展参数(如 Server 酱 tags)
        :param source: 触发来源
        :return:
        """
        # 确定渠道顺序，过滤已启用的
        channel_order = channels or settings.NOTIFY_CHANNEL_PRIORITY
        enabled_channels = [
            ch
            for ch in channel_order
            if ch in CHANNEL_HANDLERS and getattr(settings, CHANNEL_ENABLED_MAP.get(ch, ''), False)
        ]

        if not enabled_channels:
            log.warning('没有可用的通知渠道')

        # 依次尝试渠道
        attempts: list[dict] = []
        success_channel: str | None = None

        for channel_name in enabled_channels:
            handler = CHANNEL_HANDLERS[channel_name]
            try:
                success, error = await handler(title=title, content=content, options=options)
            except Exception as e:
                success, error = False, str(e)

            attempts.append({
                'channel': channel_name,
                'success': success,
                'error': error,
            })

            if success:
                success_channel = channel_name
                break

        # 构建日志
        final_status = 1 if success_channel else 2
        last_error = attempts[-1]['error'] if attempts and not success_channel else None

        log_obj = CreateNotifyLog(
            title=title[: settings.NOTIFY_MAX_TITLE_LENGTH],
            content=content,
            channel=success_channel,
            status=final_status,
            attempts=json.dumps(attempts, ensure_ascii=False),
            error_msg=last_error,
            source=source,
        )

        # 写入数据库
        async with async_db_session.begin() as db:
            created = await notify_log_dao.create_model(db, log_obj)
            await db.flush()
            log_detail = GetNotifyLogDetail.model_validate(created)

        if success_channel:
            log.info(f'通知发送成功: title={title}, channel={success_channel}')
        else:
            log.error(f'通知发送失败(所有渠道): title={title}, attempts={len(attempts)}')

        return NotifySendResult(
            success=success_channel is not None,
            channel=success_channel,
            log_id=log_detail.id,
        )


notify_service = NotifyService()
