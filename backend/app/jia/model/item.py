#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key
from backend.utils.timezone import timezone


class JiaItem(Base, UserMixin):
    """物品表"""

    __tablename__ = 'jia_item'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(128), comment='物品名称')
    category: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='分类')
    quantity: Mapped[int] = mapped_column(default=1, comment='当前数量')
    standard_quantity: Mapped[int] = mapped_column(default=1, comment='标准数量')
    consume_days: Mapped[int | None] = mapped_column(default=None, comment='消耗周期(天)-多少天用完标准量')
    expire_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='保质期(到期日期)')
    status: Mapped[str] = mapped_column(sa.String(16), default='充足', comment='状态')
    description: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='描述')
    location: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='存放位置')
    acquired_date: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='购入日期')
    price: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='价格')
    disposal_method: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='处置方式')
    image_path: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='图片路径')
    notes: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')

    def calculate_status(self) -> str:
        """
        根据数量、消耗周期、保质期计算状态

        优先级：已过期 > 即将过期 > 缺失 > 即将用完 > 待补货 > 充足
        """
        now = timezone.now()
        today = now.date()

        # 1. 检查保质期
        if self.expire_date:
            if today > self.expire_date:
                return '已过期'

            # 计算保质期总长（从 updated_time 到 expire_date）
            if self.updated_time:
                total_days = (self.expire_date - self.updated_time.date()).days
                days_left = (self.expire_date - today).days
                if total_days > 0 and days_left <= total_days * 0.1:
                    return '即将过期'

        # 2. 检查数量
        if self.quantity <= 0:
            return '缺失'

        # 3. 检查消耗周期
        if self.consume_days and self.standard_quantity > 0:
            # 剩余可用天数 = (当前数量 / 标准数量) * 消耗周期
            remaining_days = (self.quantity / self.standard_quantity) * self.consume_days
            threshold = self.consume_days * 0.1
            if remaining_days <= threshold:
                return '即将用完'

        # 4. 检查是否低于标准量
        if self.quantity < self.standard_quantity:
            return '待补货'

        return '充足'

    def update_status(self) -> None:
        """更新状态字段"""
        self.status = self.calculate_status()
