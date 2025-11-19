#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bilibili 任务配置管理组件"""
import flet as ft

from my_app.services.api.backend_api import backend_api_service


class TaskConfigManagementTab:
    """任务配置管理 Tab"""

    def __init__(self, page: ft.Page):
        """
        初始化任务配置管理 Tab

        :param page: Flet 页面对象
        """
        self.page = page
        self.task_configs = []
        self.accounts = []
        self.selected_task_config = None
        self.data_loaded = False  # 数据加载标志

        # 搜索筛选组件
        self.search_task_name = ft.TextField(
            label='任务名称',
            width=200,
            on_submit=lambda e: self.page.run_task(self.load_task_configs, True),
        )

        self.search_task_type = ft.Dropdown(
            label='任务类型',
            width=250,
            options=[
                ft.dropdown.Option('reply_my_message', '回复私信'),
                ft.dropdown.Option('reply_my_comment', '回复评论'),
                ft.dropdown.Option('send_to_others_comment', '评论区私信截流'),
            ],
            on_change=lambda e: self.page.run_task(self.load_task_configs, True),
        )

        self.search_is_enabled = ft.Dropdown(
            label='状态',
            width=150,
            options=[
                ft.dropdown.Option('true', '启用'),
                ft.dropdown.Option('false', '禁用'),
            ],
            on_change=lambda e: self.page.run_task(self.load_task_configs, True),
        )

        # 数据表格
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text('ID', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('任务名称', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('任务类型', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('工作时间', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('状态', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('运行次数', weight=ft.FontWeight.BOLD)),
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
                ft.Text('暂无任务配置', size=16, color="#9e9e9e"),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            alignment=ft.alignment.center,
            expand=True,
        )

        # 新增/编辑对话框表单
        self.dlg_task_name = ft.TextField(label='任务名称*', width=500)
        self.dlg_task_type = ft.Dropdown(
            label='任务类型*',
            width=500,
            options=[
                ft.dropdown.Option('reply_my_message', '回复私信'),
                ft.dropdown.Option('reply_my_comment', '回复评论'),
                ft.dropdown.Option('send_to_others_comment', '评论区私信截流'),
            ],
        )
        self.dlg_account_id = ft.Dropdown(
            label='执行账号*',
            width=500,
            options=[],
        )
        self.dlg_work_id = ft.TextField(
            label='关联作品 BVID',
            width=500,
            hint_text='输入 BVID(如: BV1XTy7B2ERT) 或完整网址',
            on_blur=self._normalize_bvid,
        )
        self.dlg_start_time = ft.TextField(label='开始时间*', width=240, hint_text='HH:MM:SS', value='09:00:00')
        self.dlg_end_time = ft.TextField(label='结束时间*', width=240, hint_text='HH:MM:SS', value='22:00:00')
        self.dlg_rest_start_time = ft.TextField(label='休息开始', width=240, hint_text='HH:MM:SS (可选)')
        self.dlg_rest_end_time = ft.TextField(label='休息结束', width=240, hint_text='HH:MM:SS (可选)')
        self.dlg_check_interval_min = ft.TextField(
            label='检查间隔最小值（分钟）*', width=240, keyboard_type=ft.KeyboardType.NUMBER, value='5'
        )
        self.dlg_check_interval_max = ft.TextField(
            label='检查间隔最大值（分钟）*', width=240, keyboard_type=ft.KeyboardType.NUMBER, value='10'
        )

        # 用户筛选条件 - 等级筛选（多选框）
        self.dlg_exclude_levels = []
        for level in range(1, 7):
            checkbox = ft.Checkbox(
                label=f'Lv.{level}',
                value=False,
            )
            self.dlg_exclude_levels.append(checkbox)

        # 用户筛选条件 - 注册天数
        self.dlg_min_reg_days = ft.TextField(
            label='最少注册天数', width=240, keyboard_type=ft.KeyboardType.NUMBER, hint_text='如: 30 (可选)'
        )

        # 模板列表容器（用于动态加载模板 Checkbox）
        self.dlg_template_checkboxes = []
        self.dlg_template_container = ft.Column([], spacing=5)

        self.dlg_description = ft.TextField(label='任务描述', width=500, multiline=True, min_lines=2, max_lines=3)
        self.dlg_is_enabled = ft.Switch(label='启用任务', value=True)

    def build(self) -> ft.Container:
        """
        构建任务配置管理 Tab UI

        :return: 任务配置管理 Tab 容器
        """
        return ft.Container(
            content=ft.Column([
                # 工具栏
                ft.Container(
                    content=ft.Row([
                        # 左侧搜索栏
                        ft.Row([
                            self.search_task_name,
                            self.search_task_type,
                            self.search_is_enabled,
                            ft.IconButton(
                                icon=ft.Icons.SEARCH,
                                tooltip='搜索',
                                on_click=lambda e: self.page.run_task(self.load_task_configs, True),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.REFRESH,
                                tooltip='刷新',
                                on_click=lambda e: self.page.run_task(self.clear_and_reload),
                            ),
                        ], spacing=10),
                        # 占位符推右侧按钮
                        ft.Container(expand=True),
                        # 右侧操作按钮
                        ft.ElevatedButton(
                            '新增任务',
                            icon=ft.Icons.ADD,
                            on_click=lambda e: self.show_add_dialog(),
                        ),
                    ]),
                    padding=ft.padding.only(left=10, right=10, top=10, bottom=10),
                ),
                ft.Divider(height=1),
                # 数据表格区域
                self.table_container,
            ], spacing=0, expand=True),
            expand=True,
        )

    async def load_task_configs(self, force_reload: bool = False):
        """
        加载任务配置列表

        :param force_reload: 是否强制重新加载
        """
        # 如果已加载且不强制刷新，则跳过
        if self.data_loaded and not force_reload:
            print('DEBUG: 数据已缓存，跳过加载')
            return

        try:
            # 构建查询参数
            params = {}
            if self.search_task_name.value:
                params['task_name'] = self.search_task_name.value
            if self.search_task_type.value:
                params['task_type'] = self.search_task_type.value
            if self.search_is_enabled.value:
                params['is_enabled'] = self.search_is_enabled.value == 'true'

            # 调用后端 API
            response = await backend_api_service.get_bili_task_configs(params)

            if response and 'data' in response and 'items' in response['data']:
                self.task_configs = response['data']['items']
                print(f'DEBUG: 加载了 {len(self.task_configs)} 个任务配置')
                self._update_table()
                self.data_loaded = True  # 标记为已加载
            else:
                self.task_configs = []
                print('DEBUG: 没有任务配置数据')
                self._update_table()
                self.data_loaded = True
        except Exception as e:
            print(f'DEBUG: 加载任务配置异常: {str(e)}')
            self._show_snackbar(f'加载任务配置失败: {str(e)}', success=False)

    def _update_table(self):
        """更新数据表格"""
        print(f'DEBUG: _update_table 被调用，任务数量: {len(self.task_configs)}')
        if not self.task_configs:
            # 显示无数据提示
            self.table_container.content.controls = [self.empty_hint]
            print('DEBUG: 显示空数据提示')
        else:
            # 构建表格行
            self.data_table.rows.clear()
            for task_config in self.task_configs:
                task_type_map = {
                    'reply_my_message': '回复私信',
                    'reply_my_comment': '回复评论',
                    'send_to_others_comment': '评论区私信截流',
                }
                task_type_display = task_type_map.get(task_config.get('task_type', ''), task_config.get('task_type', ''))

                work_time = f"{task_config.get('start_time', '')}-{task_config.get('end_time', '')}"
                is_enabled = task_config.get('is_enabled', False)

                row = ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(str(task_config.get('id', '')))),
                        ft.DataCell(ft.Text(task_config.get('task_name', ''))),
                        ft.DataCell(ft.Text(task_type_display)),
                        ft.DataCell(ft.Text(work_time, size=12)),
                        ft.DataCell(
                            ft.Switch(
                                value=is_enabled,
                                active_color=ft.Colors.GREEN,
                                inactive_thumb_color=ft.Colors.GREY,
                                on_change=lambda e, tc=task_config: self.page.run_task(
                                    self.toggle_task_status, tc, e.control.value
                                ),
                            )
                        ),
                        ft.DataCell(ft.Text(str(task_config.get('run_count', 0)))),
                        ft.DataCell(ft.Row([
                            ft.IconButton(
                                icon=ft.Icons.PLAY_ARROW,
                                icon_size=18,
                                tooltip='立即执行',
                                icon_color=ft.Colors.GREEN,
                                on_click=lambda e, tc=task_config: self.page.run_task(self.execute_task_now, tc),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.HISTORY,
                                icon_size=18,
                                tooltip='查看执行记录',
                                icon_color=ft.Colors.BLUE,
                                on_click=lambda e, tc=task_config: self.show_execution_logs_dialog(tc),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.EDIT,
                                icon_size=18,
                                tooltip='编辑',
                                on_click=lambda e, tc=task_config: self.show_edit_dialog(tc),
                            ),
                            ft.IconButton(
                                icon=ft.Icons.DELETE,
                                icon_size=18,
                                tooltip='删除',
                                icon_color=ft.Colors.RED,
                                on_click=lambda e, tc=task_config: self.show_delete_confirm(tc),
                            ),
                        ], spacing=5)),
                    ]
                )
                self.data_table.rows.append(row)

            self.table_container.content.controls = [self.data_table]
            print(f'DEBUG: 表格已更新，共 {len(self.data_table.rows)} 行')

        self.page.update()
        print('DEBUG: page.update() 已调用')

    async def load_accounts(self):
        """加载账号列表"""
        try:
            accounts = await backend_api_service.get_account_list()
            if accounts:
                self.accounts = accounts
                # 更新下拉选项
                self.dlg_account_id.options = [
                    ft.dropdown.Option(str(account['id']), f"{account['account_name']} (ID: {account['id']})")
                    for account in accounts
                ]
        except Exception as e:
            print(f'加载账号列表失败: {e}')

    async def load_templates(self):
        """加载话术模板列表"""
        try:
            templates = await backend_api_service.get_template_list()
            if templates:
                # 清空并重新创建模板 Checkbox
                self.dlg_template_checkboxes = []
                self.dlg_template_container.controls.clear()

                for template in templates:
                    checkbox = ft.Checkbox(
                        label=f"{template['name']} (ID: {template['id']})",
                        value=False,
                        data=template['id'],  # 存储模板 ID
                    )
                    self.dlg_template_checkboxes.append(checkbox)
                    self.dlg_template_container.controls.append(checkbox)

                self.page.update()
        except Exception as e:
            print(f'加载话术模板列表失败: {e}')

    def _normalize_bvid(self, e):
        """
        自动提取并规范化 BVID

        :param e: 事件对象
        """
        import re

        input_value = self.dlg_work_id.value
        if not input_value:
            return

        # 匹配 BVID 格式（BV + 10位字符）
        bvid_pattern = r'(BV[a-zA-Z0-9]{10})'
        match = re.search(bvid_pattern, input_value)

        if match:
            # 提取到的 BVID
            bvid = match.group(1)
            self.dlg_work_id.value = bvid
            self.page.update()
        else:
            # 如果没有匹配到 BVID，保持原值
            pass

    def show_add_dialog(self):
        """显示新增任务对话框"""
        self.selected_task_config = None
        self._reset_dialog_fields()
        # 加载账号和模板列表
        self.page.run_task(self.load_accounts)
        self.page.run_task(self.load_templates)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text('新增任务配置'),
            content=ft.Container(
                content=ft.Column([
                    self.dlg_task_name,
                    self.dlg_task_type,
                    self.dlg_account_id,
                    self.dlg_work_id,
                    ft.Divider(),
                    ft.Text('工作时间设置', weight=ft.FontWeight.BOLD, size=14),
                    ft.Row([self.dlg_start_time, self.dlg_end_time], spacing=20),
                    ft.Row([self.dlg_rest_start_time, self.dlg_rest_end_time], spacing=20),
                    ft.Row([self.dlg_check_interval_min, self.dlg_check_interval_max], spacing=20),
                    ft.Divider(),
                    ft.Text('用户筛选条件', weight=ft.FontWeight.BOLD, size=14),
                    ft.Text('排除等级（勾选后将排除对应等级用户）', size=12, color="#666"),
                    ft.Container(height=5),
                    ft.Row([*self.dlg_exclude_levels], spacing=15),
                    ft.Container(height=10),
                    self.dlg_min_reg_days,
                    ft.Divider(),
                    ft.Text('其他设置', weight=ft.FontWeight.BOLD, size=14),
                    ft.Text('选择话术模板（可多选，系统将随机使用）', size=12, color="#666"),
                    ft.Container(height=5),
                    ft.Container(
                        content=self.dlg_template_container,
                        height=150,
                        border=ft.border.all(1, "#ddd"),
                        border_radius=5,
                        padding=10,
                    ),
                    ft.Container(height=10),
                    self.dlg_description,
                    self.dlg_is_enabled,
                ], spacing=15, scroll=ft.ScrollMode.AUTO),
                width=550,
                height=650,
            ),
            actions=[
                ft.TextButton('取消', on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton('保存', on_click=lambda e: self.page.run_task(self.save_task_config, dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def show_edit_dialog(self, task_config: dict):
        """
        显示编辑任务对话框

        :param task_config: 任务配置数据
        """
        self.selected_task_config = task_config
        # 加载账号和模板列表
        self.page.run_task(self.load_accounts)
        self.page.run_task(self.load_templates)
        self._fill_dialog_fields(task_config)

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text('编辑任务配置'),
            content=ft.Container(
                content=ft.Column([
                    self.dlg_task_name,
                    self.dlg_task_type,
                    self.dlg_account_id,
                    self.dlg_work_id,
                    ft.Divider(),
                    ft.Text('工作时间设置', weight=ft.FontWeight.BOLD, size=14),
                    ft.Row([self.dlg_start_time, self.dlg_end_time], spacing=20),
                    ft.Row([self.dlg_rest_start_time, self.dlg_rest_end_time], spacing=20),
                    ft.Row([self.dlg_check_interval_min, self.dlg_check_interval_max], spacing=20),
                    ft.Divider(),
                    ft.Text('用户筛选条件', weight=ft.FontWeight.BOLD, size=14),
                    ft.Text('排除等级（勾选后将排除对应等级用户）', size=12, color="#666"),
                    ft.Container(height=5),
                    ft.Row([*self.dlg_exclude_levels], spacing=15),
                    ft.Container(height=10),
                    self.dlg_min_reg_days,
                    ft.Divider(),
                    ft.Text('其他设置', weight=ft.FontWeight.BOLD, size=14),
                    ft.Text('选择话术模板（可多选，系统将随机使用）', size=12, color="#666"),
                    ft.Container(height=5),
                    ft.Container(
                        content=self.dlg_template_container,
                        height=150,
                        border=ft.border.all(1, "#ddd"),
                        border_radius=5,
                        padding=10,
                    ),
                    ft.Container(height=10),
                    self.dlg_description,
                    self.dlg_is_enabled,
                ], spacing=15, scroll=ft.ScrollMode.AUTO),
                width=550,
                height=650,
            ),
            actions=[
                ft.TextButton('取消', on_click=lambda e: self._close_dialog(dlg)),
                ft.ElevatedButton('保存', on_click=lambda e: self.page.run_task(self.save_task_config, dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    async def save_task_config(self, dlg):
        """
        保存任务配置

        :param dlg: 对话框对象
        """
        # 验证必填字段
        if not self.dlg_task_name.value:
            self._show_snackbar('任务名称不能为空', success=False)
            return
        if not self.dlg_task_type.value:
            self._show_snackbar('任务类型不能为空', success=False)
            return
        if not self.dlg_account_id.value:
            self._show_snackbar('执行账号不能为空', success=False)
            return

        # 构建请求数据
        # 注意：检查间隔前端是分钟，后端存储是秒，需要转换
        check_interval_min_minutes = int(self.dlg_check_interval_min.value or 5)
        check_interval_max_minutes = int(self.dlg_check_interval_max.value or 10)

        data = {
            'task_name': self.dlg_task_name.value,
            'task_type': self.dlg_task_type.value,
            'account_id': int(self.dlg_account_id.value),
            'start_time': self.dlg_start_time.value or '09:00:00',
            'end_time': self.dlg_end_time.value or '22:00:00',
            'check_interval_min': check_interval_min_minutes * 60,  # 转换为秒
            'check_interval_max': check_interval_max_minutes * 60,  # 转换为秒
            'is_enabled': self.dlg_is_enabled.value,
        }

        # 构建筛选条件 JSON
        filter_config = {}
        # 收集排除的等级
        exclude_levels = []
        for i, checkbox in enumerate(self.dlg_exclude_levels, start=1):
            if checkbox.value:
                exclude_levels.append(i)
        if exclude_levels:
            filter_config['exclude_levels'] = exclude_levels
        # 注册天数限制
        if self.dlg_min_reg_days.value:
            filter_config['min_reg_days'] = int(self.dlg_min_reg_days.value)

        if filter_config:
            import json

            data['filter_config'] = json.dumps(filter_config, ensure_ascii=False)

        # 可选字段
        if self.dlg_work_id.value:
            # 先规范化 BVID（如果用户输入了网址）
            import re

            input_value = self.dlg_work_id.value.strip()
            bvid_pattern = r'(BV[a-zA-Z0-9]{10})'
            match = re.search(bvid_pattern, input_value)

            if match:
                bvid = match.group(1)
                # 调用后端 API 获取或创建作品
                work = await backend_api_service.get_or_create_work_by_bvid(bvid)
                if work:
                    data['work_id'] = work['id']
                else:
                    self._show_snackbar(f'无法获取作品信息: {bvid}', success=False)
                    return
            else:
                self._show_snackbar('请输入有效的 BVID 或 B 站视频链接', success=False)
                return
        if self.dlg_rest_start_time.value:
            data['rest_start_time'] = self.dlg_rest_start_time.value
        if self.dlg_rest_end_time.value:
            data['rest_end_time'] = self.dlg_rest_end_time.value
        # 处理模板 ID - 从 Checkbox 列表收集
        template_ids = []
        for checkbox in self.dlg_template_checkboxes:
            if checkbox.value:
                template_ids.append(checkbox.data)  # data 存储的是模板 ID
        if template_ids:
            data['template_ids'] = str(template_ids)
        if self.dlg_description.value:
            data['description'] = self.dlg_description.value

        try:
            if self.selected_task_config:
                # 更新
                await backend_api_service.update_bili_task_config(self.selected_task_config['id'], data)
                self._show_snackbar('任务配置更新成功', success=True)
            else:
                # 新增
                await backend_api_service.create_bili_task_config(data)
                self._show_snackbar('任务配置创建成功', success=True)

            # 先重新加载数据，再关闭对话框
            await self.load_task_configs(force_reload=True)
            self._close_dialog(dlg)
        except Exception as e:
            self._show_snackbar(f'保存失败: {str(e)}', success=False)

    def show_delete_confirm(self, task_config: dict):
        """
        显示删除确认对话框

        :param task_config: 任务配置数据
        """
        def confirm_delete(e):
            self.page.run_task(self.delete_task_config, task_config['id'], confirm_dlg)

        confirm_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text('确认删除'),
            content=ft.Text(f"确定要删除任务 '{task_config.get('task_name', '')}' 吗？"),
            actions=[
                ft.TextButton('取消', on_click=lambda e: self._close_dialog(confirm_dlg)),
                ft.ElevatedButton('删除', on_click=confirm_delete, bgcolor=ft.Colors.RED, color=ft.Colors.WHITE),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.overlay.append(confirm_dlg)
        confirm_dlg.open = True
        self.page.update()

    async def delete_task_config(self, task_config_id: int, dlg):
        """
        删除任务配置

        :param task_config_id: 任务配置 ID
        :param dlg: 对话框对象
        """
        try:
            await backend_api_service.delete_bili_task_config(task_config_id)
            self._show_snackbar('任务配置删除成功', success=True)
            self._close_dialog(dlg)
            await self.load_task_configs(force_reload=True)
        except Exception as e:
            self._show_snackbar(f'删除失败: {str(e)}', success=False)

    def show_execution_logs_dialog(self, task_config: dict):
        """
        显示任务执行记录对话框

        :param task_config: 任务配置数据
        """
        # 创建执行记录表格
        execution_logs_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text('ID', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('开始时间', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('执行状态', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('发送成功', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('错误信息', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('操作', weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            column_spacing=20,
            heading_row_height=50,
            data_row_min_height=50,
        )

        # 执行记录容器
        logs_container = ft.Container(
            content=ft.ListView(
                controls=[execution_logs_table],
                spacing=0,
                padding=10,
                expand=True,
            ),
            width=900,
            height=500,
        )

        # 创建对话框
        logs_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.HISTORY, color=ft.Colors.BLUE),
                ft.Text(f'任务执行记录 - {task_config.get("task_name", "")}'),
            ]),
            content=logs_container,
            actions=[
                ft.TextButton('关闭', on_click=lambda e: self._close_dialog(logs_dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 加载执行记录数据
        async def load_execution_logs():
            try:
                response = await backend_api_service.get_task_execution_logs(
                    task_config_id=task_config.get('id'), page=1, size=50
                )

                # 增加更安全的检查
                if not response:
                    logs_container.content = ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.ERROR_OUTLINE, size=80, color='#f44336'),
                            ft.Text('加载执行记录失败', size=16, color='#f44336'),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        alignment=ft.alignment.center,
                        expand=True,
                    )
                    self.page.update()
                    return

                data = response.get('data')
                if not data or not isinstance(data, dict):
                    logs_container.content = ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.ERROR_OUTLINE, size=80, color='#f44336'),
                            ft.Text('加载执行记录失败: 数据格式错误', size=16, color='#f44336'),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        alignment=ft.alignment.center,
                        expand=True,
                    )
                    self.page.update()
                    return

                logs = data.get('items', [])
                execution_logs_table.rows.clear()

                if not logs:
                    # 显示无数据提示
                    logs_container.content = ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.INBOX, size=80, color='#9e9e9e'),
                            ft.Text('暂无执行记录', size=16, color='#9e9e9e'),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        alignment=ft.alignment.center,
                        expand=True,
                    )
                else:
                    for log in logs:
                        # 状态映射（后端返回的是大写）
                        status_map = {
                            'SUCCESS': ('成功', ft.Colors.GREEN),
                            'FAILED': ('失败', ft.Colors.RED),
                            'RUNNING': ('运行中', ft.Colors.BLUE),
                            # 兼容小写
                            'success': ('成功', ft.Colors.GREEN),
                            'failed': ('失败', ft.Colors.RED),
                            'running': ('运行中', ft.Colors.BLUE),
                        }
                        status_text, status_color = status_map.get(
                            log.get('execution_status', ''), ('未知', ft.Colors.GREY)
                        )

                        # 格式化时间
                        import datetime

                        exec_time = log.get('start_time', '')
                        if exec_time:
                            try:
                                dt = datetime.datetime.fromisoformat(exec_time.replace('Z', '+00:00'))
                                exec_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except Exception:
                                pass

                        row = ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(str(log.get('id', '')))),
                                ft.DataCell(ft.Text(exec_time, size=12)),
                                ft.DataCell(
                                    ft.Container(
                                        content=ft.Text(status_text, color=ft.Colors.WHITE, size=12),
                                        bgcolor=status_color,
                                        padding=ft.padding.symmetric(horizontal=10, vertical=5),
                                        border_radius=5,
                                    )
                                ),
                                ft.DataCell(ft.Text(str(log.get('send_success', 0)))),
                                ft.DataCell(
                                    ft.Text(
                                        (error_msg := log.get('error_message') or '')[:50] + ('...' if len(error_msg) > 50 else ''),
                                        size=12,
                                        color=ft.Colors.RED if error_msg else None,
                                    )
                                ),
                                ft.DataCell(
                                    ft.IconButton(
                                        icon=ft.Icons.VISIBILITY,
                                        icon_size=18,
                                        tooltip='查看操作记录',
                                        icon_color=ft.Colors.BLUE,
                                        on_click=lambda e, log_id=log.get('id'): self.show_operation_records_dialog(log_id),
                                    )
                                ),
                            ]
                        )
                        execution_logs_table.rows.append(row)

                self.page.update()
            except Exception as e:
                print(f'加载执行记录失败: {e}')
                logs_container.content = ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ERROR_OUTLINE, size=80, color='#f44336'),
                        ft.Text(f'加载失败: {str(e)}', size=16, color='#f44336'),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.center,
                    expand=True,
                )
                self.page.update()

        # 显示对话框并加载数据
        self.page.overlay.append(logs_dlg)
        logs_dlg.open = True
        self.page.update()
        self.page.run_task(load_execution_logs)

    def show_operation_records_dialog(self, execution_log_id: int):
        """
        显示某次任务执行的操作记录详情

        :param execution_log_id: 执行记录 ID
        """
        # 创建操作记录表格
        operation_records_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text('MID', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('操作类型', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('发送内容', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('发送结果', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('创建时间', weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            column_spacing=20,
            heading_row_height=50,
            data_row_min_height=50,
        )

        # 操作记录容器
        records_container = ft.Container(
            content=ft.ListView(
                controls=[operation_records_table],
                spacing=0,
                padding=10,
                expand=True,
            ),
            width=900,
            height=500,
        )

        # 创建对话框
        records_dlg = ft.AlertDialog(
            modal=True,
            title=ft.Row([
                ft.Icon(ft.Icons.LIST_ALT, color=ft.Colors.BLUE),
                ft.Text(f'操作记录详情 - 执行 ID: {execution_log_id}'),
            ]),
            content=records_container,
            actions=[
                ft.TextButton('关闭', on_click=lambda e: self._close_dialog(records_dlg)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 加载操作记录数据
        async def load_operation_records():
            try:
                response = await backend_api_service.get_duplicate_check_list(
                    execution_log_id=execution_log_id, page=1, size=100
                )

                if not response:
                    records_container.content = ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.ERROR_OUTLINE, size=80, color='#f44336'),
                            ft.Text('加载操作记录失败', size=16, color='#f44336'),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        alignment=ft.alignment.center,
                        expand=True,
                    )
                    self.page.update()
                    return

                records = response.get('items', [])
                operation_records_table.rows.clear()

                if not records:
                    records_container.content = ft.Container(
                        content=ft.Column([
                            ft.Icon(ft.Icons.INBOX, size=80, color='#9e9e9e'),
                            ft.Text('暂无操作记录', size=16, color='#9e9e9e'),
                        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                        alignment=ft.alignment.center,
                        expand=True,
                    )
                else:
                    # 操作类型映射
                    operation_type_map = {
                        'at': '@',
                        'comment': '评论',
                        'message': '私信',
                        'blacklist': '黑名单',
                    }

                    for record in records:
                        # 格式化时间
                        import datetime

                        created_time = record.get('created_time', '')
                        if created_time:
                            try:
                                dt = datetime.datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                                created_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                            except Exception:
                                pass

                        # 发送结果颜色
                        send_result = record.get('send_result', '') or ''
                        result_color = ft.Colors.GREEN if send_result == 'SUCCESS' else ft.Colors.RED if send_result else None

                        row = ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(record.get('mid', ''))),
                                ft.DataCell(ft.Text(operation_type_map.get(record.get('operation_type', ''), record.get('operation_type', '')))),
                                ft.DataCell(
                                    ft.Container(
                                        content=ft.Text(
                                            (content := record.get('send_content', '') or '')[:30] + ('...' if len(content) > 30 else ''),
                                            size=12,
                                        ),
                                        tooltip=record.get('send_content', '') or '-',
                                    )
                                ),
                                ft.DataCell(
                                    ft.Container(
                                        content=ft.Text(
                                            send_result[:30] + ('...' if len(send_result) > 30 else ''),
                                            size=12,
                                            color=result_color,
                                        ),
                                        tooltip=send_result or '-',
                                    )
                                ),
                                ft.DataCell(ft.Text(created_time, size=12)),
                            ]
                        )
                        operation_records_table.rows.append(row)

                self.page.update()
            except Exception as e:
                print(f'加载操作记录失败: {e}')
                records_container.content = ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.ERROR_OUTLINE, size=80, color='#f44336'),
                        ft.Text(f'加载失败: {str(e)}', size=16, color='#f44336'),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    alignment=ft.alignment.center,
                    expand=True,
                )
                self.page.update()

        # 显示对话框并加载数据
        self.page.overlay.append(records_dlg)
        records_dlg.open = True
        self.page.update()
        self.page.run_task(load_operation_records)

    async def clear_and_reload(self):
        """清空筛选条件并重新加载"""
        self.search_task_name.value = ''
        self.search_task_type.value = None
        self.search_is_enabled.value = None
        await self.load_task_configs(force_reload=True)

    async def toggle_task_status(self, task_config: dict, new_status: bool):
        """
        切换任务启用/禁用状态

        :param task_config: 任务配置数据
        :param new_status: 新状态
        """
        try:
            # 更新任务状态
            update_data = {'is_enabled': new_status}
            success = await backend_api_service.update_bili_task_config(task_config['id'], update_data)

            if success:
                status_text = '启用' if new_status else '禁用'
                self._show_snackbar(f'任务已{status_text}', success=True)
                # 重新加载任务列表
                await self.load_task_configs(force_reload=True)
            else:
                self._show_snackbar('更新状态失败', success=False)
                # 恢复开关状态
                await self.load_task_configs(force_reload=True)
        except Exception as e:
            self._show_snackbar(f'更新状态失败: {str(e)}', success=False)
            # 恢复开关状态
            await self.load_task_configs(force_reload=True)

    async def execute_task_now(self, task_config: dict):
        """
        立即执行任务

        :param task_config: 任务配置数据
        """
        try:
            # 显示执行中提示
            self._show_snackbar(f'正在执行任务: {task_config.get("task_name")}...', success=True)

            # 调用后端API执行任务
            success = await backend_api_service.execute_task_config_now(task_config['id'])

            if success:
                self._show_snackbar('任务执行成功！', success=True)
                # 重新加载任务列表（更新运行次数）
                await self.load_task_configs(force_reload=True)
            else:
                self._show_snackbar('任务执行失败', success=False)
        except Exception as e:
            error_msg = str(e)
            if '正在执行中' in error_msg:
                self._show_snackbar('任务正在执行中，请稍后再试', success=False)
            else:
                self._show_snackbar(f'执行失败: {error_msg}', success=False)

    def _reset_dialog_fields(self):
        """重置对话框字段"""
        self.dlg_task_name.value = ''
        self.dlg_task_type.value = None
        self.dlg_account_id.value = None
        self.dlg_work_id.value = ''
        self.dlg_start_time.value = '09:00:00'
        self.dlg_end_time.value = '22:00:00'
        self.dlg_rest_start_time.value = ''
        self.dlg_rest_end_time.value = ''
        self.dlg_check_interval_min.value = '5'
        self.dlg_check_interval_max.value = '10'
        # 重置等级筛选
        for checkbox in self.dlg_exclude_levels:
            checkbox.value = False
        self.dlg_min_reg_days.value = ''
        # 重置模板选择
        for checkbox in self.dlg_template_checkboxes:
            checkbox.value = False
        self.dlg_description.value = ''
        self.dlg_is_enabled.value = True

    def _fill_dialog_fields(self, task_config: dict):
        """
        填充对话框字段

        :param task_config: 任务配置数据
        """
        self.dlg_task_name.value = task_config.get('task_name', '')
        self.dlg_task_type.value = task_config.get('task_type', '')
        self.dlg_account_id.value = str(task_config.get('account_id', ''))
        # work_id 处理：前端显示提示，需要用户重新输入 BVID
        if task_config.get('work_id'):
            self.dlg_work_id.value = f"作品 ID: {task_config.get('work_id')} (请重新输入 BVID)"
        else:
            self.dlg_work_id.value = ''
        self.dlg_start_time.value = task_config.get('start_time', '09:00:00')
        self.dlg_end_time.value = task_config.get('end_time', '22:00:00')
        self.dlg_rest_start_time.value = task_config.get('rest_start_time', '') or ''
        self.dlg_rest_end_time.value = task_config.get('rest_end_time', '') or ''

        # 将秒转换为分钟显示
        check_interval_min_seconds = task_config.get('check_interval_min', 300)
        check_interval_max_seconds = task_config.get('check_interval_max', 600)
        self.dlg_check_interval_min.value = str(check_interval_min_seconds // 60)
        self.dlg_check_interval_max.value = str(check_interval_max_seconds // 60)

        # 解析 filter_config JSON 并填充可视化字段
        filter_config_str = task_config.get('filter_config', '')
        if filter_config_str:
            try:
                import json

                filter_config = json.loads(filter_config_str)
                # 填充排除等级
                exclude_levels = filter_config.get('exclude_levels', [])
                for i, checkbox in enumerate(self.dlg_exclude_levels, start=1):
                    checkbox.value = i in exclude_levels
                # 填充注册天数
                min_reg_days = filter_config.get('min_reg_days')
                self.dlg_min_reg_days.value = str(min_reg_days) if min_reg_days else ''
            except Exception:
                # 解析失败，重置为默认值
                for checkbox in self.dlg_exclude_levels:
                    checkbox.value = False
                self.dlg_min_reg_days.value = ''
        else:
            # 无筛选配置，重置为默认值
            for checkbox in self.dlg_exclude_levels:
                checkbox.value = False
            self.dlg_min_reg_days.value = ''

        # 解析模板 ID 并勾选对应的 Checkbox
        if task_config.get('template_ids'):
            try:
                # template_ids 是字符串 "[1, 2, 3]"
                import ast

                template_ids_list = ast.literal_eval(task_config.get('template_ids', '[]'))
                # 遍历 Checkbox，勾选对应的模板
                for checkbox in self.dlg_template_checkboxes:
                    checkbox.value = checkbox.data in template_ids_list
            except Exception:
                # 解析失败，取消所有勾选
                for checkbox in self.dlg_template_checkboxes:
                    checkbox.value = False
        else:
            # 无模板配置，取消所有勾选
            for checkbox in self.dlg_template_checkboxes:
                checkbox.value = False

        self.dlg_description.value = task_config.get('description', '') or ''
        self.dlg_is_enabled.value = task_config.get('is_enabled', True)

    def _close_dialog(self, dlg):
        """
        关闭对话框

        :param dlg: 对话框对象
        """
        dlg.open = False
        self.page.update()

    def _show_snackbar(self, message: str, success: bool = True):
        """
        显示提示条

        :param message: 提示消息
        :param success: 是否成功（True 绿色，False 红色）
        """
        snackbar = ft.SnackBar(
            content=ft.Text(message),
            bgcolor=ft.Colors.GREEN if success else ft.Colors.RED,
        )
        self.page.snack_bar = snackbar
        snackbar.open = True
        self.page.update()
