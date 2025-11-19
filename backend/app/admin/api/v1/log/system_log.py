#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import os

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.core.conf import settings
from backend.core.path_conf import LOG_DIR

router = APIRouter()


@router.get('/stream', summary='实时日志流')
async def stream_logs():
    """实时日志流"""
    log_file = LOG_DIR / settings.LOG_ACCESS_FILENAME

    async def log_generator():
        """日志生成器"""
        # 如果日志文件不存在，等待创建
        retry_count = 0
        while not os.path.exists(log_file) and retry_count < 10:
            yield f'[INFO] 等待日志文件创建: {log_file}\n'
            await asyncio.sleep(1)
            retry_count += 1

        if not os.path.exists(log_file):
            yield f'[ERROR] 日志文件不存在: {log_file}\n'
            return

        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                # 跳到文件末尾，只显示实时日志
                f.seek(0, os.SEEK_END)
                yield '=== 实时日志监听中 ===\n'

                # 开始实时监听新日志
                while True:
                    line = f.readline()
                    if line:
                        yield line
                    else:
                        # 没有新行时，短暂休眠
                        await asyncio.sleep(0.1)
        except Exception as e:
            yield f'[ERROR] 读取日志文件失败: {str(e)}\n'

    return StreamingResponse(
        log_generator(),
        media_type='text/plain',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )
