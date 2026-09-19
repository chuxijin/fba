#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# 定时表达式：标准 5 段式（分 时 日 月 周），croniter 原生支持
CRON_DESCRIPTION = '定时表达式，标准 5 段式（分 时 日 月 周），留空则不定时执行'


class CreateFeishuSheetConfigParam(SchemaBase):
    """创建飞书表导出配置参数"""

    name: str = Field(min_length=1, max_length=128, description='配置名称，如「公考」')
    app_code: str = Field(min_length=1, max_length=64, description='分类来源：sys_category.app_code')
    sheet_url: str = Field(min_length=1, max_length=512, description='飞书表格地址')
    category_type: str = Field(default='knowledge_point', min_length=1, max_length=64, description='分类来源：sys_category.type')
    description: str = Field(default='', max_length=500, description='备注说明')
    sheet_map: dict[str, str] = Field(default_factory=dict, description='资源类型 -> 子表名称')
    category_options: list[str] = Field(default_factory=list, description='分类列下拉选项')
    source_weights: dict[str, int] = Field(default_factory=dict, description='来源 -> 随机权重')
    paid_sheets: list[str] = Field(default_factory=list, description='允许出现「店铺购买」来源的子表')
    cron: str | None = Field(default=None, max_length=128, description=CRON_DESCRIPTION)
    end_time: datetime | None = Field(default=None, description='配置结束时间')


class UpdateFeishuSheetConfigParam(SchemaBase):
    """更新飞书表导出配置参数"""

    name: str | None = Field(default=None, min_length=1, max_length=128, description='配置名称')
    app_code: str | None = Field(default=None, min_length=1, max_length=64, description='分类来源：sys_category.app_code')
    sheet_url: str | None = Field(default=None, min_length=1, max_length=512, description='飞书表格地址')
    category_type: str | None = Field(default=None, min_length=1, max_length=64, description='分类来源：sys_category.type')
    description: str | None = Field(default=None, max_length=500, description='备注说明')
    sheet_map: dict[str, str] | None = Field(default=None, description='资源类型 -> 子表名称')
    category_options: list[str] | None = Field(default=None, description='分类列下拉选项')
    source_weights: dict[str, int] | None = Field(default=None, description='来源 -> 随机权重')
    paid_sheets: list[str] | None = Field(default=None, description='允许出现「店铺购买」来源的子表')
    is_enabled: bool | None = Field(default=None, description='是否启用')
    cron: str | None = Field(default=None, max_length=128, description=CRON_DESCRIPTION)
    end_time: datetime | None = Field(default=None, description='配置结束时间')


class GetFeishuSheetConfigDetail(SchemaBase):
    """飞书表导出配置详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='导出配置 ID')
    name: str = Field(description='配置名称')
    app_code: str = Field(description='分类来源：sys_category.app_code')
    sheet_url: str = Field(description='飞书表格地址')
    category_type: str = Field(description='分类来源：sys_category.type')
    description: str = Field(description='备注说明')
    sheet_map: dict = Field(description='资源类型 -> 子表名称')
    category_options: list = Field(description='分类列下拉选项')
    source_weights: dict = Field(description='来源 -> 随机权重')
    paid_sheets: list = Field(description='允许出现「店铺购买」来源的子表')
    is_enabled: bool = Field(description='是否启用')
    cron: str | None = Field(description='定时表达式')
    end_time: datetime | None = Field(description='配置结束时间')
    last_synced_at: datetime | None = Field(description='最近同步时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class GetFeishuSheetTaskDetail(SchemaBase):
    """飞书表导出任务详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='导出任务 ID')
    config_id: int = Field(description='导出配置 ID')
    status: str = Field(description='任务状态')
    statistics: dict = Field(description='任务统计信息')
    error_message: str | None = Field(description='错误信息')
    started_at: datetime | None = Field(description='开始时间')
    finished_at: datetime | None = Field(description='完成时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class GetFeishuCategorySourceOption(SchemaBase):
    """可选分类来源（app_code + category_type 组合）"""

    app_code: str = Field(description='应用标识，如 youanshang')
    category_type: str = Field(description='分类类型，如 knowledge_point')
    category_count: int = Field(description='该组合下的分类数量，便于确认选对了来源')
    sample_names: list[str] = Field(default_factory=list, description='分类名示例，便于人工确认')
