#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.service.subscription_service import subscription_service
from backend.app.admin.model import User
from backend.app.cms.crud.crud_slot import cms_slot_dao, cms_slot_log_dao
from backend.app.cms.model import CmsSlot, CmsSlotLog
from backend.app.cms.schema.slot import (
    CreateSlotParam,
    GetActiveSlot,
    GetSlotDetail,
    UpdateSlotParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone

# 新用户判定窗口(天)
NEW_USER_WINDOW_DAYS: int = 7

# 行为类型
ACTION_SHOW: int = 0
ACTION_CLICK: int = 1
ACTION_CLOSE: int = 2


class SlotService:
    """内容运营位服务类"""

    @staticmethod
    async def get_active_slots(
        *,
        db: AsyncSession,
        scene: str,
        user_id: int | None,
    ) -> list[GetActiveSlot]:
        """
        获取场景下命中的运营位列表

        :param db: 数据库会话
        :param scene: 触发场景
        :param user_id: 当前用户 ID(未登录可空)
        :return:
        """
        now = timezone.now()
        candidates = await cms_slot_dao.get_active_candidates(db, scene, now)

        result: list[GetActiveSlot] = []
        for slot in candidates:
            if not await SlotService._match_user_segment(db, slot=slot, user_id=user_id):
                continue
            if not await SlotService._match_frequency(db, slot=slot, user_id=user_id, now=now):
                continue
            result.append(GetActiveSlot.model_validate(slot))
        return result

    @staticmethod
    async def _match_user_segment(
        db: AsyncSession,
        *,
        slot: CmsSlot,
        user_id: int | None,
    ) -> bool:
        """
        判定用户是否命中运营位的分群规则

        :param db: 数据库会话
        :param slot: 运营位
        :param user_id: 用户 ID
        :return:
        """
        if slot.target_user_type == 0:
            return True

        # 未登录用户在分群规则非全部时一律不命中
        if user_id is None:
            return False

        if slot.target_user_type == 1:
            # 新用户(注册时间在窗口内)
            stmt = select(User.created_time).where(User.id == user_id)
            created_time = (await db.execute(stmt)).scalar_one_or_none()
            if not created_time:
                return False
            return (timezone.now() - created_time) <= timedelta(days=NEW_USER_WINDOW_DAYS)

        if slot.target_user_type == 2:
            # 会员: 持有有效付费会员档位的订阅
            return await subscription_service.has_active_subscription(db, user_id=user_id)

        if slot.target_user_type == 3:
            # 普通用户(无任何有效会员)
            return not await subscription_service.has_active_subscription(db, user_id=user_id)

        # 99 自定义条件保留位
        return True

    @staticmethod
    async def _match_frequency(
        db: AsyncSession,
        *,
        slot: CmsSlot,
        user_id: int | None,
        now: datetime,
    ) -> bool:
        """
        判定用户是否命中运营位的频次规则

        :param db: 数据库会话
        :param slot: 运营位
        :param user_id: 用户 ID
        :param now: 当前时间
        :return:
        """
        # 未登录用户跳过频次校验,前端用 Storage 兜底
        if user_id is None:
            return True

        if slot.max_show_per_user > 0:
            shown = await cms_slot_log_dao.count_by_action(db, slot_id=slot.id, user_id=user_id, action=ACTION_SHOW)
            if shown >= slot.max_show_per_user:
                return False

        if slot.max_show_per_day_per_user > 0:
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_shown = await cms_slot_log_dao.count_by_action(
                db, slot_id=slot.id, user_id=user_id, action=ACTION_SHOW, since=today_start
            )
            if today_shown >= slot.max_show_per_day_per_user:
                return False

        if slot.close_dismiss_count > 0:
            closed = await cms_slot_log_dao.count_by_action(db, slot_id=slot.id, user_id=user_id, action=ACTION_CLOSE)
            if closed >= slot.close_dismiss_count:
                return False

        return True

    @staticmethod
    async def report_action(
        *,
        db: AsyncSession,
        slot_id: int,
        user_id: int | None,
        action: int,
        scene: str | None,
    ) -> None:
        """
        上报运营位行为

        :param db: 数据库会话
        :param slot_id: 运营位 ID
        :param user_id: 用户 ID(未登录可空)
        :param action: 行为类型(0 曝光 1 点击 2 关闭)
        :param scene: 触发场景
        :return:
        """
        if action not in (ACTION_SHOW, ACTION_CLICK, ACTION_CLOSE):
            raise errors.RequestError(msg='非法行为类型')

        slot = await cms_slot_dao.select_model(db, slot_id)
        if not slot:
            raise errors.NotFoundError(msg='运营位不存在')

        log = CmsSlotLog(slot_id=slot_id, action=action, user_id=user_id, scene=scene)
        db.add(log)
        await db.commit()

    @staticmethod
    async def create_slot(
        *,
        db: AsyncSession,
        user_id: int,
        obj: CreateSlotParam,
    ) -> GetSlotDetail:
        """
        创建运营位

        :param db: 数据库会话
        :param user_id: 创建者用户 ID
        :param obj: 创建参数
        :return:
        """
        existing = await cms_slot_dao.get_by_code(db, obj.code)
        if existing:
            raise errors.RequestError(msg='业务码已存在')

        data = obj.model_dump()
        data['created_by'] = user_id
        slot = CmsSlot(**data)
        db.add(slot)
        await db.commit()
        await db.refresh(slot)
        return GetSlotDetail.model_validate(slot)

    @staticmethod
    async def update_slot(
        *,
        db: AsyncSession,
        pk: int,
        obj: UpdateSlotParam,
    ) -> int:
        """
        更新运营位

        :param db: 数据库会话
        :param pk: 运营位 ID
        :param obj: 更新参数
        :return:
        """
        slot = await cms_slot_dao.select_model(db, pk)
        if not slot:
            raise errors.NotFoundError(msg='运营位不存在')
        data = obj.model_dump(exclude_unset=True)
        if not data:
            return 0
        count = await cms_slot_dao.update_model(db, pk, data)
        return count

    @staticmethod
    async def delete_slot(*, db: AsyncSession, pk: int) -> int:
        """
        删除运营位

        :param db: 数据库会话
        :param pk: 运营位 ID
        :return:
        """
        slot = await cms_slot_dao.select_model(db, pk)
        if not slot:
            raise errors.NotFoundError(msg='运营位不存在')
        return await cms_slot_dao.delete_model(db, pk)

    @staticmethod
    async def get_slot_detail(*, db: AsyncSession, pk: int) -> GetSlotDetail:
        """
        获取运营位详情

        :param db: 数据库会话
        :param pk: 运营位 ID
        :return:
        """
        slot = await cms_slot_dao.select_model(db, pk)
        if not slot:
            raise errors.NotFoundError(msg='运营位不存在')
        return GetSlotDetail.model_validate(slot)

    @staticmethod
    async def get_slot_list(
        *,
        db: AsyncSession,
        status: int | None = None,
        slot_type: str | None = None,
        scene: str | None = None,
        keyword: str | None = None,
    ) -> dict:
        """
        获取运营位分页列表

        :param db: 数据库会话
        :param status: 状态过滤
        :param slot_type: 形态过滤
        :param scene: 场景过滤
        :param keyword: 搜索关键词
        :return:
        """
        stmt = await cms_slot_dao.get_select(status=status, slot_type=slot_type, scene=scene, keyword=keyword)
        return await paging_data(db, stmt)


slot_service: SlotService = SlotService()
