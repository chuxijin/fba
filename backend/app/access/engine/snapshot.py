#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.crud.crud_grant import direct_grant_dao
from backend.app.access.crud.crud_pack import pack_item_dao
from backend.app.access.crud.crud_subscription import subscription_dao
from backend.app.access.crud.crud_template import template_pack_dao
from backend.app.access.model.grant import DirectGrant
from backend.app.access.model.pack import PackItem
from backend.app.access.model.subscription import Subscription


class UserGrantSnapshot:
    """用户权益快照(只读, 不可变)"""

    def __init__(
        self,
        user_id: int,
        ts: datetime,
        subscriptions: Sequence[Subscription],
        pack_items: Sequence[PackItem],
        direct_grants: Sequence[DirectGrant],
        entitlement_value_map: dict[str, int],
    ) -> None:
        self.user_id = user_id
        self.ts = ts
        self._subscriptions = list(subscriptions)
        self._pack_items = list(pack_items)
        self._direct_grants = list(direct_grants)
        self._entitlement_value_map = dict(entitlement_value_map)

    @property
    def subscriptions(self) -> list[Subscription]:
        """当前生效订阅列表"""
        return self._subscriptions

    @property
    def direct_grants(self) -> list[DirectGrant]:
        """当前生效直接授予列表"""
        return self._direct_grants

    @property
    def entitlement_codes(self) -> set[str]:
        """用户通过订阅持有的全部权益编码"""
        return set(self._entitlement_value_map.keys())

    def has_subscription_entitlement(self, code: str) -> bool:
        """
        判断是否通过订阅持有权益

        :param code: 权益编码
        :return:
        """
        return code in self._entitlement_value_map

    def get_subscription_value(self, code: str) -> int:
        """
        获取订阅权益的数值(若同码多包取最大值)

        :param code: 权益编码
        :return:
        """
        return int(self._entitlement_value_map.get(code, 0))

    def has_direct_grant(self, code: str) -> bool:
        """
        判断是否有有效的直接授予

        :param code: 权益编码
        :return:
        """
        return any(grant.entitlement_code == code for grant in self._direct_grants)


class SnapshotService:
    """用户权益快照加载器"""

    @classmethod
    async def load(cls, db: AsyncSession, *, user_id: int, ts: datetime) -> UserGrantSnapshot:
        """
        构建用户在指定时刻的权益快照

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        subscriptions = await subscription_dao.list_active_for_user(db, user_id, ts)
        direct_grants = await direct_grant_dao.list_active_for_user(db, user_id=user_id, ts=ts)

        if not subscriptions:
            return UserGrantSnapshot(
                user_id=user_id,
                ts=ts,
                subscriptions=[],
                pack_items=[],
                direct_grants=direct_grants,
                entitlement_value_map={},
            )

        template_ids = [sub.template_id for sub in subscriptions]
        template_packs = await template_pack_dao.get_by_templates(db, template_ids)
        pack_ids = list({tp.pack_id for tp in template_packs})
        pack_items: Sequence[PackItem] = await pack_item_dao.get_by_packs(db, pack_ids) if pack_ids else []

        value_map: dict[str, int] = {}
        all_entitlement_ids = list({item.entitlement_id for item in pack_items})
        entitlement_map: dict[int, str] = {}
        if all_entitlement_ids:
            from sqlalchemy import select as sa_select

            from backend.app.access.model.entitlement import Entitlement

            stmt = sa_select(Entitlement).where(Entitlement.id.in_(all_entitlement_ids))
            rows = (await db.execute(stmt)).scalars().all()
            entitlement_map = {row.id: row.code for row in rows}

        for item in pack_items:
            code = entitlement_map.get(item.entitlement_id)
            if not code:
                continue
            current_value = value_map.get(code, 0)
            value = item.value_int if item.value_int is not None else 1
            if value > current_value:
                value_map[code] = value

        return UserGrantSnapshot(
            user_id=user_id,
            ts=ts,
            subscriptions=subscriptions,
            pack_items=pack_items,
            direct_grants=direct_grants,
            entitlement_value_map=value_map,
        )

    @classmethod
    def to_audit_dict(cls, snapshot: UserGrantSnapshot) -> dict[str, Any]:
        """
        生成可审计字典(用于决策日志 context)

        :param snapshot: 用户权益快照
        :return:
        """
        return {
            'subscription_ids': [s.id for s in snapshot.subscriptions],
            'direct_grant_ids': [g.id for g in snapshot.direct_grants],
            'entitlement_codes': sorted(snapshot.entitlement_codes),
        }


snapshot_service: SnapshotService = SnapshotService()
