#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class BiliDuplicateCheck(Base):
    """B 站用户操作记录表"""

    __tablename__ = 'bili_duplicate_check'

    id: Mapped[id_key] = mapped_column(init=False)
    mid: Mapped[str] = mapped_column(sa.String(64), index=True, comment='被操作的 B 站用户 MID')
    operation_type: Mapped[str] = mapped_column(
        sa.String(32), index=True, comment='操作类型(at @/comment 评论/message 私信)'
    )
    is_active: Mapped[bool] = mapped_column(default=False, index=True, comment='是否主动操作(0 被动 1 主动)')
    send_content: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='内容摘要')
    send_result: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='发送结果(JSON 格式)')

    # 逻辑外键
    work_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='作品关联 ID')
    execution_log_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, default=None, index=True, comment='任务执行记录 ID'
    )

