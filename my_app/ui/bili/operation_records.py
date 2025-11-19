#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B 站操作记录组件"""
import flet as ft

from my_app.services.api.backend_api import backend_api_service


class OperationRecordsTab:
    """操作记录 Tab"""

    def __init__(self, page: ft.Page):
        """
        初始化操作记录 Tab

        :param page: Flet 页面对象
        """
        self.page = page
        self.records = []
        self.selected_record = None
        self.current_page = 1
        self.page_size = 20
        self.total = 0
        self.total_pages = 0
        self.data_loaded = False  # 数据加载标志

        # 搜索筛选组件
        self.search_mid = ft.TextField(
            label='MID',
            width=200,
            on_submit=lambda e: self.page.run_task(self.load_records),
        )

        self.search_operation_type = ft.Dropdown(
            label='操作类型',
            width=150,
            options=[
                ft.dropdown.Option('at', '@'),
                ft.dropdown.Option('comment', '评论'),
                ft.dropdown.Option('message', '私信'),
                ft.dropdown.Option('blacklist', '黑名单'),
            ],
            on_change=lambda e: self.page.run_task(self.load_records),
        )

        self.search_is_active = ft.Dropdown(
            label='是否主动',
            width=150,
            options=[
                ft.dropdown.Option('true', '是'),
                ft.dropdown.Option('false', '否'),
            ],
            on_change=lambda e: self.page.run_task(self.load_records),
        )

        self.search_work_id = ft.TextField(
            label='作品 ID',
            width=200,
            on_submit=lambda e: self.page.run_task(self.load_records),
        )

        # 数据表格
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text('ID', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('MID', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('操作类型', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('是否主动', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('发送内容', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('发送结果', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('作品 ID', weight=ft.FontWeight.BOLD)),
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

        # 分页组件
        self.page_info = ft.Text('', size=14)
        self.prev_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_LEFT,
            tooltip='上一页',
            on_click=self.prev_page,
        )
        self.next_btn = ft.IconButton(
            icon=ft.Icons.CHEVRON_RIGHT,
            tooltip='下一页',
            on_click=self.next_page,
        )
        self.page_size_dropdown = ft.Dropdown(
            label='每页数量',
            width=120,
            value='20',
            options=[
                ft.dropdown.Option('10', '10'),
                ft.dropdown.Option('20', '20'),
                ft.dropdown.Option('50', '50'),
                ft.dropdown.Option('100', '100'),
            ],
            on_change=self.change_page_size,
        )

        # 新增/编辑对话框表单
        self.dlg_mid = ft.TextField(label='MID*', width=450)
        self.dlg_operation_type = ft.Dropdown(
            label='操作类型*',
            width=450,
            options=[
                ft.dropdown.Option('at', '@'),
                ft.dropdown.Option('comment', '评论'),
                ft.dropdown.Option('message', '私信'),
                ft.dropdown.Option('blacklist', '黑名单'),
            ],
        )
        self.dlg_is_active = ft.Dropdown(
            label='是否主动*',
            width=450,
            options=[
                ft.dropdown.Option('true', '是'),
                ft.dropdown.Option('false', '否'),
            ],
            value='true',
        )
        self.dlg_send_content = ft.TextField(
            label='发送内容',
            width=450,
            multiline=True,
            min_lines=3,
            max_lines=5,
        )
        self.dlg_send_result = ft.TextField(
            label='发送结果',
            width=450,
            multiline=True,
            min_lines=3,
            max_lines=5,
        )
        self.dlg_work_id = ft.TextField(label='作品 ID', width=450)

        # 新增/编辑对话框
        self.edit_dialog = ft.AlertDialog(
            title=ft.Text('新增记录'),
            content=ft.Container(
                content=ft.Column([
                    self.dlg_mid,
                    self.dlg_operation_type,
                    self.dlg_is_active,
                    self.dlg_send_content,
                    self.dlg_send_result,
                    self.dlg_work_id,
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                width=500,
                height=550,
            ),
            actions=[
                ft.TextButton('取消', on_click=self.close_edit_dialog),
                ft.ElevatedButton('保存', on_click=self.save_record),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 删除确认对话框
        self.delete_dialog = ft.AlertDialog(
            title=ft.Text('确认删除'),
            content=ft.Text('确定要删除该记录吗？此操作不可恢复！'),
            actions=[
                ft.TextButton('取消', on_click=self.close_delete_dialog),
                ft.ElevatedButton('删除', on_click=self.confirm_delete, bgcolor="#ef5350"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def build(self) -> ft.Container:
        """构建操作记录 Tab 内容"""
        return ft.Container(
            content=ft.Column([
                # 顶部操作栏
                ft.Container(
                    content=ft.Row([
                        self.search_mid,
                        self.search_operation_type,
                        self.search_is_active,
                        self.search_work_id,
                        ft.ElevatedButton(
                            '搜索',
                            icon=ft.Icons.SEARCH,
                            on_click=lambda e: self.page.run_task(self.load_records),
                        ),
                        ft.ElevatedButton(
                            '重置',
                            icon=ft.Icons.REFRESH,
                            on_click=self.reset_search,
                        ),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            '新增记录',
                            icon=ft.Icons.ADD,
                            on_click=self.open_add_dialog,
                        ),
                    ], spacing=10),
                    padding=10,
                ),
                ft.Divider(height=1),
                # 数据表格区域
                self.table_container,
                ft.Divider(height=1),
                # 分页栏
                ft.Container(
                    content=ft.Row([
                        self.page_info,
                        ft.Container(expand=True),
                        self.page_size_dropdown,
                        self.prev_btn,
                        self.next_btn,
                    ], spacing=10),
                    padding=10,
                ),
            ], spacing=0, expand=True),
            padding=10,
            expand=True,
        )

    async def load_records(self, force_reload: bool = False):
        """
        加载操作记录列表

        :param force_reload: 是否强制重新加载
        """
        # 如果已加载且不强制刷新，则跳过
        if self.data_loaded and not force_reload:
            print('DEBUG: 操作记录数据已缓存，跳过加载')
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
        mid = self.search_mid.value or None
        operation_type = self.search_operation_type.value or None
        is_active = None
        if self.search_is_active.value:
            is_active = self.search_is_active.value == 'true'
        work_id = int(self.search_work_id.value) if self.search_work_id.value else None

        # 调用后端 API
        page_data = await backend_api_service.get_duplicate_check_list(
            mid=mid,
            operation_type=operation_type,
            is_active=is_active,
            work_id=work_id,
            page=self.current_page,
            size=self.page_size,
        )

        # 更新分页信息
        if page_data:
            self.records = page_data.get('items', [])
            self.total = page_data.get('total', 0)
            self.total_pages = (self.total + self.page_size - 1) // self.page_size
        else:
            self.records = []
            self.total = 0
            self.total_pages = 0

        # 更新表格
        self.update_table()
        self.data_loaded = True  # 标记为已加载

    def update_table(self):
        """更新数据表格"""
        self.table_container.content.controls.clear()

        if not self.records:
            # 显示空状态
            self.table_container.content.controls.append(self.empty_hint)
        else:
            # 显示数据表格
            self.data_table.rows.clear()
            for record in self.records:
                # 操作类型映射
                operation_type_map = {'at': '@', 'comment': '评论', 'message': '私信', 'blacklist': '黑名单'}
                operation_type_text = operation_type_map.get(record.get('operation_type', ''), record.get('operation_type', ''))

                self.data_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(record.get('id', '')))),
                            ft.DataCell(ft.Text(record.get('mid', '') or '-')),
                            ft.DataCell(ft.Text(operation_type_text)),
                            ft.DataCell(
                                ft.Chip(
                                    label=ft.Text('是' if record.get('is_active') else '否'),
                                    bgcolor="#c8e6c9" if record.get('is_active') else "#ffcdd2",
                                )
                            ),
                            ft.DataCell(
                                ft.Container(
                                    content=ft.Text(
                                        (content := record.get('send_content', '') or '-')[:20] + ('...' if len(content) > 20 else ''),
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    tooltip=record.get('send_content', '') or '-',
                                )
                            ),
                            ft.DataCell(
                                ft.Container(
                                    content=ft.Text(
                                        (result := record.get('send_result', '') or '-')[:20] + ('...' if len(result) > 20 else ''),
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                    ),
                                    tooltip=record.get('send_result', '') or '-',
                                )
                            ),
                            ft.DataCell(ft.Text(str(record.get('work_id', '')) if record.get('work_id') else '-')),
                            ft.DataCell(ft.Text(record.get('created_time', '')[:19] if record.get('created_time') else '-')),
                            ft.DataCell(
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT,
                                        tooltip='编辑',
                                        on_click=lambda e, rec=record: self.open_edit_dialog(rec),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE,
                                        tooltip='删除',
                                        icon_color="#ef5350",
                                        on_click=lambda e, rec=record: self.open_delete_dialog(rec),
                                    ),
                                ], spacing=0)
                            ),
                        ]
                    )
                )
            self.table_container.content.controls.append(self.data_table)

        # 更新分页信息
        self.page_info.value = f'第 {self.current_page}/{self.total_pages} 页，共 {self.total} 条记录'
        self.prev_btn.disabled = self.current_page <= 1
        self.next_btn.disabled = self.current_page >= self.total_pages

        self.page.update()

    def prev_page(self, e):
        """上一页"""
        if self.current_page > 1:
            self.current_page -= 1
            self.page.run_task(self.load_records)

    def next_page(self, e):
        """下一页"""
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.page.run_task(self.load_records)

    def change_page_size(self, e):
        """修改每页数量"""
        self.page_size = int(self.page_size_dropdown.value)
        self.current_page = 1
        self.page.run_task(self.load_records)

    def reset_search(self, e):
        """重置搜索条件"""
        self.search_mid.value = ''
        self.search_operation_type.value = None
        self.search_is_active.value = None
        self.search_work_id.value = ''
        self.current_page = 1
        self.page.run_task(self.load_records)

    def open_add_dialog(self, e):
        """打开新增对话框"""
        self.selected_record = None
        self.edit_dialog.title = ft.Text('新增记录')

        # 清空表单
        self.dlg_mid.value = ''
        self.dlg_operation_type.value = None
        self.dlg_is_active.value = 'true'
        self.dlg_send_content.value = ''
        self.dlg_send_result.value = ''
        self.dlg_work_id.value = ''

        self.page.overlay.append(self.edit_dialog)
        self.edit_dialog.open = True
        self.page.update()

    def open_edit_dialog(self, record: dict):
        """打开编辑对话框"""
        self.selected_record = record
        self.edit_dialog.title = ft.Text('编辑记录')

        # 填充表单
        self.dlg_mid.value = record.get('mid', '')
        self.dlg_operation_type.value = record.get('operation_type', '')
        self.dlg_is_active.value = 'true' if record.get('is_active') else 'false'
        self.dlg_send_content.value = record.get('send_content', '') or ''
        self.dlg_send_result.value = record.get('send_result', '') or ''
        self.dlg_work_id.value = str(record.get('work_id', '')) if record.get('work_id') else ''

        self.page.overlay.append(self.edit_dialog)
        self.edit_dialog.open = True
        self.page.update()

    def close_edit_dialog(self, e):
        """关闭编辑对话框"""
        self.edit_dialog.open = False
        self.page.update()

    def save_record(self, e):
        """保存记录"""
        # 验证必填项
        if not self.dlg_mid.value:
            self._show_snackbar('请填写 MID', error=True)
            return

        if not self.dlg_operation_type.value:
            self._show_snackbar('请选择操作类型', error=True)
            return

        # 构建数据
        record_data = {
            'mid': self.dlg_mid.value,
            'operation_type': self.dlg_operation_type.value,
            'is_active': self.dlg_is_active.value == 'true',
            'send_content': self.dlg_send_content.value or None,
            'send_result': self.dlg_send_result.value or None,
            'work_id': int(self.dlg_work_id.value) if self.dlg_work_id.value else None,
        }

        # 调用保存任务
        if self.selected_record:
            # 更新
            self.page.run_task(self.do_update_record, self.selected_record['id'], record_data)
        else:
            # 新增
            self.page.run_task(self.do_create_record, record_data)

        self.close_edit_dialog(e)

    async def do_create_record(self, record_data: dict):
        """执行创建记录"""
        success = await backend_api_service.create_duplicate_check(record_data)
        if success:
            self._show_snackbar('记录创建成功')
            await self.load_records()
        else:
            self._show_snackbar('记录创建失败', error=True)

    async def do_update_record(self, pk: int, record_data: dict):
        """执行更新记录"""
        success = await backend_api_service.update_duplicate_check(pk, record_data)
        if success:
            self._show_snackbar('记录更新成功')
            await self.load_records()
        else:
            self._show_snackbar('记录更新失败', error=True)

    def open_delete_dialog(self, record: dict):
        """打开删除确认对话框"""
        self.selected_record = record
        self.delete_dialog.content = ft.Text(f'确定要删除 ID 为 {record.get("id")} 的记录吗？此操作不可恢复！')

        self.page.overlay.append(self.delete_dialog)
        self.delete_dialog.open = True
        self.page.update()

    def close_delete_dialog(self, e):
        """关闭删除对话框"""
        self.delete_dialog.open = False
        self.page.update()

    def confirm_delete(self, e):
        """确认删除"""
        if self.selected_record:
            self.page.run_task(self.do_delete_record, self.selected_record['id'])
        self.close_delete_dialog(e)

    async def do_delete_record(self, pk: int):
        """执行删除记录"""
        success = await backend_api_service.delete_duplicate_check(pk)
        if success:
            self._show_snackbar('记录删除成功')
            await self.load_records(force_reload=True)
        else:
            self._show_snackbar('记录删除失败', error=True)

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
