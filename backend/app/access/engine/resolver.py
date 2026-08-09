#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.crud.crud_rule import resource_rule_dao
from backend.app.access.model.rule import ResourceRule


class RuleResolver:
    """资源规则解析器"""

    @classmethod
    async def resolve(
        cls,
        db: AsyncSession,
        *,
        resource_type: str,
        resource_id: int,
        ts: datetime,
        audience_attrs: dict[str, Any] | None = None,
    ) -> Sequence[ResourceRule]:
        """
        解析资源在指定时刻对当前用户生效的所有规则

        :param db: 数据库会话
        :param resource_type: 资源类型
        :param resource_id: 资源 ID
        :param ts: 时间点
        :param audience_attrs: 用户画像快照
        :return:
        """
        rules = await resource_rule_dao.resolve_for_resource(
            db,
            resource_type=resource_type,
            resource_id=resource_id,
            ts=ts,
        )
        if not rules:
            return []

        attrs = audience_attrs or {}
        matched: list[ResourceRule] = []
        for rule in rules:
            if cls._match_audience(rule.audience_filter, attrs):
                matched.append(rule)
        return matched

    @staticmethod
    def _match_audience(audience_filter: dict[str, Any], audience_attrs: dict[str, Any]) -> bool:
        """
        判断受众过滤是否匹配

        无画像时对"声明了人群条件"的规则一律不匹配(fail-closed)。若在此处放行,
        由于生产链路普遍不传 audience_attrs, 一条 audience_filter 规则会对所有人
        生效 —— 与运营的定向意图完全相反。

        :param audience_filter: 规则上的过滤声明
        :param audience_attrs: 用户画像
        :return:
        """
        if not audience_filter:
            return True
        if not audience_attrs:
            return False
        for key, expected in audience_filter.items():
            actual = audience_attrs.get(key)
            if isinstance(expected, dict):
                if 'gte' in expected and not (actual is not None and actual >= expected['gte']):
                    return False
                if 'lte' in expected and not (actual is not None and actual <= expected['lte']):
                    return False
                if 'in' in expected and actual not in expected['in']:
                    return False
            elif actual != expected:
                return False
        return True


rule_resolver: RuleResolver = RuleResolver()
