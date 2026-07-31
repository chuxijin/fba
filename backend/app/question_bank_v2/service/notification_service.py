#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题库消息生产者

题库仅作为消息中心的生产者，通过本模块统一向 admin 的消息中心投递站内信。
这里是 question_bank_v2 对 admin 消息中心的唯一耦合点，未来若更换消息后端只需改动此文件。

推送只有一种：错题到了重练时间。录入错题本身不推送 —— 用户刚做完题当场就知道错了，
批量导入更会连发多条；复盘也不推送，它由用户主动发起，没有到期概念。
"""
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model.message import MessageTargetType, MessageType
from backend.app.admin.schema.message import PublishMessageParam
from backend.app.admin.service.message_service import message_service

BIZ_SOURCE = 'question_bank_v2'


class QbankNotificationService:
    """题库站内信生产者"""

    @staticmethod
    async def notify_practice_due(
        *,
        db: AsyncSession,
        user_id: int,
        due_count: int,
        local_date: date,
    ) -> None:
        """
        错题重练到期提醒，由定时任务扫描 ix_qbv2_wrong_push_due 后按用户聚合调用

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param due_count: 到期待重练数量，调用方已按 review_daily_limit 截断
        :param local_date: 用户本地日期，用于同日幂等去重
        """
        await message_service.publish(
            db=db,
            obj=PublishMessageParam(
                title='今日有错题要重练',
                content=f'你有 {due_count} 道错题到达重练时间，及时重做能巩固记忆。',
                target_type=MessageTargetType.USER,
                user_id=user_id,
                message_type=MessageType.PERSONAL,
                biz_source=BIZ_SOURCE,
                # 固定值会导致每次扫描都重发，按用户与本地日期做同日幂等
                biz_id=f'practice_due:{user_id}:{local_date.isoformat()}',
            ),
        )


qbank_notification_service: QbankNotificationService = QbankNotificationService()
