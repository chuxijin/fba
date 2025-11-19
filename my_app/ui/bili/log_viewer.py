#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""日志查看器组件"""
import asyncio
import httpx
import flet as ft


class LogViewerTab:
    """日志查看器 Tab"""

    def __init__(self, page: ft.Page):
        """
        初始化日志查看器 Tab

        :param page: Flet 页面对象
        """
        self.page = page
        self.log_lines = []
        self.max_lines = 500  # 最多保留500行日志
        self.auto_scroll = True
        self.is_running = False

        # 日志显示区域
        self.log_text = ft.TextField(
            value='',
            multiline=True,
            read_only=True,
            min_lines=20,
            max_lines=None,
            expand=True,
            border_color='#9e9e9e',
            text_style=ft.TextStyle(
                font_family='Consolas',
                size=12,
            ),
        )

        # 自动滚动开关
        self.auto_scroll_switch = ft.Switch(
            label='自动滚动',
            value=True,
            on_change=self._toggle_auto_scroll,
        )

        # 清空日志按钮
        self.clear_button = ft.ElevatedButton(
            '清空日志',
            icon=ft.Icons.DELETE_SWEEP,
            on_click=self._clear_logs,
        )

    def build(self) -> ft.Container:
        """
        构建日志查看器 UI

        :return: 日志查看器容器
        """
        return ft.Container(
            content=ft.Column([
                # 工具栏
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ARTICLE, size=24),
                        ft.Text('实时日志', size=18, weight=ft.FontWeight.BOLD),
                        ft.Container(expand=True),
                        self.auto_scroll_switch,
                        self.clear_button,
                    ]),
                    padding=ft.padding.only(left=10, right=10, top=10, bottom=10),
                ),
                ft.Divider(height=1),
                # 日志显示区域
                ft.Container(
                    content=self.log_text,
                    padding=10,
                    expand=True,
                ),
            ], spacing=0, expand=True),
            expand=True,
        )

    async def start_log_stream(self):
        """启动日志流（从后端获取日志）"""
        if self.is_running:
            return

        self.is_running = True
        base_url = 'http://127.0.0.1:8000'

        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream('GET', f'{base_url}/api/v1/logs/system/stream') as response:
                    if response.status_code != 200:
                        self._add_log_line(f'[ERROR] 无法连接到日志流: HTTP {response.status_code}')
                        return

                    async for line in response.aiter_lines():
                        if not self.is_running:
                            break

                        if line.strip():
                            self._add_log_line(line)
                            await asyncio.sleep(0.01)  # 防止UI阻塞
        except Exception as e:
            self._add_log_line(f'[ERROR] 日志流异常: {str(e)}')
        finally:
            self.is_running = False

    def stop_log_stream(self):
        """停止日志流"""
        self.is_running = False

    def _add_log_line(self, line: str):
        """
        添加一行日志

        :param line: 日志内容
        """
        self.log_lines.append(line)

        # 限制日志行数
        if len(self.log_lines) > self.max_lines:
            self.log_lines = self.log_lines[-self.max_lines:]

        # 更新显示
        self.log_text.value = '\n'.join(self.log_lines)

        # TextField 不支持 scroll_to，需要使用其他方式
        # 自动滚动功能暂时移除，用户可以手动滚动

        self.page.update()

    def _toggle_auto_scroll(self, e):
        """切换自动滚动"""
        self.auto_scroll = e.control.value

    def _clear_logs(self, e):
        """清空日志"""
        self.log_lines.clear()
        self.log_text.value = ''
        self.page.update()
