#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
B 站账号管理器 - 主入口
支持桌面端和移动端
"""
import flet as ft

from my_app.services.api.backend_api import backend_api_service
from my_app.ui.home import HomePage


async def on_page_close(e):
    """
    页面关闭事件处理

    :param e: 事件对象
    """
    # 关闭 HTTP 客户端
    try:
        await backend_api_service.close()
    except Exception:
        pass  # 忽略关闭时的异常


def main(page: ft.Page):
    """
    应用主函数

    :param page: Flet 页面对象
    :return:
    """
    # 页面配置
    page.title = "B 站账号管理器"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    page.on_close = on_page_close  # 注册关闭事件
    page.on_disconnect = on_page_close  # 注册断开连接事件

    # 窗口配置（仅桌面端生效）
    page.window.width = 1400
    page.window.height = 900
    page.window.min_width = 1200
    page.window.min_height = 700

    # 主题配置
    page.theme = ft.Theme(
        color_scheme_seed="blue",
    )

    # 加载首页
    home_page = HomePage(page)
    page.add(home_page.build())
    page.update()


if __name__ == '__main__':
    # 运行应用
    ft.app(target=main)
