#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class BiliTaskExecutionLog(Base):
    """B 站任务执行记录表"""

    __tablename__ = 'bili_task_execution_log'

    id: Mapped[id_key] = mapped_column(init=False)

    # ===== 必填字段（无默认值） =====
    task_config_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='任务配置 ID')
    task_name: Mapped[str] = mapped_column(sa.String(128), comment='任务名称（冗余）')
    task_type: Mapped[str] = mapped_column(sa.String(32), comment='任务类型（冗余）')
    start_time: Mapped[str] = mapped_column(sa.DateTime, comment='开始执行时间')
    execution_status: Mapped[str] = mapped_column(sa.String(16), comment='执行状态: SUCCESS/FAIL/FATAL')

    # ===== 可选字段（有默认值） =====
    end_time: Mapped[str | None] = mapped_column(sa.DateTime, default=None, comment='结束执行时间')
    duration_seconds: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='执行耗时（秒）')
    comments_fetched: Mapped[int] = mapped_column(sa.Integer, default=0, comment='获取的评论数')
    users_processed: Mapped[int] = mapped_column(sa.Integer, default=0, comment='处理的用户数')
    users_skipped: Mapped[int] = mapped_column(sa.Integer, default=0, comment='跳过的用户数（去重+筛选）')
    send_success: Mapped[int] = mapped_column(sa.Integer, default=0, comment='发送成功数')
    send_fail: Mapped[int] = mapped_column(sa.Integer, default=0, comment='发送失败数')
    error_message: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='错误信息')
    work_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='关联作品 ID')
    account_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='执行账号 ID')

