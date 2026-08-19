#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class SysSensitiveWord(Base, UserMixin):
    """敏感词表"""

    __tablename__ = 'sensitive_word'
    __table_args__ = (
        sa.UniqueConstraint('word', 'deleted', name='uq_sensitive_word'),
        sa.CheckConstraint("action IN ('replace','block','reject')", name='ck_sensitive_word_action'),
        sa.CheckConstraint("status IN ('active','disabled')", name='ck_sensitive_word_status'),
        sa.Index('ix_sensitive_word_status', 'status'),
        {'comment': '敏感词表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    word: Mapped[str] = mapped_column(sa.String(128), comment='敏感词')
    variants: Mapped[list[str]] = mapped_column(
        CompatibleJSONB,
        default_factory=list,
        comment='变体词库（拼音/谐音/缩写），命中任意一个即按本词处理',
    )
    replacement: Mapped[str | None] = mapped_column(
        sa.String(128),
        default=None,
        comment='替换词（action=replace 时生效，如 政府 -> ZF）',
    )
    action: Mapped[str] = mapped_column(
        sa.String(16),
        default='replace',
        comment='replace 替换 / block 打码 / reject 拦截',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='active', comment='active/disabled')
    remark: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='备注')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')


class SensitiveHitLog(Base):
    """敏感词命中日志表"""

    __tablename__ = 'sensitive_hit_log'
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['word_id'],
            ['sensitive_word.id'],
            name='fk_sensitive_hit_word',
            ondelete='SET NULL',
        ),
        sa.Index('ix_sensitive_hit_user_time', 'user_id', 'created_time'),
        sa.Index('ix_sensitive_hit_word', 'word_id'),
        sa.Index('ix_sensitive_hit_target', 'target_type', 'target_id'),
        {'comment': '敏感词命中日志表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='触发者用户 ID')
    word: Mapped[str] = mapped_column(sa.String(128), comment='敏感词快照')
    keyword: Mapped[str] = mapped_column(sa.String(128), comment='实际命中的词/变体')
    word_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='敏感词 ID')
    action: Mapped[str] = mapped_column(sa.String(16), default='replace', comment='处理方式快照')
    replacement: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='替换词快照')
    hit_count: Mapped[int] = mapped_column(sa.Integer, default=1, comment='命中次数')
    target_type: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='命中内容类型，如 memory_card')
    target_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='命中内容 ID')
    snippet: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='命中内容摘要')
