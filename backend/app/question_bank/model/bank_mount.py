#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from .bank import QuestionBank


class QuestionBankMount(Base, UserMixin):
    """刷题内容挂载表"""

    __tablename__ = 'study_question_bank_mount'
    __table_args__ = (
        sa.UniqueConstraint('collection_id', 'item_id', name='uq_study_question_bank_mount_collection_item'),
        sa.CheckConstraint('collection_id <> item_id', name='ck_study_question_bank_mount_not_self'),
        sa.Index('idx_study_question_bank_mount_collection_sort', 'collection_id', 'status', 'sort_order'),
        sa.Index('idx_study_question_bank_mount_item', 'item_id', 'status'),
        {'comment': '刷题内容挂载表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    collection_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='CASCADE'),
        comment='合集 ID',
    )
    item_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='CASCADE'),
        comment='被挂载内容 ID',
    )
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序权重')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='状态')

    collection: Mapped['QuestionBank'] = relationship(
        init=False,
        foreign_keys=lambda: [QuestionBankMount.collection_id],
        lazy='noload',
    )
    item: Mapped['QuestionBank'] = relationship(
        init=False,
        foreign_keys=lambda: [QuestionBankMount.item_id],
        lazy='noload',
    )
