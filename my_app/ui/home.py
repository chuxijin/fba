#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首页组件"""
import flet as ft

from my_app.ui.bili.account_management import AccountManagementTab
from my_app.ui.bili.template_management import TemplateManagementTab
from my_app.ui.bili.operation_records import OperationRecordsTab
from my_app.ui.bili.task_config_management import TaskConfigManagementTab
from my_app.ui.bili.log_viewer import LogViewerTab
from my_app.ui.settings.settings_page import SettingsPage


class HomePage:
    """首页类"""

    def __init__(self, page: ft.Page):
        """
        初始化首页

        :param page: Flet 页面对象
        """
        self.page = page
        self.current_nav_index = 0

        # 初始化各功能模块
        self.account_management_tab = AccountManagementTab(page)
        self.template_management_tab = TemplateManagementTab(page)
        self.operation_records_tab = OperationRecordsTab(page)
        self.task_config_management_tab = TaskConfigManagementTab(page)
        self.log_viewer_tab = LogViewerTab(page)
        self.settings_page = SettingsPage(page)

        # Tabs 组件
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            on_change=self.on_tab_change,
            tabs=[
                ft.Tab(
                    text='账号管理',
                    icon=ft.Icons.ACCOUNT_CIRCLE,
                    content=self.account_management_tab.build(),
                ),
                ft.Tab(
                    text='话术管理',
                    icon=ft.Icons.MESSAGE,
                    content=self.template_management_tab.build(),
                ),
                ft.Tab(
                    text='操作记录',
                    icon=ft.Icons.HISTORY,
                    content=self.operation_records_tab.build(),
                ),
                ft.Tab(
                    text='任务配置',
                    icon=ft.Icons.SETTINGS_APPLICATIONS,
                    content=self.task_config_management_tab.build(),
                ),
                ft.Tab(
                    text='日志',
                    icon=ft.Icons.ARTICLE,
                    content=self.log_viewer_tab.build(),
                ),
            ],
            expand=True,
        )

        # 主内容区容器（用于切换 Bilibili 和设置）
        self.main_content = ft.Container(expand=True)

        # Bilibili 导航按钮
        self.bili_btn = ft.IconButton(
            icon=ft.Icons.ONDEMAND_VIDEO,
            icon_size=30,
            icon_color="blue",
            tooltip="Bilibili 业务",
            on_click=lambda e: self.on_nav_change(0),
        )

        # 设置导航按钮
        self.settings_btn = ft.IconButton(
            icon=ft.Icons.SETTINGS_OUTLINED,
            icon_size=30,
            tooltip="设置",
            on_click=lambda e: self.on_nav_change(1),
        )

    def build(self) -> ft.Container:
        """
        构建首页 UI

        :return: 首页容器
        """
        # 侧边栏导航（设置固定在底部）
        rail = ft.Container(
            content=ft.Column([
                # Bilibili 业务导航
                ft.Container(
                    content=ft.Column([
                        self.bili_btn,
                        ft.Text('Bilibili', size=12, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                    padding=ft.padding.only(top=10, bottom=10),
                    alignment=ft.alignment.center,
                ),
                # 占位符，将设置推到底部
                ft.Container(expand=True),
                # 设置导航（底部）
                ft.Container(
                    content=ft.Column([
                        self.settings_btn,
                        ft.Text('设置', size=12, text_align=ft.TextAlign.CENTER),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
                    padding=ft.padding.only(top=10, bottom=10),
                    alignment=ft.alignment.center,
                ),
            ], spacing=0, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            width=100,
            bgcolor="#f5f5f5",
            alignment=ft.alignment.top_center,
        )

        # 初始显示 Bilibili 业务内容
        self._update_main_content()

        # 自动加载初始 Tab 数据（账号管理）
        self.page.run_task(self.account_management_tab.load_accounts)
        self.page.run_task(self.account_management_tab.load_categories)

        # 整体布局
        return ft.Container(
            content=ft.Row([
                rail,
                ft.VerticalDivider(width=1),
                self.main_content,
            ], expand=True, spacing=0),
            expand=True,
        )

    def _update_main_content(self):
        """更新主内容区"""
        if self.current_nav_index == 0:
            # Bilibili 业务
            self.main_content.content = ft.Column([
                # 顶部标题
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.ONDEMAND_VIDEO, size=40, color="blue"),
                        ft.Text('Bilibili 业务', size=32, weight=ft.FontWeight.BOLD),
                    ]),
                    padding=ft.padding.only(left=30, top=20, bottom=10),
                ),
                ft.Divider(height=1),
                # Tabs 内容区
                ft.Container(
                    content=self.tabs,
                    padding=ft.padding.only(left=20, right=20, top=10),
                    expand=True,
                ),
            ], spacing=0, expand=True)
            # 更新导航按钮状态
            self.bili_btn.icon_color = "blue"
            self.settings_btn.icon_color = None
        else:
            # 设置页面
            self.main_content.content = self.settings_page.build()
            # 更新导航按钮状态
            self.bili_btn.icon_color = None
            self.settings_btn.icon_color = "blue"

    def _build_coming_soon_tab(self, message: str) -> ft.Container:
        """
        构建开发中 Tab 内容

        :param message: 提示消息
        :return: 开发中内容
        """
        return ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.CONSTRUCTION, size=100, color="orange"),
                ft.Container(height=20),
                ft.Text(message, size=20),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True,
        )

    def on_nav_change(self, index: int):
        """
        导航切换事件

        :param index: 导航索引
        :return:
        """
        if self.current_nav_index != index:
            self.current_nav_index = index
            self._update_main_content()
            self.page.update()

    def on_tab_change(self, e):
        """
        Tab 切换事件

        :param e: 事件对象
        :return:
        """
        tab_index = e.control.selected_index

        # 停止日志流（如果从日志 Tab 切换走）
        if hasattr(self, 'log_viewer_tab'):
            self.log_viewer_tab.stop_log_stream()

        # 根据 Tab 索引加载对应数据
        if tab_index == 0:
            # 账号管理
            self.page.run_task(self.account_management_tab.load_accounts)
            self.page.run_task(self.account_management_tab.load_categories)
        elif tab_index == 1:
            # 话术管理
            self.page.run_task(self.template_management_tab.load_templates)
            self.page.run_task(self.template_management_tab.load_categories)
        elif tab_index == 2:
            # 操作记录
            self.page.run_task(self.operation_records_tab.load_records)
        elif tab_index == 3:
            # 任务配置
            self.page.run_task(self.task_config_management_tab.load_task_configs)
        elif tab_index == 4:
            # 日志查看器
            self.page.run_task(self.log_viewer_tab.start_log_stream)
