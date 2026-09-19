#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.app.mydrive.model.account import CompatibleJSONB
from backend.common.model import Base, TimeZone, id_key


class FeishuSheetConfig(Base):
    """飞书表格导出配置表"""

    __tablename__ = 'feishu_sheet_config'
    __table_args__ = (
        sa.UniqueConstraint('name', name='uq_feishu_sheet_config_name'),
        sa.Index('idx_feishu_sheet_config_enabled', 'is_enabled'),
        {'comment': '飞书表格导出配置表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(128), comment='配置名称，如「公考」')
    app_code: Mapped[str] = mapped_column(sa.String(64), comment='分类来源：sys_category.app_code')
    sheet_url: Mapped[str] = mapped_column(sa.String(512), comment='飞书表格地址')
    category_type: Mapped[str] = mapped_column(
        sa.String(64), default='knowledge_point', comment='分类来源：sys_category.type'
    )
    description: Mapped[str] = mapped_column(sa.String(500), default='', comment='备注说明')
    sheet_map: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='资源类型 -> 子表名称')
    category_options: Mapped[list] = mapped_column(CompatibleJSONB, default_factory=list, comment='分类列下拉选项')
    source_weights: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='来源 -> 随机权重')
    paid_sheets: Mapped[list] = mapped_column(
        CompatibleJSONB, default_factory=list, comment='允许出现「店铺购买」来源的子表'
    )
    is_enabled: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    cron: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='定时表达式')
    end_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='配置结束时间')
    last_synced_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近同步时间')


class FeishuSheetTask(Base):
    """飞书表格导出任务表"""

    __tablename__ = 'feishu_sheet_task'
    __table_args__ = (
        sa.Index('idx_feishu_sheet_task_config_status', 'config_id', 'status'),
        sa.CheckConstraint(
            "status IN ('pending','running','completed','failed','cancelled')",
            name='ck_feishu_sheet_task_status',
        ),
        {'comment': '飞书表格导出任务表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    config_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('feishu_sheet_config.id', ondelete='CASCADE'),
        comment='导出配置 ID',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='pending', comment='任务状态')
    statistics: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='任务统计信息')
    error_message: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='错误信息')
    started_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    finished_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')
