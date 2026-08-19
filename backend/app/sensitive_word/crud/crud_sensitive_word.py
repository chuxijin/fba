#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.sensitive_word.model import SensitiveHitLog, SysSensitiveWord


class CRUDSensitiveWord(CRUDPlus[SysSensitiveWord]):
    """敏感词数据库操作类"""

    async def get_by_word(self, db: AsyncSession, word: str, exclude_id: int | None = None) -> SysSensitiveWord | None:
        stmt = select(SysSensitiveWord).where(SysSensitiveWord.word == word, SysSensitiveWord.deleted == 0)
        if exclude_id is not None:
            stmt = stmt.where(SysSensitiveWord.id != exclude_id)
        return (await db.execute(stmt)).scalars().first()

    async def get_by_id(self, db: AsyncSession, pk: int) -> SysSensitiveWord | None:
        stmt = select(SysSensitiveWord).where(SysSensitiveWord.id == pk, SysSensitiveWord.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    def get_list_select(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        action: str | None = None,
    ) -> Select:
        stmt = select(SysSensitiveWord).where(SysSensitiveWord.deleted == 0)
        if status is not None:
            stmt = stmt.where(SysSensitiveWord.status == status)
        if action is not None:
            stmt = stmt.where(SysSensitiveWord.action == action)
        if keyword:
            like = f'%{keyword}%'
            stmt = stmt.where(SysSensitiveWord.word.like(like))
        return stmt.order_by(SysSensitiveWord.sort_order.asc(), SysSensitiveWord.id.desc())

    async def list_active_rules(self, db: AsyncSession) -> list[dict[str, Any]]:
        """获取生效中的敏感词规则（含变体词库）。"""
        stmt = (
            select(
                SysSensitiveWord.id,
                SysSensitiveWord.word,
                SysSensitiveWord.variants,
                SysSensitiveWord.replacement,
                SysSensitiveWord.action,
            )
            .where(SysSensitiveWord.status == 'active', SysSensitiveWord.deleted == 0)
            .order_by(func.length(SysSensitiveWord.word).desc(), SysSensitiveWord.sort_order.asc())
        )
        result = await db.execute(stmt)
        rules: list[dict[str, Any]] = []
        for row in result.all():
            word = str(row[1])
            variants = [str(item) for item in (row[2] or []) if item and str(item).strip()]
            keywords = list(dict.fromkeys([word, *variants]))
            rules.append(
                {
                    'id': int(row[0]),
                    'word': word,
                    'keywords': keywords,
                    'replacement': row[3],
                    'action': str(row[4]),
                }
            )
        return rules


class CRUDSensitiveHitLog(CRUDPlus[SensitiveHitLog]):
    """敏感词命中日志数据库操作类"""

    async def create_bulk(self, db: AsyncSession, items: list[dict[str, Any]]) -> None:
        """批量写入命中日志。"""
        if not items:
            return
        db.add_all([SensitiveHitLog(**item) for item in items])
        await db.flush()

    def get_list_select(
        self,
        *,
        keyword: str | None = None,
        action: str | None = None,
        user_id: int | None = None,
        target_type: str | None = None,
    ) -> Select:
        stmt = select(SensitiveHitLog).where(SensitiveHitLog.deleted == 0)
        if user_id is not None:
            stmt = stmt.where(SensitiveHitLog.user_id == user_id)
        if action is not None:
            stmt = stmt.where(SensitiveHitLog.action == action)
        if target_type is not None:
            stmt = stmt.where(SensitiveHitLog.target_type == target_type)
        if keyword:
            like = f'%{keyword}%'
            stmt = stmt.where(
                SensitiveHitLog.word.like(like)
                | SensitiveHitLog.keyword.like(like)
                | SensitiveHitLog.snippet.like(like)
            )
        return stmt.order_by(SensitiveHitLog.created_time.desc(), SensitiveHitLog.id.desc())


sensitive_word_dao: CRUDSensitiveWord = CRUDSensitiveWord(SysSensitiveWord)
sensitive_hit_log_dao: CRUDSensitiveHitLog = CRUDSensitiveHitLog(SensitiveHitLog)
