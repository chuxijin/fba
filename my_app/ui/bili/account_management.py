#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bilibili 账号管理组件"""
import flet as ft

from my_app.services.api.backend_api import backend_api_service
from my_app.services.api.bili_api import bili_api_service


class AccountManagementTab:
    """账号管理 Tab"""

    def __init__(self, page: ft.Page):
        """
        初始化账号管理 Tab

        :param page: Flet 页面对象
        """
        self.page = page
        self.accounts = []
        self.categories = []
        self.selected_account = None
        self.data_loaded = False  # 数据加载标志
        self.categories_loaded = False  # 分类数据加载标志

        # 搜索筛选组件
        self.search_account_name = ft.TextField(
            label='账号名称',
            width=200,
            on_submit=lambda e: self.page.run_task(self.load_accounts),
        )

        self.search_mid = ft.TextField(
            label='B 站 MID',
            width=200,
            on_submit=lambda e: self.page.run_task(self.load_accounts),
        )

        self.search_status = ft.Dropdown(
            label='状态',
            width=150,
            options=[
                ft.dropdown.Option('1', '启用'),
                ft.dropdown.Option('0', '禁用'),
            ],
            on_change=lambda e: self.page.run_task(self.load_accounts),
        )

        # 数据表格
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text('ID', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('账号名称', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('MID', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('IP', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('状态', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('创建时间', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('操作', weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            column_spacing=20,
            heading_row_height=50,
            data_row_min_height=60,
        )

        self.table_container = ft.Container(
            content=ft.ListView(
                controls=[],
                spacing=0,
                padding=10,
                expand=True,
            ),
            expand=True,
        )

        # 无数据提示
        self.empty_hint = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.INBOX, size=80, color="#9e9e9e"),
                ft.Text('暂无数据', size=16, color="#9e9e9e"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True,
        )

        # 新增/编辑对话框表单
        self.dlg_cookie = ft.TextField(
            label='Cookie*',
            hint_text='粘贴完整的 Cookie 字符串',
            multiline=True,
            min_lines=3,
            max_lines=5,
            width=450,
        )
        self.dlg_fetch_btn = ft.ElevatedButton(
            '获取账号信息',
            icon=ft.Icons.DOWNLOAD,
            on_click=lambda e: self.page.run_task(self.fetch_user_info),
            width=450,
        )
        self.dlg_account_name = ft.TextField(label='账号名称*', width=450, read_only=False)
        self.dlg_mid = ft.TextField(label='B 站 MID', width=450, read_only=True)
        self.dlg_ip = ft.TextField(label='IP 地址（自动获取）', width=450, read_only=True)
        self.dlg_status = ft.Dropdown(
            label='状态',
            width=450,
            options=[
                ft.dropdown.Option('1', '启用'),
                ft.dropdown.Option('0', '禁用'),
            ],
            value='1',
        )
        self.dlg_category = ft.Dropdown(label='分类', width=450, options=[])

        # 信息提示文本
        self.dlg_info_text = ft.Text('', color="#666", size=12)

        # 新增/编辑对话框
        self.edit_dialog = ft.AlertDialog(
            title=ft.Text('新增账号'),
            content=ft.Container(
                content=ft.Column([
                    self.dlg_cookie,
                    self.dlg_fetch_btn,
                    ft.Divider(height=10),
                    self.dlg_info_text,
                    self.dlg_account_name,
                    self.dlg_mid,
                    self.dlg_ip,
                    self.dlg_status,
                    self.dlg_category,
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                width=500,
                height=550,
            ),
            actions=[
                ft.TextButton('取消', on_click=self.close_edit_dialog),
                ft.ElevatedButton('保存', on_click=self.save_account),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 删除确认对话框
        self.delete_dialog = ft.AlertDialog(
            title=ft.Text('确认删除'),
            content=ft.Text('确定要删除该账号吗？此操作不可恢复！'),
            actions=[
                ft.TextButton('取消', on_click=self.close_delete_dialog),
                ft.ElevatedButton('删除', on_click=self.confirm_delete, bgcolor="#ef5350"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def build(self) -> ft.Container:
        """构建账号管理 Tab 内容"""
        return ft.Container(
            content=ft.Column([
                # 顶部操作栏
                ft.Container(
                    content=ft.Row([
                        self.search_account_name,
                        self.search_mid,
                        self.search_status,
                        ft.ElevatedButton(
                            '搜索',
                            icon=ft.Icons.SEARCH,
                            on_click=lambda e: self.page.run_task(self.load_accounts),
                        ),
                        ft.ElevatedButton(
                            '重置',
                            icon=ft.Icons.REFRESH,
                            on_click=self.reset_search,
                        ),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            '新增账号',
                            icon=ft.Icons.ADD,
                            on_click=self.open_add_dialog,
                        ),
                    ], spacing=10),
                    padding=10,
                ),
                ft.Divider(height=1),
                # 数据表格区域
                self.table_container,
            ], spacing=0, expand=True),
            padding=10,
            expand=True,
        )

    async def load_accounts(self, force_reload: bool = False):
        """
        加载账号列表

        :param force_reload: 是否强制重新加载
        """
        # 如果已加载且不强制刷新，则跳过
        if self.data_loaded and not force_reload:
            print('DEBUG: 账号数据已缓存，跳过加载')
            return

        # 显示加载状态
        self.table_container.content.controls.clear()
        self.table_container.content.controls.append(
            ft.Container(
                content=ft.ProgressRing(),
                alignment=ft.alignment.center,
                expand=True,
            )
        )
        self.page.update()

        # 获取搜索条件
        account_name = self.search_account_name.value or None
        mid = self.search_mid.value or None
        status = int(self.search_status.value) if self.search_status.value else None

        # 调用后端 API
        self.accounts = await backend_api_service.get_account_list(
            account_name=account_name, mid=mid, status=status
        )

        # 更新表格
        self.update_table()
        self.data_loaded = True  # 标记为已加载

    def update_table(self):
        """更新数据表格"""
        self.table_container.content.controls.clear()

        if not self.accounts:
            # 显示空状态
            self.table_container.content.controls.append(self.empty_hint)
        else:
            # 显示数据表格
            self.data_table.rows.clear()
            for account in self.accounts:
                self.data_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(account.get('id', '')))),
                            ft.DataCell(ft.Text(account.get('account_name', ''))),
                            ft.DataCell(ft.Text(account.get('mid', '') or '-')),
                            ft.DataCell(ft.Text(account.get('ip', '') or '-')),
                            ft.DataCell(
                                ft.Chip(
                                    label=ft.Text('启用' if account.get('status') == 1 else '禁用'),
                                    bgcolor="#c8e6c9" if account.get('status') == 1 else "#ffcdd2",
                                )
                            ),
                            ft.DataCell(ft.Text(account.get('created_time', '')[:19] if account.get('created_time') else '-')),
                            ft.DataCell(
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT,
                                        tooltip='编辑',
                                        on_click=lambda e, acc=account: self.open_edit_dialog(acc),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE,
                                        tooltip='删除',
                                        icon_color="#ef5350",
                                        on_click=lambda e, acc=account: self.open_delete_dialog(acc),
                                    ),
                                ], spacing=0)
                            ),
                        ]
                    )
                )
            self.table_container.content.controls.append(self.data_table)

        self.page.update()

    def reset_search(self, e):
        """重置搜索条件"""
        self.search_account_name.value = ''
        self.search_mid.value = ''
        self.search_status.value = None
        self.page.run_task(self.load_accounts)

    def open_add_dialog(self, e):
        """打开新增对话框"""
        self.selected_account = None
        self.edit_dialog.title = ft.Text('新增账号')

        # 清空表单
        self.dlg_cookie.value = ''
        self.dlg_account_name.value = ''
        self.dlg_mid.value = ''
        self.dlg_ip.value = ''
        self.dlg_status.value = '1'
        self.dlg_category.value = None
        self.dlg_info_text.value = '请粘贴 Cookie 并点击"获取账号信息"，IP 地址将自动获取'

        # 显示获取按钮，编辑时隐藏
        self.dlg_fetch_btn.visible = True
        self.dlg_cookie.read_only = False

        self.page.overlay.append(self.edit_dialog)
        self.edit_dialog.open = True
        self.page.update()

    async def fetch_user_info(self):
        """通过 Cookie 获取用户信息"""
        cookie = self.dlg_cookie.value

        if not cookie:
            self.dlg_info_text.value = '❌ 请先填写 Cookie'
            self.dlg_info_text.color = "red"
            self.page.update()
            return

        # 显示加载状态
        self.dlg_info_text.value = '⏳ 正在获取账号信息和 IP 地址...'
        self.dlg_info_text.color = "#666"
        self.dlg_fetch_btn.disabled = True
        self.page.update()

        # 同时获取用户信息和 IP 地址
        user_info = await bili_api_service.get_user_info_by_cookie(cookie)
        current_ip = await bili_api_service.get_current_ip()

        if user_info:
            # 自动填充表单
            self.dlg_account_name.value = user_info.get('name', '')
            self.dlg_mid.value = str(user_info.get('mid', ''))
            self.dlg_ip.value = current_ip or ''  # 自动填充 IP
            self.dlg_info_text.value = f'✅ 成功获取账号信息：{user_info.get("name")} (Lv.{user_info.get("level", 0)}) | IP: {current_ip or "未获取"}'
            self.dlg_info_text.color = "green"
        else:
            self.dlg_info_text.value = '❌ 获取失败，请检查 Cookie 是否正确'
            self.dlg_info_text.color = "red"

        self.dlg_fetch_btn.disabled = False
        self.page.update()

    def open_edit_dialog(self, account: dict):
        """打开编辑对话框"""
        self.selected_account = account
        self.edit_dialog.title = ft.Text('编辑账号')

        # 填充表单
        self.dlg_cookie.value = account.get('cookie', '')
        self.dlg_account_name.value = account.get('account_name', '')
        self.dlg_mid.value = account.get('mid', '')
        self.dlg_ip.value = account.get('ip', '')
        self.dlg_status.value = str(account.get('status', 1))
        self.dlg_category.value = str(account.get('category_id')) if account.get('category_id') else None
        self.dlg_info_text.value = ''

        # 编辑时隐藏获取按钮
        self.dlg_fetch_btn.visible = False
        self.dlg_cookie.read_only = False

        self.page.overlay.append(self.edit_dialog)
        self.edit_dialog.open = True
        self.page.update()

    def close_edit_dialog(self, e):
        """关闭编辑对话框"""
        self.edit_dialog.open = False
        self.page.update()

    def save_account(self, e):
        """保存账号"""
        # 验证必填项
        if not self.dlg_cookie.value:
            self._show_snackbar('请填写 Cookie', error=True)
            return

        if not self.dlg_account_name.value:
            self._show_snackbar('请先获取账号信息或手动填写账号名称', error=True)
            return

        if not self.dlg_mid.value:
            self._show_snackbar('请先获取账号信息', error=True)
            return

        # 构建数据
        account_data = {
            'account_name': self.dlg_account_name.value,
            'mid': self.dlg_mid.value or None,
            'cookie': self.dlg_cookie.value or None,
            'ip': self.dlg_ip.value or None,
            'status': int(self.dlg_status.value),
            'category_id': int(self.dlg_category.value) if self.dlg_category.value else None,
        }

        # 调用保存任务
        if self.selected_account:
            # 更新
            self.page.run_task(self.do_update_account, self.selected_account['id'], account_data)
        else:
            # 新增
            self.page.run_task(self.do_create_account, account_data)

        self.close_edit_dialog(e)

    async def do_create_account(self, account_data: dict):
        """执行创建账号"""
        success = await backend_api_service.create_account(account_data)
        if success:
            self._show_snackbar('账号创建成功')
            await self.load_accounts(force_reload=True)
        else:
            self._show_snackbar('账号创建��败', error=True)

    async def do_update_account(self, pk: int, account_data: dict):
        """执行更新账号"""
        success = await backend_api_service.update_account(pk, account_data)
        if success:
            self._show_snackbar('账号更新成功')
            await self.load_accounts(force_reload=True)
        else:
            self._show_snackbar('账号更新失败', error=True)

    def open_delete_dialog(self, account: dict):
        """打开删除确认对话框"""
        self.selected_account = account
        self.delete_dialog.content = ft.Text(f'确定要删除账号 "{account.get("account_name")}" 吗？此操作不可恢复！')

        self.page.overlay.append(self.delete_dialog)
        self.delete_dialog.open = True
        self.page.update()

    def close_delete_dialog(self, e):
        """关闭删除对话框"""
        self.delete_dialog.open = False
        self.page.update()

    def confirm_delete(self, e):
        """确认删除"""
        if self.selected_account:
            self.page.run_task(self.do_delete_account, self.selected_account['id'])
        self.close_delete_dialog(e)

    async def do_delete_account(self, pk: int):
        """执行删除账号"""
        success = await backend_api_service.delete_account(pk)
        if success:
            self._show_snackbar('账号删除成功')
            await self.load_accounts(force_reload=True)
        else:
            self._show_snackbar('账号删除失败', error=True)

    async def load_categories(self, force_reload: bool = False):
        """
        加载分类列表

        :param force_reload: 是否强制重新加载
        """
        # 如果已加载且不强制刷新，则跳过
        if self.categories_loaded and not force_reload:
            print('DEBUG: 账号分类数据已缓存，跳过加载')
            return

        self.categories = await backend_api_service.get_category_list()
        self.dlg_category.options = [
            ft.dropdown.Option(str(cat['id']), cat['name']) for cat in self.categories
        ]
        self.page.update()
        self.categories_loaded = True  # 标记为已加载

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
