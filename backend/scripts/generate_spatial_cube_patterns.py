#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate vector and WebP assets for spatial cube face patterns."""

from __future__ import annotations

import argparse
import json
import string

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

import fitz

from PIL import Image

if TYPE_CHECKING:
    from collections.abc import Iterable

CANVAS_SIZE = 256
CENTER = CANVAS_SIZE / 2
COLOR = '#0f172a'
TEXT_COLOR = (15 / 255, 23 / 255, 42 / 255)
SVG_NAMESPACE = 'http://www.w3.org/2000/svg'
RADIAL_ENDPOINTS = (
    (CENTER, 0),
    (CANVAS_SIZE, 0),
    (CANVAS_SIZE, CENTER),
    (CANVAS_SIZE, CANVAS_SIZE),
    (CENTER, CANVAS_SIZE),
    (0, CANVAS_SIZE),
    (0, CENTER),
    (0, 0),
)
ET.register_namespace('', SVG_NAMESPACE)


@dataclass(frozen=True, slots=True)
class PatternAsset:
    """描述一个可发布的六面体面素材。"""

    code: str
    name: str
    category: str
    rotation_period: int
    sort: int
    svg_file: str
    webp_file: str


def rotate_mask(mask: int, shift: int) -> int:
    """
    按 45 度线段索引旋转米字掩码。

    :param mask: 8 位线段掩码
    :param shift: 旋转的 45 度步数
    :return: 旋转后的掩码
    """
    normalized_shift = shift % 8
    return ((mask << normalized_shift) | (mask >> (8 - normalized_shift))) & 0xFF


def canonical_mask(mask: int) -> int:
    """
    取 90 度旋转等价类中的最小掩码。

    :param mask: 8 位线段掩码
    :return: 旋转去重后的代表掩码
    """
    return min(rotate_mask(mask, shift) for shift in (0, 2, 4, 6))


def canonical_masks() -> list[int]:
    """返回全部非空米字组合的 90 度旋转代表。"""
    return [mask for mask in range(1, 256) if mask == canonical_mask(mask)]


def rotation_period(mask: int) -> int:
    """
    计算图案在六面体 90 度旋转中的等价周期。

    :param mask: 8 位线段掩码
    :return: 90、180 或 360
    """
    if rotate_mask(mask, 2) == mask:
        return 90
    if rotate_mask(mask, 4) == mask:
        return 180
    return 360


def svg_root(children: Iterable[ET.Element]) -> ET.Element:
    """创建统一规格的 SVG 根节点。"""
    root = ET.Element(
        f'{{{SVG_NAMESPACE}}}svg',
        {
            'viewBox': f'0 0 {CANVAS_SIZE} {CANVAS_SIZE}',
            'width': str(CANVAS_SIZE),
            'height': str(CANVAS_SIZE),
            'version': '1.1',
        },
    )
    root.extend(children)
    return root


def serialize_svg(root: ET.Element) -> str:
    """
    序列化 SVG 文档。

    :param root: SVG 根节点
    :return: SVG 文本
    """
    return ET.tostring(root, encoding='unicode', short_empty_elements=True)


def line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    stroke_width: float = 16,
) -> ET.Element:
    """
    创建一条带圆角端点的线段。

    :param x1: 起点横坐标
    :param y1: 起点纵坐标
    :param x2: 终点横坐标
    :param y2: 终点纵坐标
    :param stroke_width: 线宽
    :return: SVG 线段节点
    """
    return ET.Element(
        f'{{{SVG_NAMESPACE}}}line',
        {
            'x1': f'{x1:.3f}',
            'y1': f'{y1:.3f}',
            'x2': f'{x2:.3f}',
            'y2': f'{y2:.3f}',
            'stroke': COLOR,
            'stroke-width': f'{stroke_width:.3f}',
            'stroke-linecap': 'round',
        },
    )


def geometric_svg(code: str) -> str:
    """
    生成基础几何图案 SVG。

    :param code: 图案编码
    :return: SVG 文本
    """
    children: list[ET.Element] = []
    if code == 'shape-horizontal':
        children.append(line(38, CENTER, 218, CENTER))
    elif code == 'shape-diagonal':
        children.append(line(44, 44, 212, 212))
    elif code == 'shape-cross':
        children.extend((line(42, 42, 214, 214), line(214, 42, 42, 214)))
    elif code == 'shape-circle':
        children.append(
            ET.Element(
                f'{{{SVG_NAMESPACE}}}circle',
                {
                    'cx': str(CENTER),
                    'cy': str(CENTER),
                    'r': '78',
                    'fill': 'none',
                    'stroke': COLOR,
                    'stroke-width': '16',
                },
            ),
        )
    elif code == 'shape-square':
        children.append(
            ET.Element(
                f'{{{SVG_NAMESPACE}}}rect',
                {
                    'x': '48',
                    'y': '48',
                    'width': '160',
                    'height': '160',
                    'fill': 'none',
                    'stroke': COLOR,
                    'stroke-width': '16',
                    'stroke-linejoin': 'round',
                },
            ),
        )
    elif code == 'shape-triangle':
        children.append(
            ET.Element(
                f'{{{SVG_NAMESPACE}}}polygon',
                {
                    'points': '128,38 220,210 36,210',
                    'fill': 'none',
                    'stroke': COLOR,
                    'stroke-width': '16',
                    'stroke-linejoin': 'round',
                },
            ),
        )
    else:
        raise ValueError(f'未知几何图案: {code}')
    return serialize_svg(svg_root(children))


