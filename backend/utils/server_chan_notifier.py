#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Literal

import httpx

from backend.common.log import log
from backend.core.conf import settings


class ServerChanNotifier:
    """
    Server Chan 通知工具

    这是一个用于发送 Server Chan 通知消息的工具类。
    它封装了与 Server Chan API 的交互，支持发送带有标题和内容的通知，
    并且可以配置额外的参数，如消息卡片内容、是否隐藏调用 IP 和指定消息通道。
    通知服务的 SendKey 需要在 backend/core/conf.py 中的 SERVER_CHAN_SEND_KEY 配置。
    """

    def __init__(self):
        """
        初始化 ServerChanNotifier 实例。

        从全局配置中获取 Server Chan 的 SendKey，并构建 API 请求 URL。
        """
        self.send_key = settings.SERVER_CHAN_SEND_KEY
        self.api_url = f'https://sctapi.ftqq.com/{self.send_key}.send'

    async def send_message(
        self,
        title: str,
        desp: str,
        short: str | None = None,
        noip: Literal[0, 1] | None = None,
        channel: str | None = None,
    ) -> bool:
        """发送 Server Chan 通知消息。

        此方法异步调用 Server Chan API，发送通知到绑定的渠道。
        消息标题和内容支持 Markdown 格式，并可选择性地配置消息卡片、IP 隐藏和指定通道。

        :param title: 消息标题，必填。最大长度为 32 个字符。
        :param desp: 消息内容，选填。支持 Markdown 语法，最大长度为 32KB。消息卡片将截取前 30 个字符显示。
        :param short: 消息卡片内容，选填。最大长度 64 个字符。如果未指定，将自动从 `desp` 参数中截取生成。
        :param noip: 是否隐藏调用 IP，选填。默认不隐藏。设置为 1 则隐藏发送请求的 IP 地址。
        :param channel: 动态指定本次推送使用的消息通道，选填。例如，同时发送到服务号和企业微信应用消息通道，可使用 "9|66"。支持最多两个通道，多个通道值用竖线 | 隔开。
                      通道对应的值（部分示例）：
                      - 官方Android版·β: 98
                      - 企业微信应用消息: 66
                      - 企业微信群机器人: 1
                      - 钉钉群机器人: 2
                      - 飞书群机器人: 3
                      - Bark iOS: 8
                      - 测试号: 0
                      - 自定义: 88
                      - PushDeer: 18
                      - 方糖服务号: 9
        :return: 布尔值，表示通知是否发送成功。如果 SendKey 未配置或发生网络错误/API 错误，则返回 False。
        """
        if not self.send_key:
            log.error(
                'Server Chan send key 未配置，无法发送通知。请在 `backend/core/conf.py` 中配置 `SERVER_CHAN_SEND_KEY`。'
            )
            return False

        payload = {'title': title, 'desp': desp}
        if short is not None:
            payload['short'] = short
        if noip is not None:
            payload['noip'] = noip
        if channel is not None:
            payload['channel'] = channel

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.api_url, data=payload)
                response.raise_for_status()  # Raises HTTPStatusError for bad responses (4xx or 5xx)
                result = response.json()
                if result.get('code') == 0:
                    log.info(f'Server Chan 通知发送成功: {title}')
                    return True
                else:
                    log.error(f'Server Chan 通知发送失败: {result.get("message")}, 响应: {response.text}')
                    return False
        except httpx.RequestError as exc:
            log.error(f'请求 Server Chan API 失败: {exc}')
            return False
        except httpx.HTTPStatusError as exc:
            log.error(f'请求 Server Chan API 失败，状态码: {exc.response.status_code}, 响应: {exc.response.text}')
            return False
        except Exception as exc:
            log.error(f'发送 Server Chan 通知时发生未知错误: {exc}')
            return False


server_chan_notifier = ServerChanNotifier()


if __name__ == '__main__':
    # 这是一个使用 Server Chan 通知工具的示例。
    # 在运行此示例之前，请确保已在 backend/core/conf.py 中配置 SERVER_CHAN_SEND_KEY。

    import asyncio
    import sys

    from pathlib import Path

    # 确保项目根目录在 sys.path 中，以便可以导入 backend 模块
    # 假设此文件位于 project_root/backend/utils/
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # 打印 SERVER_CHAN_SEND_KEY，用于调试
    print(f'DEBUG: SERVER_CHAN_SEND_KEY: {settings.SERVER_CHAN_SEND_KEY}')

    async def main():
        print('--- Server Chan 通知工具示例 ---')

        # 示例 1: 仅发送标题和内容
        print('\n--- 示例 1: 仅发送标题和内容 ---')
        success1 = await server_chan_notifier.send_message(
            title='测试通知',
            desp='这是一条来自 FastAPI Best Architecture 的**测试通知**。\n\n支持 **Markdown** 格式。\n- 列表项 1\n- 列表项 2',
        )
        print(f'示例 1 发送结果: {success1}')

        # 示例 2: 发送标题、内容和消息卡片
        print('\n--- 示例 2: 发送标题、内容和消息卡片 ---')
        success2 = await server_chan_notifier.send_message(
            title='重要提醒', desp='请注意，您的系统检测到异常活动！', short='系统异常'
        )
        print(f'示例 2 发送结果: {success2}')

        # 示例 3: 隐藏 IP 并指定通道
        print('\n--- 示例 3: 隐藏 IP 并指定通道 (发送到企业微信应用消息和方糖服务号) ---')
        success3 = await server_chan_notifier.send_message(
            title='系统维护',
            desp='系统将在今晚 0:00 进行维护，预计持续 1 小时。',
            noip=1,  # 隐藏 IP
            channel='66|9',  # 发送到企业微信应用消息和方糖服务号
        )
        print(f'示例 3 发送结果: {success3}')

        # 示例 4: 缺少 SendKey 的情况 (会记录错误日志)
        print('\n--- 示例 4: 缺少 SendKey 的情况 ---')
        # 暂时修改 SendKey 为空以模拟错误情况
        # original_send_key = settings.SERVER_CHAN_SEND_KEY # 注释掉这行
        settings.SERVER_CHAN_SEND_KEY = ''  # 注释掉这行
        success4 = await server_chan_notifier.send_message(
            title='错误测试', desp='这个通知应该会因为缺少 SendKey 而失败。'
        )
        # settings.SERVER_CHAN_SEND_KEY = original_send_key # 注释掉这行
        print(f'示例 4 发送结果: {success4}')

    asyncio.run(main())
