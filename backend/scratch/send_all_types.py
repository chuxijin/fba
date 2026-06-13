#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import sys

# 将项目根目录添加到 python path 中，以便正确导入
sys.path.insert(0, "d:\\100_Work\\101_Program\\Proj\\fba")

from backend.plugin.notify.utils.channels import send_wecom_app
from backend.database.redis import redis_client


async def main() -> None:
    """ 综合测试发送不同类型的企业微信自建应用消息 """
    print("正在连接 Redis...")
    await redis_client.init()

    # 清除 token 缓存以防密钥未更新
    token_cache_key = 'fba:notify:wecom_app:access_token'
    await redis_client.delete(token_cache_key)

    # 1. 发送【Markdown 消息】
    print("\n-------------------------------------------")
    print("1. 正在发送: [Markdown 消息]...")
    markdown_content = (
        "### 📢 系统运行状态报告\n"
        "> 报告时间：<font color=\"comment\">2026-06-14 00:30:00</font>\n\n"
        "**服务组件状态：**\n"
        "- 数据库连接：<font color=\"info\">🟢 正常 (Normal)</font>\n"
        "- Redis 缓存：<font color=\"info\">🟢 正常 (Normal)</font>\n"
        "- 异步队列 (Celery)：<font color=\"warning\">🟡 队列积压 12 条</font>\n\n"
        "👉 [点击这里进入后台管理系统](https://admin.yzxj.vip)"
    )
    success, error = await send_wecom_app(
        title="系统监控月报",
        content=markdown_content,
        options={"msgtype": "markdown"}
    )
    print(f"发送结果: {'SUCCESS' if success else 'FAILED'}")
    if not success:
        print(f"错误信息: {error}")

    # 2. 发送【TextCard 文本卡片消息】
    print("\n-------------------------------------------")
    print("2. 正在发送: [TextCard 文本卡片]...")
    textcard_content = (
        "订单单号：ORD20260614001\n"
        "申请产品：超级考研尊享版专业课\n"
        "申请人：王小二 (手机 195xxxx1060)\n"
        "申请时间：2026-06-14 00:28\n\n"
        "请及时处理该笔开通申请。"
    )
    success, error = await send_wecom_app(
        title="🔔 待处理开通审批",
        content=textcard_content,
        options={
            "msgtype": "textcard",
            "url": "https://admin.yzxj.vip/api/v1/notify/send", # 详情跳转 URL
            "btntxt": "立即处理"
        }
    )
    print(f"发送结果: {'SUCCESS' if success else 'FAILED'}")
    if not success:
        print(f"错误信息: {error}")

    # 3. 发送【Text 纯文本消息】
    print("\n-------------------------------------------")
    print("3. 正在发送: [Text 纯文本]...")
    success, error = await send_wecom_app(
        title="监控警告",
        content="温馨提示：后台服务器 CPU 使用率已达到 82%，请注意检查系统负载。",
        options={"msgtype": "text"}
    )
    print(f"发送结果: {'SUCCESS' if success else 'FAILED'}")
    if not success:
        print(f"错误信息: {error}")

    # 4. 发送【TemplateCard 按钮交互卡片】(该类型可能由于未配置回调 url 报错 43012)
    print("\n-------------------------------------------")
    print("4. 正在发送: [TemplateCard 按钮交互卡片]...")
    template_card_config = {
        "card_type": "button_interaction",
        "source": {
            "desc": "有岸上系统通知",
            "desc_color": 1
        },
        "main_title": {
            "title": "待审批：新用户开通申请",
            "desc": "用户申请开通超级考研课程"
        },
        "sub_title_text": "申请人: 张三\n申请课程: 超级考研专业课",
        "button_list": [
            {
                "text": "同意开通",
                "style": 1,
                "key": "accept"
            },
            {
                "text": "拒绝开通",
                "style": 2,
                "key": "reject"
            }
        ],
        "task_id": "task_id_course_approve_9999"
    }
    success, error = await send_wecom_app(
        title="有岸上审批通知",
        content="收到一条新的审批申请",
        options={
            "msgtype": "template_card",
            "template_card": template_card_config
        }
    )
    print(f"发送结果: {'SUCCESS' if success else 'FAILED'}")
    if not success:
        print(f"提示说明: 按钮卡片发送失败是符合预期的，报错通常为 'require agent with callback url'，表示自建应用必须要先在微信后台成功配置保存回调 URL 后才能使用本功能。")
        print(f"实际返回报错信息: {error}")

    await redis_client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