def radial_svg(mask: int) -> str:
    """
    根据米字掩码生成 SVG。

    :param mask: 8 位线段掩码
    :return: SVG 文本
    """
    children: list[ET.Element] = []
    for index, (endpoint_x, endpoint_y) in enumerate(RADIAL_ENDPOINTS):
        if not mask & (1 << index):
            continue
        children.append(
            line(
                CENTER,
                CENTER,
                endpoint_x,
                endpoint_y,
                stroke_width=14,
            ),
        )
    return serialize_svg(svg_root(children))


def text_svg(character: str) -> str:
    """
    使用 MuPDF 内置粗体字体轮廓生成字符 SVG。

    :param character: 单个数字或拉丁字母
    :return: SVG 文本
    """
    document = fitz.open()
    try:
        page = document.new_page(width=CANVAS_SIZE, height=CANVAS_SIZE)
        page.insert_text((32, 210), character, fontname='hebo', fontsize=176, color=TEXT_COLOR)
        pixmap = page.get_pixmap(alpha=True)
        image = Image.frombytes('RGBA', (pixmap.width, pixmap.height), pixmap.samples)
        bbox = image.getchannel('A').getbbox()
        if bbox is None:
            raise RuntimeError(f'字符无法生成: {character}')
        offset_x = CENTER - (bbox[0] + bbox[2]) / 2
        offset_y = CENTER - (bbox[1] + bbox[3]) / 2

        document.close()
        document = fitz.open()
        page = document.new_page(width=CANVAS_SIZE, height=CANVAS_SIZE)
        page.insert_text(
            (32 + offset_x, 210 + offset_y),
            character,
            fontname='hebo',
            fontsize=176,
            color=TEXT_COLOR,
        )
        return page.get_svg_image(text_as_path=True)
    finally:
        document.close()


def render_webp(svg: str, destination: Path) -> None:
    """
    将 SVG 渲染为透明 WebP。

    :param svg: SVG 文本
    :param destination: WebP 输出路径
    :return:
    """
    document = fitz.open(stream=svg.encode('utf-8'), filetype='svg')
    try:
        pixmap = document[0].get_pixmap(alpha=True)
        image = Image.frombytes('RGBA', (pixmap.width, pixmap.height), pixmap.samples)
        image.save(destination, format='WEBP', lossless=True, quality=100, method=6)
    finally:
        document.close()


def build_assets() -> list[tuple[PatternAsset, str]]:
    """构建数字、字母、几何图案和米字组合清单。"""
    assets: list[tuple[PatternAsset, str]] = []
    definitions: list[tuple[str, str, str, int, str]] = []
    definitions.extend(
        (f'digit-{value}', f'数字 {value}', 'digit', 360, str(value))
        for value in range(10)
    )
    definitions.extend(
        (f'latin-upper-{char.lower()}', f'大写 {char}', 'letter', 360, char)
        for char in string.ascii_uppercase
    )
    definitions.extend(
        (f'latin-lower-{char}', f'小写 {char}', 'letter', 360, char)
        for char in string.ascii_lowercase
    )
    definitions.extend(
        (
            (code, name, 'shape', period, '')
            for code, name, period in (
                ('shape-horizontal', '横线', 180),
                ('shape-diagonal', '斜线', 180),
                ('shape-cross', '叉', 90),
                ('shape-circle', '圆', 90),
                ('shape-square', '正方形', 90),
                ('shape-triangle', '三角形', 360),
            )
        ),
    )
    definitions.extend(
        (f'radial-{mask:02x}', f'米字组合 {mask:02X}', 'radial', rotation_period(mask), '')
        for mask in canonical_masks()
    )

    for sort, (code, name, category, period, character) in enumerate(definitions):
        if category == 'digit' or category == 'letter':
            svg = text_svg(character)
        elif category == 'shape':
            svg = geometric_svg(code)
        else:
            svg = radial_svg(int(code.removeprefix('radial-'), 16))
        asset = PatternAsset(
            code=code,
            name=name,
            category=category,
            rotation_period=period,
            sort=sort,
            svg_file=f'svg/{code}.svg',
            webp_file=f'webp/{code}.webp',
        )
        assets.append((asset, svg))
    return assets


def write_assets(output_dir: Path, version: str) -> list[PatternAsset]:
    """
    写入全部素材和导入清单。

    :param output_dir: 输出目录
    :param version: 素材版本
    :return: 素材清单
    """
    assets = build_assets()
    for asset, svg in assets:
        svg_path = output_dir / asset.svg_file
        webp_path = output_dir / asset.webp_file
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        webp_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text(svg, encoding='utf-8')
        render_webp(svg, webp_path)

    manifest = {
        'version': version,
        'canvas': {'height': CANVAS_SIZE, 'width': CANVAS_SIZE},
        'rotation_deduplicated': True,
        'assets': [asdict(asset) for asset, _ in assets],
    }
    (output_dir / 'manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    return [asset for asset, _ in assets]


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description='生成六面体面素材 SVG 和 WebP')
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=None,
        help='素材输出目录',
    )
    parser.add_argument('--version', default='generated-v2', help='素材版本')
    return parser.parse_args()


def main() -> None:
    """生成素材并打印结果统计。"""
    args = parse_args()
    output_dir = args.output_dir or Path('assets/spatial-cube-patterns') / args.version
    assets = write_assets(output_dir, args.version)
    print(f'generated assets: {len(assets)}')
    print(f'radial assets: {sum(asset.category == "radial" for asset in assets)}')
    print(f'output: {output_dir.resolve()}')


if __name__ == '__main__':
    main()
