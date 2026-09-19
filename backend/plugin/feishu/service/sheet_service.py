import re
import time

from typing import Any, Literal

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.plugin.feishu.service.client import FeishuClient
from backend.plugin.feishu.utils.a1 import build_cell_range, parse_cell_range, with_sheet

# 子表列表缓存有效期（秒）
#
# 每次操作都要先把「子表名称 → sheet_id」解析出来，而该解析的实现在 `_resolve_sheet()` 里
# 是「先拉全量子表列表、再逐个匹配」——**即使传入的已经是 sheet_id 也照样要拉一次**。
# 实测 sheets/query 单次约 280ms，约占一次读写操作的 50% 耗时。
# 表结构由本服务自己维护（建表 / 重命名 / 插入行都会主动失效缓存），
# 因此短期内复用是安全的；外部手工改子表结构最多滞后该秒数，且滞后只会让旧名称继续
# 解析为同一个 sheet_id（目标仍然正确），不会写错表。
SHEET_LIST_CACHE_TTL: float = 60.0

# 水平对齐映射
H_ALIGN: dict[str, int] = {'left': 0, 'center': 1, 'right': 2}
# 垂直对齐映射
V_ALIGN: dict[str, int] = {'top': 0, 'middle': 1, 'bottom': 2}
# 下拉选项默认胶囊配色（按选项数循环取用）
DROPDOWN_COLORS: tuple[str, ...] = (
    '#bacefd',
    '#fed4a4',
    '#b1e8fc',
    '#f8c7d4',
    '#c9e7c0',
    '#d8ccf2',
    '#fbe3a1',
    '#c2e2ee',
    '#f5c9b6',
    '#d6d6d6',
)

# 新增行时样式继承来源
InheritStyle = Literal['before', 'after', 'none']
# 行列尺寸调整维度
DimensionType = Literal['rows', 'columns']


class FeishuSheetService:
    """飞书电子表格服务"""

    def __init__(self) -> None:
        self.client = FeishuClient()
        # workbook_token -> (子表列表, 写入缓存时的 monotonic 时间戳)
        self._sheet_cache: dict[str, tuple[list[dict[str, Any]], float]] = {}

    # ---------- 缓存 ----------

    def invalidate_sheet_cache(self, workbook_token: str | None = None) -> None:
        """
        失效子表列表缓存

        任何会改变子表数量或名称的操作（新建子表 / 重命名子表 / 插入行导致网格扩容）
        都必须调用本方法，否则后续操作会读到过期的子表元信息。

        :param workbook_token: 表格 token，为空时清空全部缓存
        :return:
        """
        if workbook_token is None:
            self._sheet_cache.clear()
            return
        self._sheet_cache.pop(workbook_token, None)

    async def _cached_sheets(self, workbook_token: str) -> list[dict[str, Any]]:
        """
        带缓存的子表列表查询

        :param workbook_token: 表格 token
        :return:
        """
        now = time.monotonic()
        cached = self._sheet_cache.get(workbook_token)
        if cached is not None and now - cached[1] < SHEET_LIST_CACHE_TTL:
            return cached[0]

        sheets = await self._list_sheets(workbook_token)
        self._sheet_cache[workbook_token] = (sheets, now)
        return sheets

    # ---------- 定位 ----------

    @staticmethod
    def _extract_token(text: str, marker: str) -> str:
        """
        从链接中截取指定路径后的 token

        :param text: 链接
        :param marker: 路径标记，如 /sheets/
        :return:
        """
        tail = text.split(marker, 1)[1]
        return re.split(r'[?#/]', tail, maxsplit=1)[0]

    @staticmethod
    def extract_sheet_id(url: str) -> str | None:
        """
        从链接的 ?sheet= 参数中取出子表 id

        :param url: 表格链接
        :return:
        """
        match = re.search(r'[?&]sheet=([A-Za-z0-9]+)', url)
        return match.group(1) if match else None

    async def resolve_workbook_token(self, workbook: str) -> str:
        """
        把 /sheets/ 链接、/wiki/ 知识库链接或裸 token 统一解析为 spreadsheet_token

        :param workbook: 表格链接或 token
        :return:
        """
        if '/wiki/' in workbook:
            node_token = self._extract_token(workbook, '/wiki/')
            data = await self.client.request(
                'GET',
                '/wiki/v2/spaces/get_node',
                params={'token': node_token, 'obj_type': 'wiki'},
            )
            node_info = data.get('node') or {}
            obj_token = node_info.get('obj_token')
            if not obj_token:
                raise errors.NotFoundError(msg=f'无法从知识库节点解析电子表格: {workbook}')
            return str(obj_token)

        if '/sheets/' in workbook:
            return self._extract_token(workbook, '/sheets/')

        return workbook.strip()

    async def _list_sheets(self, workbook_token: str) -> list[dict[str, Any]]:
        """
        按 spreadsheet_token 获取子表列表

        :param workbook_token: 表格 token
        :return:
        """
        data = await self.client.request('GET', f'/sheets/v3/spreadsheets/{workbook_token}/sheets/query')
        return data.get('sheets') or []

    async def list_sheets(self, workbook: str | None = None) -> list[dict[str, Any]]:
        """
        获取子表列表

        :param workbook: 表格链接或 token，为空时使用 FEISHU_SHEET_URL
        :return:
        """
        book = (workbook or settings.FEISHU_SHEET_URL or '').strip()
        if not book:
            raise errors.ForbiddenError(msg='飞书表格未指定，请传入 workbook 或配置 FEISHU_SHEET_URL')

        workbook_token = await self.resolve_workbook_token(book)
        return await self._cached_sheets(workbook_token)

    async def _resolve_sheet(self, workbook_token: str, sheet: str | None) -> str:
        """
        按子表名称或 sheet_id 解析出 sheet_id，为空时取第一个子表

        :param workbook_token: 表格 token
        :param sheet: 子表名称或 sheet_id
        :return:
        """
        sheets = await self._cached_sheets(workbook_token)
        if not sheets:
            raise errors.NotFoundError(msg='电子表格中不存在任何子表')

        if sheet:
            for item in sheets:
                if item.get('sheet_id') == sheet or item.get('title') == sheet:
                    return str(item['sheet_id'])
            raise errors.NotFoundError(msg=f'子表不存在: {sheet}')

        return str(sheets[0]['sheet_id'])

    async def resolve_target(self, workbook: str | None, sheet: str | None = None) -> tuple[str, str]:
        """
        解析目标表格与子表

        :param workbook: 表格链接或 token，为空时使用 FEISHU_SHEET_URL
        :param sheet: 子表名称或 sheet_id，为空时按链接参数 / FEISHU_SHEET_NAME / FEISHU_SHEET_ID / 首个子表 回退
        :return: (spreadsheet_token, sheet_id)
        """
        book = (workbook or settings.FEISHU_SHEET_URL or '').strip()
        if not book:
            raise errors.ForbiddenError(msg='飞书表格未指定，请传入 workbook 或配置 FEISHU_SHEET_URL')

        workbook_token = await self.resolve_workbook_token(book)
        target = sheet or self.extract_sheet_id(book) or settings.FEISHU_SHEET_NAME or settings.FEISHU_SHEET_ID
        sheet_id = await self._resolve_sheet(workbook_token, target or None)
        return workbook_token, sheet_id

    # ---------- 子表结构 ----------

    async def create_sheet(self, *, workbook: str | None = None, title: str, index: int | None = None) -> str:
        """
        新建子表

        :param workbook: 表格链接或 token
        :param title: 子表名称
        :param index: 插入位置（0-based），为空则追加到最后
        :return: 新子表 id
        """
        if not title.strip():
            raise errors.RequestError(msg='子表名称不能为空')

        book = (workbook or settings.FEISHU_SHEET_URL or '').strip()
        if not book:
            raise errors.ForbiddenError(msg='飞书表格未指定，请传入 workbook 或配置 FEISHU_SHEET_URL')
        workbook_token = await self.resolve_workbook_token(book)

        properties: dict[str, Any] = {'title': title}
        if index is not None:
            properties['index'] = index

        data = await self.client.request(
            'POST',
            f'/sheets/v2/spreadsheets/{workbook_token}/sheets_batch_update',
            json_body={'requests': [{'addSheet': {'properties': properties}}]},
        )
        replies = data.get('replies') or []
        sheet_id = ''
        if replies:
            added = (replies[0].get('addSheet') or {}).get('properties') or {}
            sheet_id = str(added.get('sheetId') or '')
        # 新建子表会改变子表列表，必须失效缓存，否则后续操作找不到这张新表
        self.invalidate_sheet_cache(workbook_token)
        log.info(f'[Feishu] 新建子表完成 title={title} sheet_id={sheet_id}')
        return sheet_id

    async def rename_sheet(self, *, workbook: str | None = None, sheet: str, title: str) -> None:
        """
        重命名子表

        :param workbook: 表格链接或 token
        :param sheet: 原名称或 sheet_id
        :param title: 新名称
        :return:
        """
        if not title.strip():
            raise errors.RequestError(msg='子表名称不能为空')

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        await self.client.request(
            'PUT',
            f'/sheets/v2/spreadsheets/{workbook_token}/sheets_batch_update',
            json_body={'requests': [{'updateSheet': {'properties': {'sheetId': sheet_id, 'title': title}}}]},
        )
        # 重命名会改变「名称 → sheet_id」的映射，必须失效缓存
        self.invalidate_sheet_cache(workbook_token)
        log.info(f'[Feishu] 重命名子表完成 sheet_id={sheet_id} title={title}')

    async def find_sheet_by_title(self, *, workbook: str | None = None, title: str) -> str | None:
        """
        按名称查找子表 id

        :param workbook: 表格链接或 token
        :param title: 子表名称
        :return:
        """
        sheets = await self.list_sheets(workbook)
        for item in sheets:
            if item.get('title') == title:
                return str(item['sheet_id'])
        return None

    async def get_grid_row_count(self, *, workbook: str | None = None, sheet: str | None = None) -> int:
        """
        获取子表已分配的网格行数（含表头行）

        这是「数据行数的天然上界」：向网格之外的行写入会失败，因此数据行数必定不超过它。
        该值来自子表元信息（`grid_properties.row_count`），命中 `_cached_sheets` 缓存时零额外请求，
        可以用来替代写死的最大扫描行数。

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :return: 网格行数，取不到时返回 0
        """
        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        sheets = await self._cached_sheets(workbook_token)
        target = next((item for item in sheets if str(item.get('sheet_id')) == sheet_id), None)
        grid = (target or {}).get('grid_properties') or {}
        return int(grid.get('row_count') or 0)

    # ---------- 读写 ----------

    @staticmethod
    def _extract_updates(data: dict[str, Any]) -> dict[str, Any]:
        """
        兼容不同接口的返回结构，统一取出更新结果

        `values` 接口直接返回更新字段，`style` 等接口会把它们包在 updates 里

        :param data: 飞书接口返回的 data
        :return:
        """
        return data.get('updates') or data

    async def _read_values(self, workbook_token: str, sheet_id: str, cell_range: str) -> list[list[Any]]:
        """
        按 token 读取单元格

        :param workbook_token: 表格 token
        :param sheet_id: 子表 id
        :param cell_range: 单元格范围，如 A1:F3
        :return:
        """
        data = await self.client.request(
            'GET',
            f'/sheets/v2/spreadsheets/{workbook_token}/values/{with_sheet(sheet_id, cell_range)}',
        )
        value_range = data.get('valueRange') or {}
        return value_range.get('values') or []

    async def _write_values(
        self,
        workbook_token: str,
        sheet_id: str,
        cell_range: str,
        values: list[list[Any]],
    ) -> dict[str, Any]:
        """
        按 token 写入单元格

        :param workbook_token: 表格 token
        :param sheet_id: 子表 id
        :param cell_range: 单元格范围，如 A1:F3
        :param values: 二维数据
        :return:
        """
        data = await self.client.request(
            'PUT',
            f'/sheets/v2/spreadsheets/{workbook_token}/values',
            json_body={'valueRange': {'range': with_sheet(sheet_id, cell_range), 'values': values}},
        )
        return self._extract_updates(data)

    async def read(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        cell_range: str = 'A1:Z1000',
    ) -> list[list[Any]]:
        """
        读取单元格数据

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param cell_range: 单元格范围，如 A1:F10
        :return:
        """
        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        return await self._read_values(workbook_token, sheet_id, cell_range)

    async def _last_row(
        self,
        workbook_token: str,
        sheet_id: str,
        column: str = 'A',
        max_row: int = 5000,
    ) -> int:
        """
        从下往上查找最后一个非空行

        :param workbook_token: 表格 token
        :param sheet_id: 子表 id
        :param column: 用于判断的列字母
        :param max_row: 最大探测行数
        :return:
        """
        values = await self._read_values(workbook_token, sheet_id, f'{column}1:{column}{max_row}')
        for index in range(len(values) - 1, -1, -1):
            row = values[index]
            cell = row[0] if row else None
            if cell not in (None, ''):
                return index + 1
        return 0

    async def find_last_row(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        column: str = 'A',
        max_row: int = 5000,
    ) -> int:
        """
        查找最后一个非空行

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param column: 用于判断的列字母
        :param max_row: 最大探测行数
        :return:
        """
        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        return await self._last_row(workbook_token, sheet_id, column, max_row)

    async def write(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        cell_range: str,
        values: list[list[Any]],
    ) -> dict[str, Any]:
        """
        写入指定范围

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param cell_range: 单元格范围，如 A1:F3（不含子表前缀）
        :param values: 二维数据
        :return:
        """
        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        updates = await self._write_values(workbook_token, sheet_id, cell_range, values)
        log.info(f'[Feishu] 写入完成 sheet_id={sheet_id} range={cell_range} rows={len(values)}')
        return updates

    async def append(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        rows: list[list[Any]],
        header_rows: int = 1,
    ) -> dict[str, Any]:
        """
        追加数据到数据区末尾（不会影响表头行）

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param rows: 二维数据
        :param header_rows: 表头行数，追加时会跳过这些行
        :return:
        """
        if not rows:
            raise errors.RequestError(msg='追加数据不能为空')

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        column_count = max(len(row) for row in rows)
        start_row = max(await self._last_row(workbook_token, sheet_id), header_rows) + 1
        cell_range = build_cell_range(start_row, len(rows), column_count)
        updates = await self._write_values(workbook_token, sheet_id, cell_range, rows)
        log.info(f'[Feishu] 追加完成 sheet_id={sheet_id} range={cell_range} rows={len(rows)}')
        return {'sheet_id': sheet_id, 'range': cell_range, 'updates': updates}

    async def batch_append(self, *, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        批量追加，同一工作簿内的多个子表会合并为一次请求

        :param jobs: 追加任务列表，每项包含 workbook / sheet / rows / header_rows
        :return:
        """
        grouped: dict[str, list[dict[str, Any]]] = {}
        metas: dict[str, list[str]] = {}

        for job in jobs:
            rows = job.get('rows') or []
            if not rows:
                continue

            workbook_token, sheet_id = await self.resolve_target(job.get('workbook'), job.get('sheet'))
            header_rows = int(job.get('header_rows') or 0)
            column_count = max(len(row) for row in rows)
            start_row = max(await self._last_row(workbook_token, sheet_id), header_rows) + 1
            cell_range = build_cell_range(start_row, len(rows), column_count)

            grouped.setdefault(workbook_token, []).append({'range': with_sheet(sheet_id, cell_range), 'values': rows})
            metas.setdefault(workbook_token, []).append(f'{sheet_id}!{cell_range}')

        results: list[dict[str, Any]] = []
        for workbook_token, value_ranges in grouped.items():
            data = await self.client.request(
                'POST',
                f'/sheets/v2/spreadsheets/{workbook_token}/values_batch_update',
                json_body={'valueRanges': value_ranges},
            )
            log.info(f'[Feishu] 批量追加完成 workbook={workbook_token} sheets={metas[workbook_token]}')
            results.append({
                'workbook_token': workbook_token,
                'ranges': metas[workbook_token],
                'responses': data.get('responses') or [],
                'revision': data.get('revision'),
            })

        return results

    async def insert_rows(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        position: int,
        count: int,
        inherit_style: InheritStyle = 'after',
    ) -> None:
        """
        在指定位置插入空行（新行插入到 position 行之前，表头不会被顶掉）

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param position: 插入位置（1-based 行号）
        :param count: 插入行数
        :param inherit_style: 样式继承来源
        :return:
        """
        if position < 1:
            raise errors.RequestError(msg='插入位置必须大于 0')
        if count < 1:
            raise errors.RequestError(msg='插入行数必须大于 0')

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        await self.client.request(
            'POST',
            f'/sheets/v2/spreadsheets/{workbook_token}/insert_dimension_range',
            json_body={
                'dimension': {
                    'sheetId': sheet_id,
                    'majorDimension': 'ROWS',
                    'startIndex': position - 1,
                    'endIndex': position - 1 + count,
                    'inheritStyle': inherit_style.upper(),
                }
            },
        )
        # 插入行会改变网格行数（grid_properties.row_count），而该值被
        # `_ensure_grid_rows()` 用来判断是否需要扩容，缓存必须失效
        self.invalidate_sheet_cache(workbook_token)
        log.info(f'[Feishu] 插入行完成 sheet_id={sheet_id} position={position} count={count}')

    # ---------- 样式与下拉 ----------

    @staticmethod
    def _build_font(
        *,
        bold: bool | None,
        italic: bool | None,
    ) -> dict[str, Any]:
        """
        构造字体样式

        注意：飞书 API 只接受 bold / italic 位于 font 子对象内，
        fontSize 必须放在样式对象顶层（放这里会报 code=90204），故本函数不处理字号。

        :param bold: 是否加粗
        :param italic: 是否斜体
        :return:
        """
        pairs = (('bold', bold), ('italic', italic))
        return {key: value for key, value in pairs if value is not None}

    @staticmethod
    def build_style(
        *,
        bold: bool | None = None,
        italic: bool | None = None,
        font_size: int | None = None,
        font_color: str | None = None,
        background_color: str | None = None,
        horizontal_alignment: str | None = None,
        vertical_alignment: str | None = None,
        border_type: str | None = None,
        border_color: str | None = None,
    ) -> dict[str, Any]:
        """
        构造飞书单元格样式对象

        :param bold: 是否加粗
        :param italic: 是否斜体
        :param font_size: 字号（9~36）
        :param font_color: 字体颜色，如 #FFFFFF
        :param background_color: 背景色，如 #4472C4
        :param horizontal_alignment: 水平对齐 left/center/right
        :param vertical_alignment: 垂直对齐 top/middle/bottom
        :param border_type: 边框类型，如 FULL_BORDER
        :param border_color: 边框颜色
        :return:
        """
        style: dict[str, Any] = {}

        font = FeishuSheetService._build_font(bold=bold, italic=italic)
        if font:
            style['font'] = font
        if font_size is not None:
            # 飞书 API 要求 fontSize 位于样式对象顶层，放进 font 子对象会报 code=90204
            style['fontSize'] = font_size
        if font_color:
            style['foreColor'] = font_color
        if background_color:
            style['backColor'] = background_color
        if horizontal_alignment:
            style['hAlign'] = H_ALIGN.get(horizontal_alignment, 0)
        if vertical_alignment:
            style['vAlign'] = V_ALIGN.get(vertical_alignment, 1)
        if border_type:
            style['borderType'] = border_type
        if border_color:
            style['borderColor'] = border_color

        return style

    async def set_style(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        cell_range: str,
        style: dict[str, Any],
    ) -> dict[str, Any]:
        """
        设置单元格样式（不改变单元格的值与公式）

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param cell_range: 单元格范围，如 A1:F1
        :param style: 样式对象，可用 build_style 构造
        :return:
        """
        if not style:
            raise errors.RequestError(msg='样式不能为空')

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        data = await self.client.request(
            'PUT',
            f'/sheets/v2/spreadsheets/{workbook_token}/style',
            json_body={'appendStyle': {'range': with_sheet(sheet_id, cell_range), 'style': style}},
        )
        log.info(f'[Feishu] 设置样式完成 sheet_id={sheet_id} range={cell_range}')
        return self._extract_updates(data)

    async def set_dropdown(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        cell_range: str,
        options: list[str],
        multiple: bool = False,
        highlight: bool = True,
        colors: list[str] | None = None,
    ) -> None:
        """
        为单元格范围设置下拉列表

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param cell_range: 单元格范围，如 E2:E1000
        :param options: 下拉选项，不能包含英文逗号
        :param multiple: 是否允许多选
        :param highlight: 是否开启选项胶囊高亮
        :param colors: 选项配色，数量需与 options 一致，开启高亮时必填
        :return:
        """
        if not options:
            raise errors.RequestError(msg='下拉选项不能为空')

        invalid = [item for item in options if ',' in item]
        if invalid:
            raise errors.RequestError(msg=f'下拉选项不能包含英文逗号: {", ".join(invalid)}')

        option_props: dict[str, Any] = {'multipleValues': multiple, 'highlightValidData': highlight}
        if highlight:
            palette = colors or []
            if palette and len(palette) != len(options):
                raise errors.RequestError(msg='下拉配色数量必须与选项数量一致')
            option_props['colors'] = palette or [
                DROPDOWN_COLORS[index % len(DROPDOWN_COLORS)] for index in range(len(options))
            ]

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        await self.client.request(
            'POST',
            f'/sheets/v2/spreadsheets/{workbook_token}/dataValidation',
            json_body={
                'range': with_sheet(sheet_id, cell_range),
                'dataValidationType': 'list',
                'dataValidation': {'conditionValues': options, 'options': option_props},
            },
        )
        log.info(f'[Feishu] 设置下拉完成 sheet_id={sheet_id} range={cell_range} options={len(options)}')

    async def get_dropdown(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        cell_range: str,
    ) -> list[dict[str, Any]]:
        """
        查询下拉列表配置

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param cell_range: 单元格范围，如 E1:E10
        :return:
        """
        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        data = await self.client.request(
            'GET',
            f'/sheets/v2/spreadsheets/{workbook_token}/dataValidation',
            params={'range': with_sheet(sheet_id, cell_range)},
        )
        return data.get('dataValidations') or []

    async def delete_dropdown(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        cell_range: str,
    ) -> None:
        """
        删除下拉列表配置

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param cell_range: 单元格范围，如 E1:E10
        :return:
        """
        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        await self.client.request(
            'DELETE',
            f'/sheets/v2/spreadsheets/{workbook_token}/dataValidation',
            params={'range': with_sheet(sheet_id, cell_range)},
        )
        log.info(f'[Feishu] 删除下拉完成 sheet_id={sheet_id} range={cell_range}')

    async def resize(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        dimension: DimensionType = 'columns',
        start: int = 1,
        end: int = 1,
        size: int = 100,
    ) -> None:
        """
        调整行高或列宽

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param dimension: rows 行高 / columns 列宽
        :param start: 起始序号（1-based，含）
        :param end: 结束序号（1-based，含）
        :param size: 像素值
        :return:
        """
        if start < 1 or end < start:
            raise errors.RequestError(msg='行列序号不合法')
        if size < 1:
            raise errors.RequestError(msg='尺寸必须大于 0')

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        await self.client.request(
            'PUT',
            f'/sheets/v2/spreadsheets/{workbook_token}/dimension_range',
            json_body={
                'dimension': {
                    'sheetId': sheet_id,
                    'majorDimension': 'ROWS' if dimension == 'rows' else 'COLUMNS',
                    'startIndex': start,
                    'endIndex': end,
                },
                'dimensionProperties': {'fixedSize': size},
            },
        )
        log.info(f'[Feishu] 调整尺寸完成 sheet_id={sheet_id} dimension={dimension} {start}-{end} size={size}')

    async def set_dimension_visible(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        dimension: DimensionType = 'columns',
        start: int = 1,
        end: int = 1,
        visible: bool = False,
    ) -> None:
        """
        显示或隐藏行 / 列

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param dimension: rows 行 / columns 列
        :param start: 起始序号（1-based，含）
        :param end: 结束序号（1-based，含）
        :param visible: 是否可见
        :return:
        """
        if start < 1 or end < start:
            raise errors.RequestError(msg='行列序号不合法')

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        await self.client.request(
            'PUT',
            f'/sheets/v2/spreadsheets/{workbook_token}/dimension_range',
            json_body={
                'dimension': {
                    'sheetId': sheet_id,
                    'majorDimension': 'ROWS' if dimension == 'rows' else 'COLUMNS',
                    'startIndex': start,
                    'endIndex': end,
                },
                'dimensionProperties': {'visible': visible},
            },
        )
        log.info(f'[Feishu] 设置可见性完成 sheet_id={sheet_id} dimension={dimension} {start}-{end} visible={visible}')

    async def clear_values(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        cell_range: str,
    ) -> None:
        """
        清空指定范围的内容（飞书无公开的清空接口，这里以空字符串覆盖实现）

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param cell_range: 单元格范围，如 A2:G100
        :return:
        """
        (
            start_row,
            row_count,
            column_count,
            start_column,
        ) = parse_cell_range(cell_range)

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        target_range = build_cell_range(start_row, row_count, column_count, start_column)
        empty_values = [[''] * column_count for _ in range(row_count)]
        await self.client.request(
            'PUT',
            f'/sheets/v2/spreadsheets/{workbook_token}/values',
            json_body={'valueRange': {'range': with_sheet(sheet_id, target_range), 'values': empty_values}},
        )
        log.info(f'[Feishu] 清空范围完成 sheet_id={sheet_id} range={target_range}')

    async def batch_write(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        ranges: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        一次请求写入多个区域（同一子表内合并为一次调用）

        :param workbook: 表格链接或 token
        :param sheet: 子表名称或 sheet_id
        :param ranges: 区域列表，每项为 {'cell_range': 'A2:G3', 'values': [[...]]}
        :return:
        """
        if not ranges:
            return {}

        workbook_token, sheet_id = await self.resolve_target(workbook, sheet)
        value_ranges = [
            {'range': with_sheet(sheet_id, item['cell_range']), 'values': item['values']} for item in ranges
        ]
        data = await self.client.request(
            'POST',
            f'/sheets/v2/spreadsheets/{workbook_token}/values_batch_update',
            json_body={'valueRanges': value_ranges},
        )
        log.info(f'[Feishu] 批量写入完成 sheet_id={sheet_id} ranges={len(value_ranges)}')
        return data


feishu_sheet_service = FeishuSheetService()
