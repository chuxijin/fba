#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.sensitive_word.crud.crud_sensitive_word import sensitive_hit_log_dao, sensitive_word_dao
from backend.app.sensitive_word.model import SysSensitiveWord
from backend.app.sensitive_word.schema.sensitive_word import (
    CreateSensitiveWordParam,
    GetSensitiveHitLogItem,
    GetSensitiveWordDetail,
    UpdateSensitiveWordParam,
)
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import JsonSerializer
from backend.common.exception import errors
from backend.common.pagination import paging_data

_SENSITIVE_RULES_CACHE = RedisCache(prefix='sensitive:word:rules', ttl=600, serializer=JsonSerializer())


@dataclass(slots=True)
class HitInfo:
    """单条命中信息"""

    word_id: int | None
    word: str
    action: str
    replacement: str | None
    keyword: str
    hit_count: int


@dataclass(slots=True)
class SanitizeResult:
    """脱敏结果"""

    clean_text: str
    matched: list[str] = field(default_factory=list)
    hits: list[HitInfo] = field(default_factory=list)


class SensitiveWordService:
    """敏感词处理服务类"""

    @staticmethod
    async def get_active_rules(db: AsyncSession) -> list[dict[str, Any]]:
        """获取生效中的敏感词规则（含变体，缓存 10 分钟）。"""

        async def _load() -> list[dict[str, Any]]:
            return await sensitive_word_dao.list_active_rules(db)

        cached = await _SENSITIVE_RULES_CACHE.get_or_set(factory=_load)
        return cached or []

    @staticmethod
    async def invalidate_cache() -> None:
        """管理端增删改后失效规则缓存。"""
        await _SENSITIVE_RULES_CACHE.invalidate()

    @classmethod
    async def sanitize(cls, db: AsyncSession, text: str | None) -> SanitizeResult:  # noqa: C901
        """对文本执行敏感词处理：拦截 -> 替换/打码，返回命中明细。"""
        if not text:
            return SanitizeResult(clean_text=text or '', matched=[])
        rules = await cls.get_active_rules(db)
        if not rules:
            return SanitizeResult(clean_text=text, matched=[])

        reject_matches = [
            keyword
            for rule in rules
            if rule['action'] == 'reject'
            for keyword in rule['keywords']
            if keyword in text
        ]
        if reject_matches:
            words = '、'.join(sorted(set(reject_matches)))
            raise errors.RequestError(msg=f'内容包含敏感词「{words}」，请修改后再提交')

        keyword_rule: dict[str, dict[str, Any]] = {}
        for rule in rules:
            if rule['action'] not in ('replace', 'block'):
                continue
            for keyword in rule['keywords']:
                if keyword in text and keyword not in keyword_rule:
                    keyword_rule[keyword] = rule
        if not keyword_rule:
            return SanitizeResult(clean_text=text, matched=[])

        ordered_keywords = sorted(keyword_rule.keys(), key=len, reverse=True)
        pattern = re.compile('|'.join(re.escape(keyword) for keyword in ordered_keywords))
        matches = pattern.findall(text)
        counts = Counter(matches)
        hits = [
            HitInfo(
                word_id=keyword_rule[keyword]['id'],
                word=keyword_rule[keyword]['word'],
                action=keyword_rule[keyword]['action'],
                replacement=keyword_rule[keyword]['replacement'],
                keyword=keyword,
                hit_count=counts[keyword],
            )
            for keyword in counts
        ]

        def _replace(match: re.Match) -> str:
            rule = keyword_rule[match.group(0)]
            if rule['action'] == 'replace':
                return rule['replacement'] or '**'
            return '**'

        clean_text = pattern.sub(_replace, text)
        return SanitizeResult(clean_text=clean_text, matched=sorted(set(matches)), hits=hits)

    @classmethod
    async def sanitize_value(cls, db: AsyncSession, value: Any, hits: list[HitInfo] | None = None) -> Any:
        """递归脱敏字符串容器（dict / list / str），命中明细追加到 hits。"""
        if hits is None:
            hits = []
        if isinstance(value, str):
            result = await cls.sanitize(db, value)
            hits.extend(result.hits)
            return result.clean_text
        if isinstance(value, list):
            return [await cls.sanitize_value(db, item, hits) for item in value]
        if isinstance(value, dict):
            return {key: await cls.sanitize_value(db, item, hits) for key, item in value.items()}
        return value

    @classmethod
    async def sanitize_collect(cls, db: AsyncSession, value: Any) -> tuple[Any, list[HitInfo]]:
        """脱敏结构化内容并返回全部命中明细。"""
        hits: list[HitInfo] = []
        cleaned = await cls.sanitize_value(db, value, hits)
        return cleaned, hits

    # ============ 命中日志 ============

    @staticmethod
    async def log_hits(
        *,
        db: AsyncSession,
        user_id: int,
        hits: list[HitInfo],
        target_type: str | None = None,
        target_id: int | None = None,
        snippet: str | None = None,
    ) -> None:
        """批量写入命中日志。"""
        items = [
            {
                'user_id': user_id,
                'word': hit.word,
                'keyword': hit.keyword,
                'word_id': hit.word_id,
                'action': hit.action,
                'replacement': hit.replacement,
                'hit_count': hit.hit_count,
                'target_type': target_type,
                'target_id': target_id,
                'snippet': snippet,
            }
            for hit in hits
        ]
        await sensitive_hit_log_dao.create_bulk(db, items)

    @staticmethod
    async def page_hits(
        *,
        db: AsyncSession,
        keyword: str | None = None,
        action: str | None = None,
        user_id: int | None = None,
        target_type: str | None = None,
    ) -> dict[str, Any]:
        """获取命中日志分页列表。"""
        stmt = sensitive_hit_log_dao.get_list_select(
            keyword=keyword,
            action=action,
            user_id=user_id,
            target_type=target_type,
        )
        return await paging_data(db, stmt, schema_cls=GetSensitiveHitLogItem)

    # ============ 管理端 CRUD ============

    @staticmethod
    async def create(*, db: AsyncSession, user_id: int, obj: CreateSensitiveWordParam) -> GetSensitiveWordDetail:
        """创建敏感词。"""
        existing = await sensitive_word_dao.get_by_word(db, obj.word)
        if existing is not None:
            raise errors.ConflictError(msg='敏感词已存在')
        item = SysSensitiveWord(
            word=obj.word,
            variants=obj.variants,
            replacement=obj.replacement,
            action=obj.action,
            status=obj.status,
            remark=obj.remark,
            sort_order=obj.sort_order,
            created_by=user_id,
        )
        db.add(item)
        await db.flush()
        await db.refresh(item)
        await SensitiveWordService.invalidate_cache()
        return GetSensitiveWordDetail.model_validate(item)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateSensitiveWordParam) -> int:
        """更新敏感词。"""
        item = await sensitive_word_dao.get_by_id(db, pk)
        if item is None:
            raise errors.NotFoundError(msg='敏感词不存在')
        data = obj.model_dump(exclude_unset=True, exclude_none=True)
        if 'word' in data and data['word'] != item.word:
            existing = await sensitive_word_dao.get_by_word(db, data['word'], exclude_id=pk)
            if existing is not None:
                raise errors.ConflictError(msg='敏感词已存在')
        if data.get('action') == 'replace' and not (data.get('replacement') or item.replacement or '').strip():
            raise errors.RequestError(msg='替换模式必须提供替换词')
        if 'variants' in data:
            cleaned = [value.strip() for value in data['variants'] if value and value.strip()]
            cleaned = list(dict.fromkeys(cleaned))
            current_word = data.get('word') or item.word
            if current_word in cleaned:
                raise errors.RequestError(msg='变体词不能与主词重复')
            data['variants'] = cleaned
        if not data:
            return 0
        count = await sensitive_word_dao.update_model(db, pk, data)
        await SensitiveWordService.invalidate_cache()
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pk: int) -> int:
        """删除敏感词。"""
        item = await sensitive_word_dao.get_by_id(db, pk)
        if item is None:
            raise errors.NotFoundError(msg='敏感词不存在')
        count = await sensitive_word_dao.delete_model(db, pk)
        await SensitiveWordService.invalidate_cache()
        return count

    @staticmethod
    async def page_words(
        *,
        db: AsyncSession,
        keyword: str | None = None,
        status: str | None = None,
        action: str | None = None,
    ) -> dict[str, Any]:
        """获取敏感词分页列表。"""
        stmt = sensitive_word_dao.get_list_select(keyword=keyword, status=status, action=action)
        return await paging_data(db, stmt, schema_cls=GetSensitiveWordDetail)


sensitive_word_service: SensitiveWordService = SensitiveWordService()
