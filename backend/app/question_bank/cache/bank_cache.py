#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Iterable
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import PydanticSerializer


class BankSnapshot(BaseModel):
    """题库快照(仅含稳定字段, 用于跨接口共享缓存)"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题库 ID')
    cat_id: int = Field(description='分类 ID')
    name: str = Field(description='题库名称')
    code: str = Field(description='业务编码')
    desc: str | None = Field(None, description='描述')
    year: int | None = Field(None, description='年份')
    cover_url: str | None = Field(None, description='封面地址')
    difficulty: Decimal | None = Field(None, description='整体难度')
    bank_type: int = Field(description='内容类型')
    scene_mask: int = Field(description='场景位标记')
    parent_id: int | None = Field(None, description='父合集 ID')
    sort_order: int = Field(description='排序权重')
    chapter_source_bank_id: int | None = Field(None, description='篇章来源内容 ID')
    status: int = Field(description='状态')


bank_cache: RedisCache[BankSnapshot] = RedisCache(
    prefix='qbank:bank:snapshot',
    ttl=600,
    serializer=PydanticSerializer(BankSnapshot),
    local=True,
    invalidate_pubsub=True,
)


async def get_bank_snapshot(db: AsyncSession, bank_id: int) -> BankSnapshot | None:
    """
    读取题库快照, 命中走 L1/L2 缓存, miss 时回源 DB

    :param db: 数据库会话
    :param bank_id: 题库 ID
    """

    async def factory() -> BankSnapshot | None:
        bank = await bank_dao.get(db, bank_id)
        if bank is None:
            return None
        return BankSnapshot.model_validate(bank)

    return await bank_cache.get_or_set(bank_id, factory=factory)


async def invalidate_bank_snapshots(bank_ids: Iterable[int]) -> None:
    """
    失效一批题库快照, 用于 bank 写入后的缓存清理

    :param bank_ids: 题库 ID 集合
    """
    for bank_id in bank_ids:
        await bank_cache.invalidate(bank_id)
