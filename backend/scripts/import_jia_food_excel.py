#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import asyncio
import re
import zipfile
import xml.etree.ElementTree as ET

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from sqlalchemy import delete, text

from backend.app.jia.model.food import HealthyFood
from backend.database.db import async_db_session


MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
PKGREL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
RID_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'main': MAIN_NS, 'pkgrel': PKGREL_NS}

EXCEL_HEADERS = [
    'name',
    'energy',
    'protein',
    'carbohydrate',
    'fat',
    'water',
    'fiber',
    'ash',
    'vitamin_a',
    'carotene',
    'retinol_eq',
    'vitamin_b1',
    'vitamin_b2',
    'niacin',
    'vitamin_c',
    'vitamin_e',
    'potassium',
    'sodium',
    'calcium',
    'magnesium',
    'iron',
    'manganese',
    'zinc',
    'copper',
    'phosphorus',
    'selenium',
]

NUTRIENT_SCALES = {
    'energy': Decimal('0.01'),
    'protein': Decimal('0.01'),
    'carbohydrate': Decimal('0.01'),
    'fat': Decimal('0.01'),
    'water': Decimal('0.01'),
    'fiber': Decimal('0.01'),
    'ash': Decimal('0.01'),
    'vitamin_a': Decimal('0.001'),
    'carotene': Decimal('0.001'),
    'retinol_eq': Decimal('0.001'),
    'vitamin_b1': Decimal('0.001'),
    'vitamin_b2': Decimal('0.001'),
    'niacin': Decimal('0.001'),
    'vitamin_c': Decimal('0.001'),
    'vitamin_e': Decimal('0.001'),
    'potassium': Decimal('0.001'),
    'sodium': Decimal('0.001'),
    'calcium': Decimal('0.001'),
    'magnesium': Decimal('0.001'),
    'iron': Decimal('0.001'),
    'manganese': Decimal('0.001'),
    'zinc': Decimal('0.001'),
    'copper': Decimal('0.001'),
    'phosphorus': Decimal('0.001'),
    'selenium': Decimal('0.001'),
}


@dataclass(slots=True)
class FoodRow:
    """食物行数据"""

    row_no: int
    values: dict[str, str]


def parse_args() -> argparse.Namespace:
    """
    解析命令参数

    :return:
    """
    parser = argparse.ArgumentParser(description='从 Excel 导入 jia_food 数据')
    parser.add_argument(
        '--file',
        default=r'C:\Users\19396\Desktop\各种食物营养成分表.xlsx',
        help='Excel 文件路径',
    )
    parser.add_argument(
        '--sheet',
        default='食物成份表',
        help='工作表名称，默认使用 食物成份表',
    )
    parser.add_argument(
        '--created-by',
        type=int,
        default=1,
        help='created_by 字段值，默认 1',
    )
    parser.add_argument(
        '--truncate',
        action='store_true',
        help='导入前清空 jia_food 表',
    )
    parser.add_argument(
        '--commit',
        action='store_true',
        help='执行实际导入；默认仅预检查',
    )
    return parser.parse_args()


def col_to_index(cell_ref: str) -> int:
    """
    将 Excel 列标转换为从 0 开始的索引

    :param cell_ref: 单元格引用
    :return:
    """
    match = re.match(r'([A-Z]+)', cell_ref)
    if not match:
        return 0

    value = 0
    for ch in match.group(1):
        value = value * 26 + (ord(ch) - ord('A') + 1)
    return value - 1


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    """
    读取共享字符串表

    :param zf: Excel 压缩包
    :return:
    """
    if 'xl/sharedStrings.xml' not in zf.namelist():
        return []

    root = ET.fromstring(zf.read('xl/sharedStrings.xml'))
    result: list[str] = []
    for si in root.findall('main:si', NS):
        parts = []
        for text_node in si.iterfind('.//main:t', NS):
            parts.append(text_node.text or '')
        result.append(''.join(parts))
    return result


def resolve_sheet_path(zf: zipfile.ZipFile, sheet_name: str) -> str:
    """
    解析工作表对应的 xml 路径

    :param zf: Excel 压缩包
    :param sheet_name: 工作表名称
    :return:
    """
    workbook = ET.fromstring(zf.read('xl/workbook.xml'))
    rels = ET.fromstring(zf.read('xl/_rels/workbook.xml.rels'))
    rel_map = {
        rel.attrib['Id']: rel.attrib['Target']
        for rel in rels.findall('pkgrel:Relationship', NS)
    }

    sheets = workbook.find('main:sheets', NS)
    if sheets is None:
        raise ValueError('Excel 中未找到工作表定义')

    for sheet in sheets.findall('main:sheet', NS):
        if sheet.attrib.get('name') != sheet_name:
            continue
        rid = sheet.attrib.get(f'{{{RID_NS}}}id')
        if not rid or rid not in rel_map:
            raise ValueError(f'工作表 {sheet_name} 缺少关联关系')
        return f"xl/{rel_map[rid]}"

    raise ValueError(f'Excel 中不存在工作表: {sheet_name}')


