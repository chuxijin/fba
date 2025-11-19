#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""话术管理组件"""
import flet as ft

from my_app.services.api.backend_api import backend_api_service


class TemplateManagementTab:
    """话术管理 Tab"""

    def __init__(self, page: ft.Page):
        """
        初始化话术管理 Tab

        :param page: Flet 页面对象
        """
        self.page = page
        self.templates = []
        self.categories = []
        self.selected_template = None
        self.data_loaded = False  # 数据加载标志
        self.categories_loaded = False  # 分类数据加载标志

        # 搜索筛选组件
        self.search_name = ft.TextField(
            label='模板名称',
            width=200,
            on_submit=lambda e: self.page.run_task(self.load_templates),
        )

        self.search_type = ft.Dropdown(
            label='模板类型',
            width=150,
            options=[
                ft.dropdown.Option('comment', '评论'),
                ft.dropdown.Option('message', '私信'),
            ],
            on_change=lambda e: self.page.run_task(self.load_templates),
        )

        self.search_status = ft.Dropdown(
            label='状态',
            width=150,
            options=[
                ft.dropdown.Option('1', '启用'),
                ft.dropdown.Option('0', '禁用'),
            ],
            on_change=lambda e: self.page.run_task(self.load_templates),
        )

        # 数据表格
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text('ID', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('模板名称', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('类型', weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text('内容预览', weight=ft.FontWeight.BOLD)),
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
        self.dlg_name = ft.TextField(label='模板名称*', width=450)
        self.dlg_type = ft.Dropdown(
            label='模板类型*',
            width=450,
            options=[
                ft.dropdown.Option('comment', '评论'),
                ft.dropdown.Option('message', '私信'),
            ],
        )
        self.dlg_content = ft.TextField(
            label='话术内容*',
            hint_text='支持多行内容',
            multiline=True,
            min_lines=5,
            max_lines=10,
            width=450,
        )
        self.dlg_keywords = ft.TextField(
            label='关键词（JSON 格式）',
            hint_text='例如：["关键词1", "关键词2"]',
            width=450,
        )
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

        # 新增/编辑对话框
        self.edit_dialog = ft.AlertDialog(
            title=ft.Text('新增话术'),
            content=ft.Container(
                content=ft.Column([
                    self.dlg_name,
                    self.dlg_type,
                    self.dlg_content,
                    self.dlg_keywords,
                    self.dlg_status,
                    self.dlg_category,
                ], tight=True, scroll=ft.ScrollMode.AUTO),
                width=500,
                height=550,
            ),
            actions=[
                ft.TextButton('取消', on_click=self.close_edit_dialog),
                ft.ElevatedButton('保存', on_click=self.save_template),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 删除确认对话框
        self.delete_dialog = ft.AlertDialog(
            title=ft.Text('确认删除'),
            content=ft.Text('确定要删除该话术吗？此操作不可恢复！'),
            actions=[
                ft.TextButton('取消', on_click=self.close_delete_dialog),
                ft.ElevatedButton('删除', on_click=self.confirm_delete, bgcolor="#ef5350"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 分类管理对话框
        self.category_tree_container = ft.Container(
            content=ft.Column([], scroll=ft.ScrollMode.AUTO),
            width=400,
            height=400,
        )
        self.category_dialog = ft.AlertDialog(
            title=ft.Text('分类管理'),
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.ElevatedButton(
                            '新增根分类',
                            icon=ft.Icons.ADD,
                            on_click=lambda e: self.open_category_edit_dialog(None),
                        ),
                        ft.ElevatedButton(
                            '刷新',
                            icon=ft.Icons.REFRESH,
                            on_click=lambda e: self.page.run_task(self.load_category_tree),
                        ),
                    ], spacing=10),
                    ft.Divider(height=10),
                    self.category_tree_container,
                ]),
                width=450,
                height=500,
            ),
            actions=[
                ft.TextButton('关闭', on_click=self.close_category_dialog),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 分类编辑对话框
        self.cat_dlg_name = ft.TextField(label='分类名称*', width=300)
        self.cat_dlg_description = ft.TextField(label='描述', width=300)
        self.cat_dlg_sort = ft.TextField(label='排序', width=300, value='0')
        self.cat_dlg_status = ft.Dropdown(
            label='状态',
            width=300,
            options=[
                ft.dropdown.Option('1', '启用'),
                ft.dropdown.Option('0', '禁用'),
            ],
            value='1',
        )
        self.selected_category = None
        self.selected_parent_id = None

        self.category_edit_dialog = ft.AlertDialog(
            title=ft.Text('新增分类'),
            content=ft.Container(
                content=ft.Column([
                    self.cat_dlg_name,
                    self.cat_dlg_description,
                    self.cat_dlg_sort,
                    self.cat_dlg_status,
                ], tight=True),
                width=350,
                height=300,
            ),
            actions=[
                ft.TextButton('取消', on_click=self.close_category_edit_dialog),
                ft.ElevatedButton('保存', on_click=self.save_category),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 分类删除确认对话框
        self.category_delete_dialog = ft.AlertDialog(
            title=ft.Text('确认删除'),
            content=ft.Text('确定要删除该分类吗？'),
            actions=[
                ft.TextButton('取消', on_click=self.close_category_delete_dialog),
                ft.ElevatedButton('删除', on_click=self.confirm_delete_category, bgcolor="#ef5350"),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

    def build(self) -> ft.Container:
        """构建话术管理 Tab 内容"""
        return ft.Container(
            content=ft.Column([
                # 顶部操作栏
                ft.Container(
                    content=ft.Row([
                        self.search_name,
                        self.search_type,
                        self.search_status,
                        ft.ElevatedButton(
                            '搜索',
                            icon=ft.Icons.SEARCH,
                            on_click=lambda e: self.page.run_task(self.load_templates),
                        ),
                        ft.ElevatedButton(
                            '重置',
                            icon=ft.Icons.REFRESH,
                            on_click=self.reset_search,
                        ),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            '新增话术',
                            icon=ft.Icons.ADD,
                            on_click=self.open_add_dialog,
                        ),
                        ft.ElevatedButton(
                            '管理分类',
                            icon=ft.Icons.FOLDER,
                            on_click=self.open_category_dialog,
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

    async def load_templates(self, force_reload: bool = False):
        """
        加载话术列表

        :param force_reload: 是否强制重新加载
        """
        # 如果已加载且不强制刷新，则跳过
        if self.data_loaded and not force_reload:
            print('DEBUG: 话术数据已缓存，跳过加载')
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
        name = self.search_name.value or None
        template_type = self.search_type.value or None
        status = int(self.search_status.value) if self.search_status.value else None

        # 调用后端 API
        self.templates = await backend_api_service.get_template_list(
            name=name, template_type=template_type, status=status
        )

        # 更新表格
        self.update_table()
        self.data_loaded = True  # 标记为已加载

    def update_table(self):
        """更新数据表格"""
        self.table_container.content.controls.clear()

        if not self.templates:
            # 显示空状态
            self.table_container.content.controls.append(self.empty_hint)
        else:
            # 显示数据表格
            self.data_table.rows.clear()
            for template in self.templates:
                # 类型映射
                type_map = {'comment': '评论', 'message': '私信'}
                type_text = type_map.get(template.get('template_type', ''), template.get('template_type', ''))

                # 内容预览（截取前30字符，保留换行提示）
                content = template.get('content', '') or ''
                content_preview = content.replace('\n', '↵')[:30]
                if len(content) > 30:
                    content_preview += '...'

                self.data_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(str(template.get('id', '')))),
                            ft.DataCell(ft.Text(template.get('name', ''))),
                            ft.DataCell(ft.Text(type_text)),
                            ft.DataCell(ft.Text(content_preview)),
                            ft.DataCell(
                                ft.Chip(
                                    label=ft.Text('启用' if template.get('status') == 1 else '禁用'),
                                    bgcolor="#c8e6c9" if template.get('status') == 1 else "#ffcdd2",
                                )
                            ),
                            ft.DataCell(ft.Text(template.get('created_time', '')[:19] if template.get('created_time') else '-')),
                            ft.DataCell(
                                ft.Row([
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT,
                                        tooltip='编辑',
                                        on_click=lambda e, tpl=template: self.open_edit_dialog(tpl),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE,
                                        tooltip='删除',
                                        icon_color="#ef5350",
                                        on_click=lambda e, tpl=template: self.open_delete_dialog(tpl),
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
        self.search_name.value = ''
        self.search_type.value = None
        self.search_status.value = None
        self.page.run_task(self.load_templates)

    async def load_categories(self, force_reload: bool = False):
        """
        加载分类列表用于下拉框

        :param force_reload: 是否强制重新加载
        """
        if self.categories_loaded and not force_reload:
            print('DEBUG: 话术分类数据已缓存，跳过加载')
            return

        self.categories = await backend_api_service.get_category_list()
        self.dlg_category.options = [
            ft.dropdown.Option(str(cat['id']), cat['name']) for cat in self.categories
        ]
        self.categories_loaded = True
        self.page.update()

    def open_add_dialog(self, e):
        """打开新增对话框"""
        self.selected_template = None
        self.edit_dialog.title = ft.Text('新增话术')

        # 清空表单
        self.dlg_name.value = ''
        self.dlg_type.value = None
        self.dlg_content.value = ''
        self.dlg_keywords.value = ''
        self.dlg_status.value = '1'
        self.dlg_category.value = None

        # 加载分类
        self.page.run_task(self.load_categories)

        self.page.overlay.append(self.edit_dialog)
        self.edit_dialog.open = True
        self.page.update()

    def open_edit_dialog(self, template: dict):
        """打开编辑对话框"""
        self.selected_template = template
        self.edit_dialog.title = ft.Text('编辑话术')

        # 填充表单
        self.dlg_name.value = template.get('name', '')
        self.dlg_type.value = template.get('template_type', '')
        self.dlg_content.value = template.get('content', '') or ''
        self.dlg_keywords.value = template.get('keywords', '') or ''
        self.dlg_status.value = str(template.get('status', 1))
        self.dlg_category.value = str(template.get('category_id')) if template.get('category_id') else None

        # 加载分类
        self.page.run_task(self.load_categories)

        self.page.overlay.append(self.edit_dialog)
        self.edit_dialog.open = True
        self.page.update()

    def close_edit_dialog(self, e):
        """关闭编辑对话框"""
        self.edit_dialog.open = False
        self.page.update()

    def save_template(self, e):
        """保存话术"""
        # 验证必填项
        if not self.dlg_name.value:
            self._show_snackbar('请填写模板名称', error=True)
            return

        if not self.dlg_type.value:
            self._show_snackbar('请选择模板类型', error=True)
            return

        if not self.dlg_content.value:
            self._show_snackbar('请填写话术内容', error=True)
            return

        # 构建数据
        template_data = {
            'name': self.dlg_name.value,
            'template_type': self.dlg_type.value,
            'content': self.dlg_content.value,
            'keywords': self.dlg_keywords.value or None,
            'status': int(self.dlg_status.value),
            'category_id': int(self.dlg_category.value) if self.dlg_category.value else None,
        }

        # 调用保存任务
        if self.selected_template:
            # 更新
            self.page.run_task(self.do_update_template, self.selected_template['id'], template_data)
        else:
            # 新增
            self.page.run_task(self.do_create_template, template_data)

        self.close_edit_dialog(e)

    async def do_create_template(self, template_data: dict):
        """执行创建话术"""
        success = await backend_api_service.create_template(template_data)
        if success:
            self._show_snackbar('话术创建成功')
            await self.load_templates(force_reload=True)
        else:
            self._show_snackbar('话术创建失败', error=True)

    async def do_update_template(self, pk: int, template_data: dict):
        """执行更新话术"""
        success = await backend_api_service.update_template(pk, template_data)
        if success:
            self._show_snackbar('话术更新成功')
            await self.load_templates(force_reload=True)
        else:
            self._show_snackbar('话术更新失败', error=True)

    def open_delete_dialog(self, template: dict):
        """打开删除确认对话框"""
        self.selected_template = template
        self.delete_dialog.content = ft.Text(f'确定要删除话术 "{template.get("name")}" 吗？此操作不可恢复！')

        self.page.overlay.append(self.delete_dialog)
        self.delete_dialog.open = True
        self.page.update()

    def close_delete_dialog(self, e):
        """关闭删除对话框"""
        self.delete_dialog.open = False
        self.page.update()

    def confirm_delete(self, e):
        """确认删除"""
        if self.selected_template:
            self.page.run_task(self.do_delete_template, self.selected_template['id'])
        self.close_delete_dialog(e)

    async def do_delete_template(self, pk: int):
        """执行删除话术"""
        success = await backend_api_service.delete_template(pk)
        if success:
            self._show_snackbar('话术删除成功')
            await self.load_templates(force_reload=True)
        else:
            self._show_snackbar('话术删除失败', error=True)

    # ==================== 分类管理 ====================

    def open_category_dialog(self, e):
        """打开分类管理对话框"""
        self.page.run_task(self.load_category_tree)
        self.page.overlay.append(self.category_dialog)
        self.category_dialog.open = True
        self.page.update()

    def close_category_dialog(self, e):
        """关闭分类管理对话框"""
        self.category_dialog.open = False
        self.page.update()

    async def load_category_tree(self):
        """加载分类树"""
        tree_data = await backend_api_service.get_category_tree()
        self.category_tree_container.content.controls.clear()

        if not tree_data:
            self.category_tree_container.content.controls.append(
                ft.Container(
                    content=ft.Text('暂无分类', color="#9e9e9e"),
                    alignment=ft.alignment.center,
                    padding=20,
                )
            )
        else:
            # 构建树形视图
            tree_controls = self._build_tree_controls(tree_data, 0)
            self.category_tree_container.content.controls.extend(tree_controls)

        self.page.update()

    def _build_tree_controls(self, nodes: list, level: int) -> list:
        """
        构建树形控件

        :param nodes: 节点列表
        :param level: 层级
        :return:
        """
        controls = []
        for node in nodes:
            # 缩进
            indent = level * 20

            # 节点行
            node_row = ft.Container(
                content=ft.Row([
                    ft.Icon(
                        ft.Icons.FOLDER if node.get('children') else ft.Icons.ARTICLE,
                        size=20,
                        color="#ffa726" if node.get('children') else "#42a5f5",
                    ),
                    ft.Text(node.get('name', ''), expand=True),
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        icon_size=18,
                        tooltip='添加子分类',
                        on_click=lambda e, n=node: self.open_category_edit_dialog(n['id']),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT,
                        icon_size=18,
                        tooltip='编辑',
                        on_click=lambda e, n=node: self.open_category_edit_dialog(None, n),
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        icon_size=18,
                        icon_color="#ef5350",
                        tooltip='删除',
                        on_click=lambda e, n=node: self.open_category_delete_dialog(n),
                    ),
                ], spacing=5),
                padding=ft.padding.only(left=indent, top=5, bottom=5),
            )
            controls.append(node_row)

            # 递归处理子节点
            if node.get('children'):
                child_controls = self._build_tree_controls(node['children'], level + 1)
                controls.extend(child_controls)

        return controls

    def open_category_edit_dialog(self, parent_id: int | None, category: dict | None = None):
        """打开分类编辑对话框"""
        self.selected_parent_id = parent_id
        self.selected_category = category

        if category:
            # 编辑模式
            self.category_edit_dialog.title = ft.Text('编辑分类')
            self.cat_dlg_name.value = category.get('name', '')
            self.cat_dlg_description.value = category.get('description', '') or ''
            self.cat_dlg_sort.value = str(category.get('sort', 0))
            self.cat_dlg_status.value = str(category.get('status', 1))
        else:
            # 新增模式
            self.category_edit_dialog.title = ft.Text('新增分类')
            self.cat_dlg_name.value = ''
            self.cat_dlg_description.value = ''
            self.cat_dlg_sort.value = '0'
            self.cat_dlg_status.value = '1'

        self.page.overlay.append(self.category_edit_dialog)
        self.category_edit_dialog.open = True
        self.page.update()

    def close_category_edit_dialog(self, e):
        """关闭分类编辑对话框"""
        self.category_edit_dialog.open = False
        self.page.update()

    def save_category(self, e):
        """保存分类"""
        if not self.cat_dlg_name.value:
            self._show_snackbar('请填写分类名称', error=True)
            return

        category_data = {
            'name': self.cat_dlg_name.value,
            'description': self.cat_dlg_description.value or None,
            'sort': int(self.cat_dlg_sort.value or 0),
            'status': int(self.cat_dlg_status.value),
            'parent_id': self.selected_parent_id,
        }

        if self.selected_category:
            # 更新
            self.page.run_task(self.do_update_category, self.selected_category['id'], category_data)
        else:
            # 新增
            self.page.run_task(self.do_create_category, category_data)

        self.close_category_edit_dialog(e)

    async def do_create_category(self, category_data: dict):
        """执行创建分类"""
        success = await backend_api_service.create_category(category_data)
        if success:
            self._show_snackbar('分类创建成功')
            await self.load_category_tree()
            # 刷新分类下拉框选项
            await self.load_categories()
        else:
            self._show_snackbar('分类创建失败', error=True)

    async def do_update_category(self, pk: int, category_data: dict):
        """执行更新分类"""
        success = await backend_api_service.update_category(pk, category_data)
        if success:
            self._show_snackbar('分类更新成功')
            await self.load_category_tree()
            # 刷新分类下拉框选项
            await self.load_categories()
        else:
            self._show_snackbar('分类更新失败', error=True)

    def open_category_delete_dialog(self, category: dict):
        """打开分类删除确认对话框"""
        self.selected_category = category
        self.category_delete_dialog.content = ft.Text(f'确定要删除分类 "{category.get("name")}" 吗？')

        self.page.overlay.append(self.category_delete_dialog)
        self.category_delete_dialog.open = True
        self.page.update()

    def close_category_delete_dialog(self, e):
        """关闭分类删除对话框"""
        self.category_delete_dialog.open = False
        self.page.update()

    def confirm_delete_category(self, e):
        """确认删除分类"""
        if self.selected_category:
            self.page.run_task(self.do_delete_category, self.selected_category['id'])
        self.close_category_delete_dialog(e)

    async def do_delete_category(self, pk: int):
        """执行删除分类"""
        success = await backend_api_service.delete_category(pk)
        if success:
            self._show_snackbar('分类删除成功')
            await self.load_category_tree()
        else:
            self._show_snackbar('分类删除失败', error=True)

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
