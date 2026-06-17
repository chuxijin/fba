#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库延迟分层基准测试

逐层测量数据库访问开销，定位 chapter-progress 接口慢的根因
- L1: asyncpg 裸 SELECT 1（纯网络 + PG 处理）
- L2: asyncpg 复用连接 SELECT 1（去掉建连开销）
- L3: SQLAlchemy 引擎 SELECT 1（看 SA 包装开销）
- L4: SQLAlchemy ORM 主键查询（业务实际路径）
- L5: 复现接口 4 条 SQL 串行（端到端）

后端服务在跑时用 --no-sync 避免 uv 重装依赖（防止 fba.exe 被占用报错）：
    uv run --no-sync python backend/scratch/bench_db_latency.py
"""

import asyncio
import statistics
import sys
import time
from pathlib import Path

# 让 backend 包可被导入
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import asyncpg

from sqlalchemy import select, text

from backend.core.conf import settings
from backend.database.db import async_db_session, async_engine
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.service.bank_progress_service import BankProgressService

ROUNDS = 10
BANK_ID = 1128
USER_ID = 18


def fmt(samples: list[float]) -> str:
    """格式化统计数据"""
    if not samples:
        return 'no data'
    return (
        f'min={min(samples):.1f}ms '
        f'avg={statistics.mean(samples):.1f}ms '
        f'p50={statistics.median(samples):.1f}ms '
        f'max={max(samples):.1f}ms'
    )


async def bench_l1_asyncpg_per_call() -> list[float]:
    """L1：每次新建连接 + SELECT 1"""
    samples = []
    for _ in range(ROUNDS):
        t = time.perf_counter()
        conn = await asyncpg.connect(
            host=settings.DATABASE_HOST,
            port=settings.DATABASE_PORT,
            user=settings.DATABASE_USER,
            password=settings.DATABASE_PASSWORD,
            database=settings.DATABASE_SCHEMA,
        )
        await conn.fetchval('SELECT 1')
        await conn.close()
        samples.append((time.perf_counter() - t) * 1000)
    return samples


async def bench_l2_asyncpg_reuse() -> list[float]:
    """L2：复用连接，只测 SELECT 1 往返"""
    conn = await asyncpg.connect(
        host=settings.DATABASE_HOST,
        port=settings.DATABASE_PORT,
        user=settings.DATABASE_USER,
        password=settings.DATABASE_PASSWORD,
        database=settings.DATABASE_SCHEMA,
    )
    samples = []
    try:
        for _ in range(ROUNDS):
            t = time.perf_counter()
            await conn.fetchval('SELECT 1')
            samples.append((time.perf_counter() - t) * 1000)
    finally:
        await conn.close()
    return samples


async def bench_l3_sa_engine_select1() -> list[float]:
    """L3：通过 SQLAlchemy 引擎跑 SELECT 1"""
    samples = []
    for _ in range(ROUNDS):
        t = time.perf_counter()
        async with async_engine.connect() as conn:
            await conn.execute(text('SELECT 1'))
        samples.append((time.perf_counter() - t) * 1000)
    return samples


async def bench_l4_sa_orm_get() -> list[float]:
    """L4：复现 bank_dao.get（ORM 主键查询）"""
    samples = []
    for _ in range(ROUNDS):
        async with async_db_session() as session:
            t = time.perf_counter()
            await bank_dao.get(session, BANK_ID)
            samples.append((time.perf_counter() - t) * 1000)
    return samples


async def bench_l5_full_chain() -> list[float]:
    """L5：端到端调用真实业务方法"""
    samples = []
    for _ in range(ROUNDS):
        async with async_db_session() as session:
            t = time.perf_counter()
            await BankProgressService.get_chapter_progress(db=session, bank_id=BANK_ID, user_id=USER_ID)
            samples.append((time.perf_counter() - t) * 1000)
    return samples


async def main() -> None:
    """跑全部分层基准"""
    print(f'>>> Database: {settings.DATABASE_HOST}:{settings.DATABASE_PORT} / {settings.DATABASE_SCHEMA}')
    print(f'>>> Rounds per layer: {ROUNDS}')
    print(f'>>> Bank ID: {BANK_ID}, User ID: {USER_ID}\n')

    print('--- L1: asyncpg connect + SELECT 1 (建连成本) ---')
    print(fmt(await bench_l1_asyncpg_per_call()))

    print('\n--- L2: asyncpg reuse + SELECT 1 (纯往返) ---')
    print(fmt(await bench_l2_asyncpg_reuse()))

    print('\n--- L3: SA engine + SELECT 1 (SA 引擎包装) ---')
    print(fmt(await bench_l3_sa_engine_select1()))

    print('\n--- L4: SA ORM bank_dao.get (业务路径单条) ---')
    print(fmt(await bench_l4_sa_orm_get()))

    print('\n--- L5: 端到端 get_chapter_progress (4条 SQL 串行) ---')
    print(fmt(await bench_l5_full_chain()))

    await async_engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
