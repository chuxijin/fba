#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书导出「只写变化行」自检

覆盖两处关键逻辑，都是纯内存验证 —— **不连数据库、不连飞书、不写任何真实表格**：

  1. 值对比：与表格现状一致的行不写，只有真正变化的行才写（含 B 列超链接回读归一化）
  2. 装饰按需：表头样式 / 下拉只在首次、选项变化、数据区扩张时重建，其余轮次零请求

手法：假表继承真实服务类，只覆盖网络 IO，保留 `build_style` 等纯函数；
DB 侧三个取数方法（分类 ID 集合 / 资源列表 / 分类名映射）打桩返回固定数据。

使用方法:
    python scripts/check_feishu_sync_diff.py          # 打印全部断言结果
    python scripts/check_feishu_sync_diff.py -q       # 只打印失败项与总计
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys

from datetime import datetime
from datetime import timezone as dt_timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from backend.common.log import log

# 断言里会大量触发正常告警（如「数据已铺满读取上界」），这里静音以保持输出干净
log.remove()

from backend.app.mydrive.model.feishu import FeishuSheetConfig  # noqa: E402
from backend.app.mydrive.service import feishu_export_service as svc_module  # noqa: E402
from backend.plugin.feishu.service.sheet_service import FeishuSheetService  # noqa: E402

OUT: list[str] = []
PASS = 0
FAIL = 0

ROW_RE = re.compile(r'^[A-Z]+(\d+):[A-Z]+\d+$')
SHEET = '真题获取'
COLUMN_COUNT = 7


def check(name: str, condition: Any, detail: str = '') -> None:
    """记录一条断言（condition 按真值判断）"""
    global PASS, FAIL
    if condition:
        PASS += 1
        OUT.append(f'[PASS] {name}')
    else:
        FAIL += 1
        OUT.append(f'[FAIL] {name} :: {detail}')


# ---------------------------------------------------------------- 假表


