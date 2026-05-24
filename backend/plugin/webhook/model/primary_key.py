#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import BigInteger
from sqlalchemy.orm import MappedColumn, mapped_column

from backend.common.enums import PrimaryKeyType
from backend.core.conf import settings
from backend.utils.snowflake import snowflake


def webhook_id_column() -> MappedColumn[int]:
    """生成 Webhook 模型主键列"""
    if PrimaryKeyType.autoincrement == settings.DATABASE_PK_MODE:
        return mapped_column(
            BigInteger,
            init=False,
            primary_key=True,
            unique=True,
            index=True,
            autoincrement=True,
            sort_order=-999,
            comment='主键 ID',
        )

    return mapped_column(
        BigInteger,
        init=False,
        primary_key=True,
        unique=True,
        index=True,
        default=snowflake.generate,
        sort_order=-999,
        comment='雪花算法主键 ID',
    )
