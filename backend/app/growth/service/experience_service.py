#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.growth.constants import GrowthEventOp, next_tier_exp_required, resolve_grade
from backend.app.growth.crud.crud_experience_rule import experience_rule_dao
from backend.app.growth.crud.crud_growth_account import growth_account_dao
from backend.app.growth.crud.crud_growth_event import growth_event_dao
from backend.app.growth.model.account import GrowthAccount
from backend.app.growth.model.event import GrowthEvent
from backend.common.exception import errors


class ExperienceService:
    """经验值服务（用户维度，跨等级共享）"""

    @staticmethod
    async def _ensure_account(
        db: AsyncSession,
        *,
        user_id: int,
        for_update: bool = False,
    ) -> GrowthAccount:
        """
        确保成长账户存在（不存在时自动创建）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param for_update: 是否加行锁
        :return:
        """
        account = await growth_account_dao.get_by_user(
            db, user_id=user_id, for_update=for_update,
        )
        if account is not None:
            return account

        account = GrowthAccount(
            user_id=user_id,
            total_exp=0,
            available_exp=0,
            current_grade=0,
        )
        db.add(account)
        await db.flush()
        return account

    @classmethod
    async def add_experience(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        exp_delta: int,
        source: str,
        source_key: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        增加经验值

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param exp_delta: 经验增量
        :param source: 来源
        :param source_key: 来源幂等键
        :param reason: 原因
        :return:
        """
        if exp_delta <= 0:
            raise errors.RequestError(msg='经验增量必须大于 0')

        idempotency_key = f'exp_add:{user_id}:{source}:{source_key}'
        existing = await growth_event_dao.get_by_idempotency_key(db, idempotency_key)
        if existing:
            account = await cls._ensure_account(db, user_id=user_id)
            return cls._progress_payload(account)

        account = await cls._ensure_account(
            db, user_id=user_id, for_update=True
        )
        new_total = account.total_exp + exp_delta
        new_available = account.available_exp + exp_delta

        account.total_exp = new_total
        account.available_exp = new_available

        new_grade = resolve_grade(new_total)
        if new_grade > account.current_grade:
            account.current_grade = new_grade

        event = GrowthEvent(
            user_id=user_id,
            operation=GrowthEventOp.CREDIT,
            exp_delta=exp_delta,
            total_exp_after=new_total,
            available_exp_after=new_available,
            grade_after=account.current_grade,
            source=source,
            source_key=source_key,
            idempotency_key=idempotency_key,
            reason=reason,
        )
        db.add(event)
        return cls._progress_payload(account)

    @classmethod
    async def consume_experience(
        cls,
        db: AsyncSession,
        *,
        user_id: int,
        exp_delta: int,
        source: str,
        source_key: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        消耗经验值

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param exp_delta: 消耗量
        :param source: 来源
        :param source_key: 来源幂等键
        :param reason: 原因
        :return:
        """
        if exp_delta <= 0:
            raise errors.RequestError(msg='消耗量必须大于 0')

        idempotency_key = f'exp_consume:{user_id}:{source}:{source_key}'
        existing = await growth_event_dao.get_by_idempotency_key(db, idempotency_key)
        if existing:
            account = await cls._ensure_account(db, user_id=user_id)
            return cls._progress_payload(account)

        account = await cls._ensure_account(
            db, user_id=user_id, for_update=True
        )
        if account.available_exp < exp_delta:
            raise errors.RequestError(msg='可用经验不足')

        new_available = account.available_exp - exp_delta
        account.available_exp = new_available

        event = GrowthEvent(
            user_id=user_id,
            operation=GrowthEventOp.CONSUME,
            exp_delta=exp_delta,
            total_exp_after=account.total_exp,
            available_exp_after=new_available,
            grade_after=account.current_grade,
            source=source,
            source_key=source_key,
            idempotency_key=idempotency_key,
            reason=reason,
        )
        db.add(event)
        return cls._progress_payload(account)

    @staticmethod
    async def get_user_progress(
        db: AsyncSession, *, user_id: int
    ) -> dict[str, Any] | None:
        """
        查询用户成长进度

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        account = await growth_account_dao.get_by_user(db, user_id=user_id)
        if account is None:
            return None
        return ExperienceService._progress_payload(account)

    @staticmethod
    def _progress_payload(account: GrowthAccount) -> dict[str, Any]:
        """
        构建进度返回数据

        :param account: 成长账户
        :return:
        """
        return {
            'total_exp': account.total_exp,
            'available_exp': account.available_exp,
            'current_grade': account.current_grade,
            'next_exp_required': next_tier_exp_required(account.current_grade),
        }


experience_service: ExperienceService = ExperienceService()
