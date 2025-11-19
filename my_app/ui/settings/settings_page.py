#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""设置页面组件"""
import flet as ft

from my_app.services.config_service import config_service


class SettingsPage:
    """设置页面"""

    def __init__(self, page: ft.Page):
        """
        初始化设置页面

        :param page: Flet 页面对象
        """
        self.page = page

        # 从配置文件加载当前配置
        current_theme = config_service.get('theme', 'light')
        current_api_url = config_service.get('api_base_url', 'http://localhost:8000')
        current_interval_min = config_service.get('bili_interval_min', 30)
        current_interval_max = config_service.get('bili_interval_max', 60)

        # 主题设置控件
        self.theme_radio_group = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="light", label="浅色主题"),
                ft.Radio(value="dark", label="深色主题"),
                ft.Radio(value="system", label="跟随系统"),
            ]),
            value=current_theme,
            on_change=self.on_theme_change,
        )

        # API 地址输入框
        self.api_url_field = ft.TextField(
            label='后端 API 地址',
            value=current_api_url,
            hint_text='例如：http://localhost:8000',
            on_blur=self.on_api_url_change,
            on_submit=self.on_api_url_change,
        )

        # 间隔时间
        self.interval_min_field = ft.TextField(
            label='最小间隔（秒）',
            value=str(current_interval_min),
            width=140,
            on_blur=self.on_interval_change,
            on_submit=self.on_interval_change,
        )
        self.interval_max_field = ft.TextField(
            label='最大间隔（秒）',
            value=str(current_interval_max),
            width=140,
            on_blur=self.on_interval_change,
            on_submit=self.on_interval_change,
        )

        # 应用初始主题
        self._apply_theme(current_theme)

    def build(self) -> ft.Container:
        """构建设置页面 UI"""
        return ft.Container(
            content=ft.Column([
                # 页面标题
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.SETTINGS, size=40, color="blue"),
                        ft.Text('应用设置', size=32, weight=ft.FontWeight.BOLD),
                    ]),
                    padding=ft.padding.only(left=30, top=20, bottom=10),
                ),
                ft.Divider(height=1),

                # 设置内容区
                ft.Container(
                    content=ft.Column([
                        # 主题设置
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.PALETTE),
                                        title=ft.Text('主题设置', size=18, weight=ft.FontWeight.BOLD),
                                    ),
                                    ft.Divider(height=1),
                                    ft.Container(
                                        content=ft.Column([
                                            self.theme_radio_group,
                                        ]),
                                        padding=15,
                                    ),
                                ]),
                            ),
                        ),

                        ft.Container(height=20),

                        # API 设置
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.API),
                                        title=ft.Text('API 设置', size=18, weight=ft.FontWeight.BOLD),
                                    ),
                                    ft.Divider(height=1),
                                    ft.Container(
                                        content=ft.Column([
                                            self.api_url_field,
                                            ft.Container(height=10),
                                            ft.Row([
                                                ft.ElevatedButton(
                                                    '测试连接',
                                                    icon=ft.Icons.WIFI_TETHERING,
                                                    on_click=self.test_api_connection,
                                                ),
                                                ft.ElevatedButton(
                                                    '重置默认',
                                                    icon=ft.Icons.RESTORE,
                                                    on_click=self.reset_config,
                                                ),
                                            ], spacing=10),
                                        ]),
                                        padding=15,
                                    ),
                                ]),
                            ),
                        ),

                        ft.Container(height=20),

                        # Bilibili 业务配置
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.ONDEMAND_VIDEO),
                                        title=ft.Text('Bilibili 业务配置', size=18, weight=ft.FontWeight.BOLD),
                                    ),
                                    ft.Divider(height=1),
                                    ft.Container(
                                        content=ft.Column([
                                            # 间隔时间
                                            ft.Text('操作间隔时间', size=14, weight=ft.FontWeight.W_500),
                                            ft.Container(height=5),
                                            ft.Row([
                                                self.interval_min_field,
                                                ft.Text('至', size=16),
                                                self.interval_max_field,
                                                ft.Text('秒', size=14, color="#666"),
                                            ], spacing=10),
                                            ft.Container(height=10),
                                            ft.Text('提示：等级筛选和注册时间限制已移至任务配置中单独设置', size=12, color="#999"),
                                        ]),
                                        padding=15,
                                    ),
                                ]),
                            ),
                        ),

                        ft.Container(height=20),

                        # 关于信息
                        ft.Card(
                            content=ft.Container(
                                content=ft.Column([
                                    ft.ListTile(
                                        leading=ft.Icon(ft.Icons.INFO),
                                        title=ft.Text('关于', size=18, weight=ft.FontWeight.BOLD),
                                    ),
                                    ft.Divider(height=1),
                                    ft.Container(
                                        content=ft.Column([
                                            ft.Text('B 站账号管理器', size=16, weight=ft.FontWeight.BOLD),
                                            ft.Container(height=5),
                                            ft.Text('版本: 1.0.0', size=14),
                                            ft.Container(height=5),
                                            ft.Text('基于 Flet 框架开发', size=14),
                                            ft.Container(height=5),
                                            ft.Text('配置文件: config.json', size=14, color="#666"),
                                        ]),
                                        padding=15,
                                    ),
                                ]),
                            ),
                        ),
                    ], scroll=ft.ScrollMode.AUTO),
                    padding=ft.padding.only(left=20, right=20, top=10),
                    expand=True,
                ),
            ], spacing=0, expand=True),
            expand=True,
        )

    def _apply_theme(self, theme_value: str):
        """
        应用主题设置

        :param theme_value: 主题值
        :return:
        """
        if theme_value == "light":
            self.page.theme_mode = ft.ThemeMode.LIGHT
        elif theme_value == "dark":
            self.page.theme_mode = ft.ThemeMode.DARK
        else:
            self.page.theme_mode = ft.ThemeMode.SYSTEM

    def on_theme_change(self, e):
        """主题切换事件"""
        theme_value = e.control.value
        # 应用主题
        self._apply_theme(theme_value)
        self.page.update()
        # 保存到配置文件
        config_service.set('theme', theme_value)
        self._show_snackbar(f'已切换主题，配置已自动保存')

    def on_api_url_change(self, e):
        """API 地址修改事件"""
        api_url = self.api_url_field.value
        if api_url:
            # 保存到配置文件
            config_service.set('api_base_url', api_url)
            self._show_snackbar('API 地址已保存')

    def on_interval_change(self, e):
        """间隔时间修改事件"""
        try:
            interval_min = int(self.interval_min_field.value or 30)
            interval_max = int(self.interval_max_field.value or 60)
            if interval_min > interval_max:
                self._show_snackbar('最小间隔不能大于最大间隔', error=True)
                return
            config_service.set('bili_interval_min', interval_min)
            config_service.set('bili_interval_max', interval_max)
            self._show_snackbar('间隔时间已保存')
        except ValueError:
            self._show_snackbar('请输入有效的数字', error=True)

    def test_api_connection(self, e):
        """测试 API 连接"""
        api_url = self.api_url_field.value
        self.page.run_task(self._do_test_connection, api_url)

    async def _do_test_connection(self, api_url: str):
        """
        执行 API 连接测试

        :param api_url: API 地址
        :return:
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f'{api_url}/api/v1/sys/configs')
                if response.status_code == 200:
                    self._show_snackbar('✅ API 连接成功')
                else:
                    self._show_snackbar(f'⚠️ API 返回状态码: {response.status_code}')
        except httpx.ConnectError:
            self._show_snackbar('❌ 连接失败，请检查地址是否正确')
        except httpx.TimeoutException:
            self._show_snackbar('❌ 连接超时，请检查服务是否运行')
        except Exception as ex:
            self._show_snackbar(f'❌ 连接失败: {str(ex)}')

    def reset_config(self, e):
        """重置配置为默认值"""
        config_service.reset()
        # 更新 UI 控件
        self.theme_radio_group.value = 'light'
        self.api_url_field.value = 'http://localhost:8000'
        self.interval_min_field.value = '30'
        self.interval_max_field.value = '60'
        self._apply_theme('light')
        self.page.update()
        self._show_snackbar('配置已重置为默认值')

    def _show_snackbar(self, message: str, error: bool = False):
        """显示提示条"""
        snack_bar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor="#ef5350" if error else None,
            action='好的',
        )
        self.page.overlay.append(snack_bar)
        snack_bar.open = True
        self.page.update()
