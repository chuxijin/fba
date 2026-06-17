#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OCR e2e 测试 (百度 handwriting)

用法:
  .venv/Scripts/python -m backend.plugin.agents.scripts.test_ocr_baidu --image backend/plugin/agents/tests/33734e2b853489ad707a5a31f6b03db5.png
"""

import argparse
import asyncio
import sys

from pathlib import Path

from backend.plugin.agents.service.common.ocr.client import OCRClient


async def run_ocr(image_path: Path) -> None:
    """执行百度 OCR 识别"""
    content = image_path.read_bytes()
    if not content:
        print(f'图片文件为空: {image_path}', file=sys.stderr)
        sys.exit(1)

    filename = image_path.name
    content_type = 'image/png' if filename.endswith('.png') else 'image/jpeg'

    print(f'图片: {image_path}')
    print(f'大小: {len(content)} bytes')
    print()

    client = OCRClient(provider_name='baidu')
    text = await client.recognize_images(
        images=[(content, filename, content_type)],
        scene='subjective_answer',
    )

    print('=' * 60)
    print('百度 OCR 识别结果 (subjective_answer 场景):')
    print('=' * 60)
    print(text)
    print('=' * 60)
    print(f'字数: {len(text)}')


def main() -> None:
    parser = argparse.ArgumentParser(description='百度 OCR 手写识别测试')
    parser.add_argument('--image', required=True, help='图片文件路径')
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f'图片文件不存在: {image_path}', file=sys.stderr)
        sys.exit(1)

    asyncio.run(run_ocr(image_path))


if __name__ == '__main__':
    main()
