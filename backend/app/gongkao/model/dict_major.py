#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class GkDictMajor(Base):
    """专业目录字典表（门类/类/专业三级）"""

    __tablename__ = 'gk_dict_major'
    __table_args__ = (
        sa.Index('ix_dict_major_parent', 'parent_code'),
        sa.Index('ix_dict_major_level', 'level'),
        sa.Index('ix_dict_major_edu', 'edu_level'),
        {'comment': '专业目录字典表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息
    code: Mapped[str] = mapped_column(sa.String(20), unique=True, index=True, comment='专业代码')
    name: Mapped[str] = mapped_column(sa.String(200), index=True, comment='专业名称')
    level: Mapped[int] = mapped_column(sa.Integer, comment='级别: 1学科门类 2专业类 3专业')
    parent_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='父级代码')

    # 学历层次
    edu_level: Mapped[str] = mapped_column(
        sa.String(20),
        default='本科',
        comment='学历层次: 本科/研究生',
    )

    # 别名（用于匹配）
    aliases: Mapped[list[str] | None] = mapped_column(
        ARRAY(sa.String(100)),
        default=None,
        comment='专业别名列表',
    )

    # 说明
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='专业说明')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, comment='是否启用')
