#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""能力 URL 派生服务：基于 catalog.url_base + param_schema 与计划项 extra，重写出最终 URL"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.study_plan.schema.ability import GetStudyPlanAbilityCatalogItem
from backend.app.study_plan.service.ability_catalog import (
    get_ability_catalog_item,
    list_ability_catalog_with_db,
)


async def get_catalog_by_key(
    db: AsyncSession | None,
    ability_key: str,
    domain: str | None = None,
) -> GetStudyPlanAbilityCatalogItem | None:
    """
    按 key 解析能力目录（DB 优先，静态兜底）

    :param db: 数据库会话
    :param ability_key: 能力标识
    :param domain: 业务领域
    :return:
    """
    if db is not None:
        items = await list_ability_catalog_with_db(db, domain=domain, include_inactive=True)
        for item in items:
            if item.key == ability_key:
                return item
    return get_ability_catalog_item(ability_key)


def derive_ability_url(
    catalog: GetStudyPlanAbilityCatalogItem,
    extra: dict[str, Any] | None,
) -> str:
    """
    根据 catalog 的 url_base + param_schema 与计划项 extra，派生最终 URL

    优先级（每个参数）：
    1. 计划项 extra 里的同名键
    2. param_schema 通过 bind_to 映射 extra 里的逻辑字段（如 count.bind_to='question_count'）
    3. param_schema 的 default

    若 catalog 没有 url_base 或 param_schema，回退到 catalog.url 原值

    :param catalog: 能力目录
    :param extra: 计划项 extra
    :return:
    """
    if not catalog.url_base or not catalog.param_schema:
        return catalog.url

    extra_dict = dict(extra or {})
    final_params: dict[str, Any] = {}

    for param_name, spec in catalog.param_schema.items():
        if not isinstance(spec, dict):
            continue
        value = _resolve_param_value(param_name, spec, extra_dict)
        if value is None or value == '':
            continue
        final_params[param_name] = value

    if not final_params:
        return catalog.url_base

    return f'{catalog.url_base}?{urlencode(final_params, doseq=False)}'


def _resolve_param_value(
    param_name: str,
    spec: dict[str, Any],
    extra: dict[str, Any],
) -> Any:
    """
    解析单个 URL 参数的最终值

    :param param_name: URL 参数名
    :param spec: 参数 schema
    :param extra: 计划项 extra
    :return:
    """
    if param_name in extra:
        return _coerce(spec.get('type'), extra[param_name], spec)

    bind_to = spec.get('bind_to')
    if isinstance(bind_to, str) and bind_to and bind_to in extra:
        return _coerce(spec.get('type'), extra[bind_to], spec)

    if 'default' in spec:
        return _coerce(spec.get('type'), spec['default'], spec)

    return None


def _coerce(value_type: str | None, value: Any, spec: dict[str, Any]) -> Any:
    """
    按 schema type 做温和的值转换与裁剪

    :param value_type: schema 声明的类型 (int/string/enum)
    :param value: 原始值
    :param spec: 参数 schema
    :return:
    """
    if value is None:
        return None

    if value_type == 'int':
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        min_value = spec.get('min')
        max_value = spec.get('max')
        if isinstance(min_value, (int, float)):
            parsed = max(int(min_value), parsed)
        if isinstance(max_value, (int, float)):
            parsed = min(int(max_value), parsed)
        return parsed

    if value_type == 'enum':
        options = spec.get('options')
        if isinstance(options, list) and value not in options:
            return spec.get('default')
        return value

    return value


async def enrich_ability_item_extra(
    db: AsyncSession | None,
    extra: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """
    若 extra 含 ability_key 且对应 catalog 有 url_base/param_schema，重写 ability_url

    幂等：同样的 extra 入参始终产生同样的 ability_url 输出

    :param db: 数据库会话
    :param extra: 计划项 extra
    :return:
    """
    if not extra:
        return extra

    ability_key = extra.get('ability_key')
    if not isinstance(ability_key, str) or not ability_key:
        return extra

    catalog = await get_catalog_by_key(db, ability_key)
    if catalog is None:
        return extra

    derived_url = derive_ability_url(catalog, extra)
    new_extra = dict(extra)
    new_extra['ability_url'] = derived_url
    if not new_extra.get('ability_title') and catalog.title:
        new_extra['ability_title'] = catalog.title
    return new_extra
