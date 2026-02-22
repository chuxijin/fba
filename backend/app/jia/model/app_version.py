#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class JiaAppVersion(Base):
    """应用版本表"""

    __tablename__ = 'jia_app_version'

    id: Mapped[id_key] = mapped_column(init=False)
    platform: Mapped[str] = mapped_column(sa.String(16), index=True, comment='平台(android/ios)')
    version: Mapped[str] = mapped_column(sa.String(32), comment='版本号(如 1.0.3)')
    build_number: Mapped[int] = mapped_column(comment='构建号')
    download_url: Mapped[str] = mapped_column(sa.String(512), comment='下载链接')
    changelog: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='更新日志')
    force_update: Mapped[bool] = mapped_column(default=False, comment='是否强制更新')
