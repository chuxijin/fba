#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import sys

# 将项目根目录添加到 python path 中，以便正确导入
sys.path.insert(0, 'd:\\100_Work\\101_Program\\Proj\\fba')

from backend.core.conf import settings
from backend.plugin.notify.utils.channels import send_wecom_app
from backend.database.redis import redis_client


async def main() -> None:
    print('正在连接 Redis...')
    await redis_client.init()

    # 清除 Redis 缓存的 token 确保全新获取
    token_cache_key = 'fba:notify:wecom_app:access_token'
    await redis_client.delete(token_cache_key)

    print('\n【准备发送交互模板卡片消息】')

    template_card_config = {
        'card_type': 'button_interaction',
        'source': {'desc': '有岸上系统通知', 'desc_color': 1},
        'main_title': {'title': '待审批：新用户开通申请', 'desc': '用户申请开通超级考研课程'},
        'sub_title_text': '申请人: 张三\n申请课程: 超级考研专业课',
        'button_list': [
            {'text': '同意开通', 'style': 1, 'key': 'accept'},
            {'text': '拒绝开通', 'style': 2, 'key': 'reject'},
        ],
        'task_id': 'task_id_course_approve_9999',
    }

    success, error = await send_wecom_app(
        title='有岸上审批通知',
        content='收到一条新的审批申请',
        options={'msgtype': 'template_card', 'template_card': template_card_config},
    )

    print('\n【发送结果】:')
    if success:
        print('发送状态: SUCCESS (交互卡片发送成功！请查看您的企业微信/微信消息)')
    else:
        print(f'发送状态: FAILED (发送失败)')
        print(f'错误信息: {error}')

    await redis_client.aclose()


if __name__ == '__main__':
    asyncio.run(main())