def get_cell_text(cell: ET.Element, shared_strings: list[str]) -> str:
    """
    获取单元格文本

    :param cell: 单元格节点
    :param shared_strings: 共享字符串表
    :return:
    """
    cell_type = cell.attrib.get('t')
    value_elem = cell.find('main:v', NS)

    if cell_type == 'inlineStr':
        inline_elem = cell.find('main:is', NS)
        if inline_elem is None:
            return ''
        return ''.join(text.text or '' for text in inline_elem.iterfind('.//main:t', NS)).strip()

    if value_elem is None:
        return ''

    raw = (value_elem.text or '').strip()
    if cell_type == 's' and raw:
        return shared_strings[int(raw)].strip()
    return raw


def parse_excel(file_path: Path, sheet_name: str) -> tuple[list[str], list[FoodRow]]:
    """
    解析 Excel 数据

    :param file_path: 文件路径
    :param sheet_name: 工作表名称
    :return:
    """
    with zipfile.ZipFile(file_path) as zf:
        shared_strings = read_shared_strings(zf)
        sheet_path = resolve_sheet_path(zf, sheet_name)
        sheet_root = ET.fromstring(zf.read(sheet_path))

    sheet_data = sheet_root.find('main:sheetData', NS)
    if sheet_data is None:
        raise ValueError('工作表中缺少 sheetData')

    excel_header: list[str] = []
    rows: list[FoodRow] = []
    for row_idx, row in enumerate(sheet_data.findall('main:row', NS), start=1):
        values_by_index: dict[int, str] = {}
        for cell in row.findall('main:c', NS):
            cell_ref = cell.attrib.get('r', 'A1')
            values_by_index[col_to_index(cell_ref)] = get_cell_text(cell, shared_strings)

        ordered_values = [values_by_index.get(index, '').strip() for index in range(len(EXCEL_HEADERS))]
        if row_idx == 1:
            excel_header = ordered_values
            continue

        if not ordered_values[0]:
            continue

        rows.append(
            FoodRow(
                row_no=row_idx,
                values={EXCEL_HEADERS[index]: ordered_values[index] for index in range(len(EXCEL_HEADERS))},
            )
        )

    return excel_header, rows


def parse_decimal(raw: str, scale: Decimal) -> Decimal | None:
    """
    将 Excel 原始值转换为 Decimal

    :param raw: 原始字符串
    :param scale: 保留精度
    :return:
    """
    if raw == '':
        return None

    normalized = raw.replace('，', ',').replace(',', '').strip()
    if not normalized:
        return None

    value = Decimal(normalized)
    return value.quantize(scale, rounding=ROUND_HALF_UP)


def build_food_model(row: FoodRow, created_by: int) -> HealthyFood:
    """
    构建食物模型

    :param row: Excel 行数据
    :param created_by: 创建者 ID
    :return:
    """
    payload: dict[str, object] = {
        'name': row.values['name'],
        'alias': None,
        'description': None,
        'category_id': None,
        'image_path': None,
        'barcode': None,
        'serving_size': Decimal('100.00'),
        'serving_unit': 'g',
        'source': 'system',
        'status': True,
        'created_by': created_by,
    }

    for field, scale in NUTRIENT_SCALES.items():
        payload[field] = parse_decimal(row.values[field], scale)

    return HealthyFood(**payload)


def summarize_rows(rows: list[FoodRow]) -> dict[str, object]:
    """
    汇总导入数据统计

    :param rows: Excel 行数据
    :return:
    """
    name_counter = Counter(row.values['name'] for row in rows)
    duplicate_names = [(name, count) for name, count in name_counter.items() if count > 1]
    return {
        'row_count': len(rows),
        'duplicate_name_count': len(duplicate_names),
        'duplicate_name_samples': duplicate_names[:20],
    }


async def run_import(args: argparse.Namespace) -> None:
    """
    执行导入流程

    :param args: 命令参数
    :return:
    """
    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f'Excel 文件不存在: {file_path}')

    excel_header, rows = parse_excel(file_path, args.sheet)
    summary = summarize_rows(rows)

    print(f'文件: {file_path}')
    print(f'工作表: {args.sheet}')
    print(f'表头: {excel_header}')
    print(f"数据行数: {summary['row_count']}")
    print(f"重名组数: {summary['duplicate_name_count']}")
    print(f"重名示例: {summary['duplicate_name_samples']}")

    async with async_db_session() as db:
        current_count = await db.scalar(text('select count(*) from jia_food'))
        print(f'当前 jia_food 记录数: {current_count}')

        if not args.commit:
            print('当前为 dry-run，未写入数据库。')
            return

        if current_count and not args.truncate:
            raise ValueError('jia_food 表已存在数据，如需重新导入请显式添加 --truncate')

        if args.truncate:
            await db.execute(delete(HealthyFood))
            await db.flush()
            print('已清空 jia_food 表。')

        models = [build_food_model(row, args.created_by) for row in rows]
        db.add_all(models)
        await db.commit()
        print(f'已导入 {len(models)} 条食物数据。')


def main() -> None:
    """程序入口"""
    args = parse_args()
    asyncio.run(run_import(args))


if __name__ == '__main__':
    main()
