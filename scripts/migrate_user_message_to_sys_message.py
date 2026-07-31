#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""站内信历史数据迁移脚本：question_bank → admin 消息中心

将 v1 的 study_user_message / study_user_message_read 迁入 v2 的 sys_message / sys_message_read。

设计要点：
- 用 ORM 写入，主键生成对自增/雪花两种模式透明。
- 保留原 message.id，使 read 行的 message_id 引用无需映射表即可对齐。
- 幂等：已存在的 message.id / (message_id, user_id) 直接跳过，可重复运行。
- 统一已读表：v1 单人消息行上的 read_time 转成一条 sys_message_read；v1 已读表整表直搬。
- 自增主键模式下，迁移后用 pg_get_serial_sequence + setval 重置序列，避免后续新建撞 id。

使用方法: python scripts/migrate_user_message_to_sys_message.py
"""
import asyncio
import sys

from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select, text

from backend.app.admin.model.message import Message, MessageRead, MessageTargetType
from backend.app.question_bank.model import UserMessage, UserMessageRead
from backend.database.db import async_db_session


async def _reset_sequence(session, model) -> None:
    """自增主键模式下重置序列到 max(id)；雪花模式无序列则跳过"""
    table = model.__tablename__
    seq_stmt = text(f"SELECT pg_get_serial_sequence('{table}', 'id')")
    seq_name = (await session.execute(seq_stmt)).scalar()
    if not seq_name:
        # 雪花算法主键，无自增序列
        return
    max_id = (await session.execute(select(func.max(model.id)))).scalar()
    if max_id is None:
        return
    # setval 到当前最大 id，下一条从 max_id + 1 开始
    await session.execute(text(f"SELECT setval('{seq_name}', {int(max_id)}, true)"))
    print(f'  序列 {seq_name} 已重置到 {max_id}')


async def migrate() -> None:
    """执行迁移"""
    print('=' * 60)
    print('站内信历史数据迁移：study_user_message → sys_message')
    print('=' * 60)

    async with async_db_session.begin() as session:
        # -------------------------------------------------- 1. 迁移消息主体
        existing_message_ids = set(
            (await session.execute(select(Message.id))).scalars().all()
        )
        v1_messages = (await session.execute(select(UserMessage))).scalars().all()

        migrated_messages = 0
        generated_read_rows: list[dict] = []
        for src in v1_messages:
            if src.id in existing_message_ids:
                continue
            session.add(
                Message(
                    id=src.id,
                    title=src.title,
                    content=src.content,
                    target_type=src.target_type,
                    user_id=src.user_id,
                    role_id=None,
                    message_type=src.message_type,
                    biz_source=None,
                    biz_id=None,
                    sender_id=None,
                    link_url=src.link_url,
                    payload=src.payload,
                    status=src.status,
                    publish_time=src.publish_time,
                    expire_time=src.expire_time,
                )
            )
            migrated_messages += 1

            # v1 单人消息的行上已读 → 统一进 read 表
            if (
                src.target_type == MessageTargetType.USER
                and src.read_time is not None
                and src.user_id is not None
            ):
                generated_read_rows.append(
                    {'message_id': src.id, 'user_id': src.user_id, 'read_time': src.read_time}
                )

        await session.flush()
        print(f'\n[1/3] 迁移消息主体：新增 {migrated_messages} 条（跳过已存在 {len(existing_message_ids)}）')

        # -------------------------------------------------- 2. 迁移 v1 已读表
        existing_reads = set(
            (await session.execute(select(MessageRead.message_id, MessageRead.user_id))).all()
        )
        v1_reads = (await session.execute(select(UserMessageRead))).scalars().all()

        migrated_reads = 0
        for r in v1_reads:
            key = (r.message_id, r.user_id)
            if key in existing_reads:
                continue
            session.add(MessageRead(message_id=r.message_id, user_id=r.user_id, read_time=r.read_time))
            existing_reads.add(key)
            migrated_reads += 1
        print(f'[2/3] 迁移已读表：新增 {migrated_reads} 条')

        # -------------------------------------------------- 2b. 单人消息行上已读转入
        generated = 0
        for row in generated_read_rows:
            key = (row['message_id'], row['user_id'])
            if key in existing_reads:
                continue
            session.add(MessageRead(**row))
            existing_reads.add(key)
            generated += 1
        print(f'      单人消息行上已读转入：新增 {generated} 条')

        await session.flush()

        # -------------------------------------------------- 3. 重置序列
        print('\n[3/3] 重置主键序列...')
        await _reset_sequence(session, Message)
        await _reset_sequence(session, MessageRead)

    print('\n迁移完成。')


if __name__ == '__main__':
    asyncio.run(migrate())