class FakeSheetService(FeishuSheetService):
    """只把网络 IO 换成内存实现，其余（build_style 等纯函数）沿用真实代码"""

    def __init__(self, rows: list[list[Any]] | None = None, grid_rows: int = 100) -> None:
        self.client = None
        self._sheet_cache: dict[str, Any] = {}
        self.rows: list[list[Any]] = [list(row) for row in (rows or [])]
        self.grid_rows = grid_rows
        self.calls: list[str] = []

    # --- 调用记录 ---
    def reset(self) -> None:
        self.calls = []

    def count(self, prefix: str) -> int:
        return sum(1 for item in self.calls if item.startswith(prefix))

    def _apply(self, cell_range: str, values: list[list[Any]]) -> None:
        match = ROW_RE.match(cell_range)
        if not match:
            raise AssertionError(f'假表收到无法解析的范围: {cell_range}')
        start = int(match.group(1))
        for offset, row in enumerate(values):
            index = start - 2 + offset
            while len(self.rows) <= index:
                self.rows.append([''] * COLUMN_COUNT)
            self.rows[index] = list(row)

    # --- 结构 ---
    async def list_sheets(self, workbook: str | None = None) -> list[dict[str, Any]]:
        return [{'sheet_id': 's1', 'title': SHEET, 'grid_properties': {'row_count': self.grid_rows}}]

    async def resolve_target(self, workbook: str | None = None, sheet: str | None = None) -> tuple[str, str]:
        return 'BOOKTOKEN', 's1'

    async def get_grid_row_count(self, *, workbook: str | None = None, sheet: str | None = None) -> int:
        return self.grid_rows

    async def find_sheet_by_title(self, *, workbook: str | None = None, title: str) -> str | None:
        return 's1' if title == SHEET else None

    async def create_sheet(self, *, workbook: str | None = None, title: str, index: int | None = None) -> str:
        self.calls.append(f'create_sheet:{title}')
        return 's1'

    async def rename_sheet(self, *, workbook: str | None = None, sheet: str, title: str) -> None:
        self.calls.append(f'rename_sheet:{title}')

    async def insert_rows(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        position: int,
        count: int,
        inherit_style: str = 'after',
    ) -> None:
        self.calls.append(f'insert_rows:count={count}')
        index = max(position - 2, 0)
        for _ in range(count):
            self.rows.insert(index, [''] * COLUMN_COUNT)

    # --- 读写 ---
    async def read(
        self, *, workbook: str | None = None, sheet: str | None = None, cell_range: str = 'A1:Z1000'
    ) -> list[list[Any]]:
        self.calls.append('read')
        return [list(row) for row in self.rows]

    async def write(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        cell_range: str,
        values: list[list[Any]],
    ) -> dict[str, Any]:
        self.calls.append(f'write:{cell_range}')
        self._apply(cell_range, values)
        return {}

    async def batch_write(
        self, *, workbook: str | None = None, sheet: str | None = None, ranges: list[dict[str, Any]]
    ) -> dict[str, Any]:
        self.calls.append(f'batch_write:{len(ranges)}')
        for item in ranges:
            self._apply(item['cell_range'], item['values'])
        return {}

    async def clear_values(self, *, workbook: str | None = None, sheet: str | None = None, cell_range: str) -> None:
        self.calls.append(f'clear_values:{cell_range}')

    async def resize(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        dimension: str = 'columns',
        start: int = 1,
        end: int = 1,
        size: int = 100,
    ) -> None:
        self.calls.append(f'resize:{dimension}{start}')

    async def set_dimension_visible(
        self,
        *,
        workbook: str | None = None,
        sheet: str | None = None,
        dimension: str = 'columns',
        start: int = 1,
        end: int = 1,
        visible: bool = False,
    ) -> None:
        self.calls.append(f'set_dimension_visible:{dimension}{start}={visible}')

    # --- 样式与下拉 ---
    async def set_style(
        self, *, workbook: str | None = None, sheet: str | None = None, cell_range: str, style: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append(f'set_style:{cell_range}')
        return {}

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
        self.calls.append(f'set_dropdown:{cell_range}|{",".join(options)}')


# ---------------------------------------------------------------- 假数据


class FakeShare:
    """分享记录桩"""

    def __init__(self, url: str, share_status: str = 'active', deleted: int = 0) -> None:
        self.share_url = url
        self.share_status = share_status
        self.deleted = deleted


class FakeResource:
    """资源桩（字段与 is_public_visible 用到的完全对齐）"""

    def __init__(
        self,
        rid: int,
        title: str,
        category_id: int,
        url: str | None,
        updated: datetime,
        *,
        deleted: int = 0,
        status: str = 'enabled',
        audit_status: str = 'approved',
        share_status: str = 'active',
    ) -> None:
        self.id = rid
        self.title = title
        self.category_id = category_id
        self.updated_time = updated
        self.created_time = updated
        self.deleted = deleted
        self.status = status
        self.audit_status = audit_status
        self.share = FakeShare(url, share_status) if url is not None else None


T0 = datetime(2026, 9, 19, 20, 0, 0, tzinfo=dt_timezone.utc)
NAMES = {10: '行测', 11: '申论'}


def make_config() -> FeishuSheetConfig:
    """构造一份未落库的导出配置（id 手动指定，够签名使用）"""
    config = FeishuSheetConfig(
        name='公考',
        app_code='gongkao',
        sheet_url='https://example.feishu.cn/sheets/BOOKTOKEN?sheet=s1',
        category_type='knowledge_point',
        sheet_map={'zhen_ti': SHEET},
        category_options=['行测', '申论', '常识'],
        source_weights={'网络获取': 1, '用户推荐': 1, '店铺购买': 1},
        paid_sheets=[SHEET],
    )
    config.id = 1
    return config


class Ctx:
    """把服务、假表、假资源组装成一个可反复跑的场景"""

    def __init__(self) -> None:
        self.config = make_config()
        self.fake = FakeSheetService()
        svc_module.feishu_sheet_service = self.fake
        self.service = svc_module.MyDriveFeishuExportService()
        # 以下三个打桩方法必须是协程：服务侧是以 await 调用的，这里只换返回值
        self.resources: list[FakeResource] = []

        async def fake_category_ids(*, config: FeishuSheetConfig, db: Any) -> set[int]:  # noqa: RUF029
            return {10, 11}

        async def fake_load_resources(  # noqa: RUF029
            *,
            db: Any,
            resource_types: list[str],
            category_ids: set[int],
            known_ids: set[int] | None = None,
        ) -> list[FakeResource]:
            return list(self.resources)

        async def fake_names(*, config: FeishuSheetConfig, db: Any) -> dict[int, str]:  # noqa: RUF029
            return dict(NAMES)

        self.service._load_app_category_ids = fake_category_ids
        self.service._load_resources = fake_load_resources
        self.service._load_category_names = fake_names

    async def run(self) -> dict[str, Any]:
        """跑一轮 sync_sheet"""
        return await self.service.sync_sheet(db=None, config=self.config, sheet=SHEET, resource_types=['zhen_ti'])

    def build(self, resource: FakeResource, source: str, status_label: str = '有效') -> list[Any]:
        """用被测代码自身组装一行，作为「表已与库一致」的基准"""
        return self.service._build_row(resource, NAMES.get(resource.category_id, ''), source, status_label)

    def seed(self, rows: list[list[Any]]) -> None:
        self.fake.rows = [list(row) for row in rows]

    def find_row(self, resource_id: int) -> list[Any] | None:
        for row in self.fake.rows:
            if len(row) > 6 and str(row[6]) == str(resource_id):
                return row
        return None


# ---------------------------------------------------------------- 断言


async def main(*, quiet: bool = False) -> int:
    """执行全部断言并输出报告"""
    ctx = Ctx()
    r1 = FakeResource(101, '行测真题A', 10, 'https://a/1', T0)
    r2 = FakeResource(102, '申论真题B', 11, 'https://a/2', T0)
    r3 = FakeResource(103, '常识真题C', 10, 'https://a/3', T0)
    ctx.resources = [r1, r2, r3]
    ctx.seed([
        ctx.build(r1, '网络获取'),
        ctx.build(r2, '用户推荐'),
        ctx.build(r3, '网络获取'),
    ])

    # --- 1) 首轮：表已与库一致 -> 不写任何行，但装饰一次 ---
    ctx.fake.reset()
    result = await ctx.run()
    check('1.1 一致时 updated=0', result['updated'] == 0, str(result))
    check('1.2 一致时 inserted=0', result['inserted'] == 0, str(result))
    check('1.3 一致时零 batch_write', ctx.fake.count('batch_write') == 0, str(ctx.fake.calls))
    check('1.4 一致时零 insert_rows', ctx.fake.count('insert_rows') == 0, str(ctx.fake.calls))
    check('1.5 只读一次表（无重复读）', ctx.fake.count('read') == 1, str(ctx.fake.calls))
    check('1.6 首轮装饰表头样式', ctx.fake.count('set_style') == 2, str(ctx.fake.calls))
    check('1.7 首轮装饰三个下拉', ctx.fake.count('set_dropdown') == 3, str(ctx.fake.calls))

    # --- 2) 第二轮无变化：连装饰都不再做（核心优化） ---
    ctx.fake.reset()
    result = await ctx.run()
    check('2.1 无变化整轮只有 1 次读', ctx.fake.calls == ['read'], str(ctx.fake.calls))
    check('2.2 无变化 updated=0', result['updated'] == 0, str(result))
    check('2.3 装饰不重复执行', ctx.fake.count('set_style') + ctx.fake.count('set_dropdown') == 0, str(ctx.fake.calls))

    # --- 3) 只改一条：仅写那一行 ---
    r2.share = FakeShare('https://a/2-new')
    ctx.fake.reset()
    result = await ctx.run()
    check('3.1 只更新 1 行', result['updated'] == 1, str(result))
    check('3.2 单次 batch_write 只含 1 个区域', ctx.fake.count('batch_write:1') == 1, str(ctx.fake.calls))
    check('3.3 新链接已落表', (ctx.find_row(102) or [''])[1] == 'https://a/2-new')
    check('3.4 未变化的行内容保持原样', (ctx.find_row(101) or [''])[1] == 'https://a/1')

    # --- 4) 人工改来源：不被覆盖 ---
    row1 = ctx.find_row(101)
    assert row1 is not None
    row1[5] = '店铺购买'
    ctx.fake.reset()
    result = await ctx.run()
    check('4.1 来源人工痕迹不被覆盖（零写入）', result['updated'] == 0, str(result))
    check('4.2 来源仍是人工值', (ctx.find_row(101) or [''] * 6)[5] == '店铺购买')

    # --- 5) 新增一条可见资源：插到表头下方 ---
    r4 = FakeResource(104, '新增资料D', 11, 'https://a/4', T0)
    ctx.resources = [r1, r2, r3, r4]
    ctx.fake.reset()
    result = await ctx.run()
    check('5.1 新增 1 行', result['inserted'] == 1, str(result))
    check('5.2 未更新的行不被重写', result['updated'] == 0, str(result))
    check('5.3 insert_rows 只调 1 次', ctx.fake.count('insert_rows:count=1') == 1, str(ctx.fake.calls))
    check('5.4 新行写在 A2:G2', ctx.fake.count('write:A2:G2') == 1, str(ctx.fake.calls))
    check('5.5 新行在表头下方', ctx.find_row(104) is ctx.fake.rows[0])
    check('5.6 表格共 4 行数据', len(ctx.fake.rows) == 4, str(len(ctx.fake.rows)))

    # --- 6) 资源失效：只改状态列，不删行 ---
    r1.status = 'disabled'
    ctx.fake.reset()
    result = await ctx.run()
    check('6.1 失效只更新 1 行', result['updated'] == 1, str(result))
    check('6.2 状态列改为失效', (ctx.find_row(101) or [''] * 5)[4] == '失效')
    check('6.3 失效行未被删除', ctx.find_row(101) is not None)
    check('6.4 offline 计数为 1', result['offline'] == 1, str(result))
    r1.status = 'enabled'

    # --- 7) 分类选项变化：触发一次重建，且只在变化时重建 ---
    ctx.config.category_options = ['行测', '申论', '常识', '时政']
    ctx.fake.reset()
    await ctx.run()
    check('7.1 选项变化后重建下拉', ctx.fake.count('set_dropdown') == 3, str(ctx.fake.calls))
    check('7.2 新选项已下发', ctx.fake.count('set_dropdown:C2:C50|行测,申论,常识,时政') == 1, str(ctx.fake.calls))
    ctx.fake.reset()
    await ctx.run()
    check('7.3 选项未变则不再重建', ctx.fake.count('set_dropdown') == 0, str(ctx.fake.calls))

    # --- 8) 数据区超出已装饰范围：补一次装饰 ---
    extra = [FakeResource(200 + index, f'批量资料{index}', 10, f'https://b/{index}', T0) for index in range(40)]
    ctx.resources = [r1, r2, r3, r4, *extra]
    ctx.fake.rows.extend([ctx.build(item, '网络获取') for item in extra])
    ctx.fake.reset()
    result = await ctx.run()
    check('8.1 批量行本身无需改写', result['updated'] == 0 and result['inserted'] == 0, str(result))
    check('8.2 数据扩张后补一次装饰', ctx.fake.count('set_dropdown') == 3, str(ctx.fake.calls))
    ctx.fake.reset()
    await ctx.run()
    check('8.3 扩张后下一轮不再装饰', ctx.fake.count('set_dropdown') == 0, str(ctx.fake.calls))

    # --- 9) 归一化 / 行对比单元行为 ---
    norm = ctx.service._normalize_cell
    changed = ctx.service._row_changed
    check('9.1 None 与空串等价', norm(None) == norm(''))
    check('9.2 数字 123.0 与 123 等价', norm(123.0) == norm(123) == '123')
    check('9.3 超链接结构回读为文本', norm([{'link': 'https://a/1', 'text': 'https://a/1'}]) == 'https://a/1')
    check('9.4 富文本分段拼接', norm([{'text': 'AB'}, {'text': 'CD'}]) == 'ABCD')
    check('9.5 旧行缺列按空处理', changed(['标题', '链接'], ['标题', '链接', '', '', '', '', 1]) is True)
    check(
        '9.6 完全一致判为未变化',
        changed(
            ['标题', '链接', '行测', 'X', '有效', '网络获取', 101],
            ['标题', '链接', '行测', 'X', '有效', '网络获取', 101],
        )
        is False,
    )
    check(
        '9.7 任一列不同即判为变化',
        changed(
            ['标题', '链接', '行测', 'X', '有效', '网络获取', 101],
            ['标题', '链接', '申论', 'X', '有效', '网络获取', 101],
        )
        is True,
    )
    check(
        '9.8 超链接列表与纯文本视作同一值',
        changed([[{'link': 'https://a/1', 'text': 'https://a/1'}]], ['https://a/1']) is False,
    )
    check(
        '9.9 超链接裸对象亦视作同一值',
        changed([{'link': 'https://a/1', 'text': 'https://a/1'}], ['https://a/1']) is False,
    )
    check('9.10 不可识别结构不与空串混淆', norm({}) != norm(''))

    # --- 10) is_public_visible 口径 ---
    check('10.1 正常可见', ctx.service.is_public_visible(r2) is True)
    check('10.2 分享链接为空即不可见', ctx.service.is_public_visible(FakeResource(301, 't', 10, '', T0)) is False)
    check('10.3 无分享记录即不可见', ctx.service.is_public_visible(FakeResource(302, 't', 10, None, T0)) is False)
    check(
        '10.4 审核未通过即不可见',
        ctx.service.is_public_visible(FakeResource(303, 't', 10, 'u', T0, audit_status='pending')) is False,
    )

    quiet = quiet or '-q' in sys.argv or '--quiet' in sys.argv
    lines = [line for line in OUT if not quiet or line.startswith('[FAIL]')]
    print('\n'.join(lines))
    print()
    print(f'总计: PASS={PASS} FAIL={FAIL}')
    return 1 if FAIL else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='飞书导出「只写变化行」自检')
    parser.add_argument('-q', '--quiet', action='store_true', help='只输出失败项与总计')
    arguments = parser.parse_args()
    sys.exit(asyncio.run(main(quiet=arguments.quiet)))
