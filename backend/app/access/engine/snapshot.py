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
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import JsonSerializer


_SNAPSHOT_CACHE_TTL = 60


snapshot_payload_cache: RedisCache[dict[str, Any]] = RedisCache(
    prefix='access:snapshot',
    ttl=_SNAPSHOT_CACHE_TTL,
    serializer=JsonSerializer(),
)


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
        cached_direct_grant_codes: set[str] | None = None,
        cached_subscription_ids: list[int] | None = None,
        cached_direct_grant_ids: list[int] | None = None,
    ) -> None:
        self.user_id = user_id
        self.ts = ts
        self._subscriptions = list(subscriptions)
        self._pack_items = list(pack_items)
        self._direct_grants = list(direct_grants)
        self._entitlement_value_map = dict(entitlement_value_map)
        # 缓存命中路径: 仅持有 codes/ids, 不持有 ORM 对象, 用于 has_direct_grant 与 to_audit_dict
        self._cached_direct_grant_codes = (
            set(cached_direct_grant_codes) if cached_direct_grant_codes is not None else None
        )
        self._cached_subscription_ids = list(cached_subscription_ids) if cached_subscription_ids is not None else None
        self._cached_direct_grant_ids = list(cached_direct_grant_ids) if cached_direct_grant_ids is not None else None

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

    @property
    def all_entitlement_codes(self) -> set[str]:
        """订阅 + 直接授予持有的全部权益编码"""
        if self._cached_direct_grant_codes is not None:
            direct = set(self._cached_direct_grant_codes)
        else:
            direct = {grant.entitlement_code for grant in self._direct_grants}
        return set(self._entitlement_value_map.keys()) | direct

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
        if self._cached_direct_grant_codes is not None:
            return code in self._cached_direct_grant_codes
        return any(grant.entitlement_code == code for grant in self._direct_grants)

    def to_cache_payload(self) -> dict[str, Any]:
        """构造可 JSON 序列化的缓存 payload"""
        return {
            'user_id': self.user_id,
            'ts_iso': self.ts.isoformat(),
            'entitlement_value_map': dict(self._entitlement_value_map),
            'subscription_ids': [s.id for s in self._subscriptions],
            'direct_grant_codes': sorted({g.entitlement_code for g in self._direct_grants}),
            'direct_grant_ids': [g.id for g in self._direct_grants],
        }


class SnapshotService:
    """用户权益快照加载器"""

    @classmethod
    async def load(cls, db: AsyncSession, *, user_id: int, ts: datetime) -> UserGrantSnapshot:
        """
        构建用户在指定时刻的权益快照(命中 Redis 缓存优先)

        缓存语义边界:
        - 命中缓存的 snapshot 仅适用于"判断 code 是否拥有"类调用
          (has_subscription_entitlement / has_direct_grant / get_subscription_value)
        - 命中缓存时 subscriptions/direct_grants/pack_items 三个 ORM 列表为空
          仅 deny 路径写决策日志时才需要完整 ORM 对象, 命中放行不写日志, 因此降级安全
        - TTL=60s 兜底: 即使有遗漏的失效点(例如 expire_due 定时任务批量过期)
          最坏情况是过期 60 秒内还能错误放行, 业务可接受

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param ts: 时间点
        :return:
        """
        cached = await cls._load_from_cache(user_id=user_id, ts=ts)
        if cached is not None:
            return cached

        snapshot = await cls._load_from_db(db=db, user_id=user_id, ts=ts)
        await cls._save_to_cache(snapshot)
        return snapshot

    @classmethod
    async def _load_from_cache(cls, *, user_id: int, ts: datetime) -> UserGrantSnapshot | None:
        """尝试从 Redis 加载用户权益快照"""
        payload = await snapshot_payload_cache.get(user_id)
        if not payload:
            return None

        return UserGrantSnapshot(
            user_id=user_id,
            ts=ts,
            subscriptions=[],
            pack_items=[],
            direct_grants=[],
            entitlement_value_map=payload.get('entitlement_value_map') or {},
            cached_direct_grant_codes=set(payload.get('direct_grant_codes') or []),
            cached_subscription_ids=list(payload.get('subscription_ids') or []),
            cached_direct_grant_ids=list(payload.get('direct_grant_ids') or []),
        )

    @classmethod
    async def _save_to_cache(cls, snapshot: UserGrantSnapshot) -> None:
        """将快照语义写入 Redis"""
        await snapshot_payload_cache.set(snapshot.user_id, value=snapshot.to_cache_payload())

    @staticmethod
    async def invalidate_cache(user_id: int) -> None:
        """
        失效用户权益快照缓存

        :param user_id: 用户 ID
        :return:
        """
        await snapshot_payload_cache.invalidate(user_id)

    @classmethod
    async def _load_from_db(cls, *, db: AsyncSession, user_id: int, ts: datetime) -> UserGrantSnapshot:
        """从 DB 全量构建用户权益快照(原始路径, 5+ 条 SQL)"""
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
        生成可审计字典(用于决策日志 context, 兼容缓存路径)

        :param snapshot: 用户权益快照
        :return:
        """
        if snapshot._cached_subscription_ids is not None:
            return {
                'subscription_ids': list(snapshot._cached_subscription_ids),
                'direct_grant_ids': list(snapshot._cached_direct_grant_ids or []),
                'entitlement_codes': sorted(snapshot.entitlement_codes),
            }
        return {
            'subscription_ids': [s.id for s in snapshot.subscriptions],
            'direct_grant_ids': [g.id for g in snapshot.direct_grants],
            'entitlement_codes': sorted(snapshot.entitlement_codes),
        }


snapshot_service: SnapshotService = SnapshotService()
