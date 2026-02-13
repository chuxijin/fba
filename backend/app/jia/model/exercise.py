#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import String, Float
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from backend.common.model import Base, UserMixin, id_key


class Exercise(Base, UserMixin):
    """健身动作表"""

    __tablename__ = 'jia_exercise'

    id: Mapped[id_key] = mapped_column(init=False)
    
    # 基本信息
    name_zh: Mapped[str] = mapped_column(String(128), index=True, comment='动作名称(中文)')
    name_en: Mapped[str] = mapped_column(String(128), index=True, comment='动作名称(英文)')
    category: Mapped[str] = mapped_column(String(64), index=True, comment='分类')
    
    # 属性标签（虽然可以用 ID，但这种枚举值少的也可以直接存字符串，或者用字典表）
    # 这里为了简便和导入脚本处理，先存中文字符串，也可以后续优化为字典
    difficulty: Mapped[str | None] = mapped_column(String(32), default=None, comment='难度(初级/中级/高级)')
    mechanic: Mapped[str | None] = mapped_column(String(32), default=None, comment='机制(复合/孤立)')
    force: Mapped[str | None] = mapped_column(String(32), default=None, comment='发力(推/拉/静止)')
    equipment: Mapped[str | None] = mapped_column(String(64), default=None, comment='器械(哑铃/杠铃/徒手)')
    
    # 核心数据
    met_value: Mapped[float | None] = mapped_column(Float, default=None, comment='代谢当量(MET) - 用于计算热量')
    primary_muscles: Mapped[list[str] | None] = mapped_column(JSONB, default=None, comment='主要肌肉群(中文)')
    secondary_muscles: Mapped[list[str] | None] = mapped_column(JSONB, default=None, comment='次要肌肉群(中文)')
    
    # 详细内容 (JSONB)
    images: Mapped[list[str] | None] = mapped_column(JSONB, default=None, comment='动作图片/GIF链接')
    instructions: Mapped[list[str] | None] = mapped_column(JSONB, default=None, comment='动作步骤(中文)')
    instructions_en: Mapped[list[str] | None] = mapped_column(JSONB, default=None, comment='动作步骤(英文原版)')
    
    # 向量搜索
    vector: Mapped[list[float] | None] = mapped_column(
        Vector(1536), deferred=True, default=None, comment='向量化数据(1536维，默认不加载)'
    )
