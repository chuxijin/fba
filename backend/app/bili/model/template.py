#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class BiliTemplate(Base):
    """B 站模板话术表"""

    __tablename__ = 'bili_template'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(128), index=True, comment='模板名称')
    template_type: Mapped[str] = mapped_column(
        sa.String(32), index=True, comment='模板类型(comment 评论/message 私信)'
    )
    content: Mapped[str] = mapped_column(sa.Text, comment='模板内容')
    keywords: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='关键词触发条件(JSON 格式)')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态(0 停用 1 正常)')

    # 逻辑外键
    category_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='分类关联 ID')
