#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, time, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.payment.model.pay_order import PayOrder
from backend.app.payment.schema.my_orders import MyOrderQuery
from backend.utils.timezone import timezone


class CRUDPayOrder(CRUDPlus[PayOrder]):
    """支付业务订单数据库操作类"""

    async def create_from_dict(self, db: AsyncSession, data: dict[str, object]) -> PayOrder:
        """
        通过字典创建支付业务订单

        :param db: 数据库会话
        :param data: 订单数据
        :return:
        """
        order = PayOrder(**data)
        db.add(order)
        await db.flush()
        return order

    async def get(self, db: AsyncSession, pk: int) -> PayOrder | None:
        """
        获取支付业务订单详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_order_no(self, db: AsyncSession, order_no: str, *, for_update: bool = False) -> PayOrder | None:
        """
        通过业务订单号查询

        :param db: 数据库会话
        :param order_no: 业务订单号
        :param for_update: 是否锁定订单并刷新会话中的旧数据
        :return:
        """
        if not for_update:
            return await self.select_model_by_column(db, order_no=order_no)
        stmt = (
            select(PayOrder)
            .where(PayOrder.order_no == order_no)
            # 主键及订单号不变：仍互斥业务写入，同时允许任务表外键核验。
            .with_for_update(key_share=True)
            .execution_options(populate_existing=True)
        )
        return (await db.execute(stmt)).scalars().first()

    async def get_by_user(self, db: AsyncSession, user_id: int, status: str | None = None) -> list[PayOrder]:
        """
        获取用户支付业务订单列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态过滤
        :return:
        """
        stmt = select(PayOrder).where(PayOrder.user_id == user_id, self.user_visible())
        if status:
            stmt = stmt.where(PayOrder.status == status)
        stmt = stmt.order_by(PayOrder.created_time.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def user_visible() -> ColumnElement[bool]:
        """迟到支付/退款处理中重新显示，用户隐藏不能遮住仍需处理的交易。"""
        return and_(
            PayOrder.deleted == 0,
            or_(PayOrder.user_hidden_at.is_(None), PayOrder.status.not_in(('closed', 'refunded'))),
        )

    async def get_user_page(self, db: AsyncSession, user_id: int, query: MyOrderQuery) -> tuple[list[PayOrder], int]:
        """在数据库中筛选分页，避免只筛选客户端已加载的一页。"""
        filters = [PayOrder.user_id == user_id, self.user_visible()]
        if query.status == 'refund':
            filters.append(PayOrder.status.in_(('refund_pending', 'refunded')))
        elif query.status != 'all':
            filters.append(PayOrder.status == query.status)
        if query.biz_type:
            filters.append(PayOrder.biz_type == query.biz_type)
        if query.pay_type:
            filters.append(PayOrder.pay_type == query.pay_type)
        if query.keyword:
            value = query.keyword.strip()
            filters.append(
                or_(
                    PayOrder.order_no.icontains(value, autoescape=True),
                    PayOrder.item_name.icontains(value, autoescape=True),
                )
            )
        if query.created_from:
            filters.append(PayOrder.created_time >= datetime.combine(query.created_from, time.min, timezone.tz_info))
        if query.created_to:
            filters.append(
                PayOrder.created_time
                < datetime.combine(query.created_to + timedelta(days=1), time.min, timezone.tz_info)
            )
        total = await db.scalar(select(func.count()).select_from(PayOrder).where(*filters))
        stmt = (
            select(PayOrder)
            .where(*filters)
            .order_by(PayOrder.created_time.desc(), PayOrder.id.desc())
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        return list((await db.execute(stmt)).scalars().all()), int(total or 0)

    async def get_user_filter_options(self, db: AsyncSession, user_id: int) -> tuple[list[str], list[str]]:
        """选项仅来自当前用户可见的订单，不泄漏其他用户的业务类型。"""
        filters = [PayOrder.user_id == user_id, self.user_visible()]
        biz_types = (
            await db.scalars(select(PayOrder.biz_type).where(*filters).distinct().order_by(PayOrder.biz_type))
        ).all()
        pay_types = (
            await db.scalars(select(PayOrder.pay_type).where(*filters).distinct().order_by(PayOrder.pay_type))
        ).all()
        return list(biz_types), list(pay_types)

    async def get_timeout_pending_orders(
        self,
        db: AsyncSession,
        *,
        created_before: datetime,
        limit: int = 100,
    ) -> list[PayOrder]:
        """
        获取超时未支付订单

        :param db: 数据库会话
        :param created_before: 创建时间上限
        :param limit: 批量数量
        :return:
        """
        stmt = (
            select(PayOrder)
            .where(PayOrder.status == 'pending', PayOrder.created_time < created_before)
            .order_by(PayOrder.created_time.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


pay_order_dao = CRUDPayOrder(PayOrder)
