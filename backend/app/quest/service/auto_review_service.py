#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.actcode.crud.crud_actcode import actcode_dao
from backend.app.quest.crud.crud_quest import quest_claim_dao
from backend.app.quest.model import Quest, QuestClaim
from backend.app.quest.service.reward_service import reward_service
from backend.common.exception import errors
from backend.utils.timezone import timezone

REVIEW_STRATEGY_MANUAL = 'manual'
REVIEW_STRATEGY_AUTO_PASS = 'auto_pass'
REVIEW_STRATEGY_ORDER_PHONE_REQUIRED = 'order_phone_required'

# 自动审核策略命名约定:
# 1. 使用 snake_case, 只描述“审核条件”, 不描述奖励发放方式
# 2. 新增策略时优先新增独立的 _validate_xxx 函数, 再在 handle_after_submit 中分发
# 3. 如果策略数量继续增长, 这里可以升级为 registry: dict[str, Callable], 避免堆叠 if/elif
# 示例:
# - order_phone_required: 校验 actcode 订单号存在且手机号格式正确后自动通过
# - chaoji_order_verify: 调超级考研订单接口校验后自动通过
# - external_order_verify: 调通用第三方订单接口校验后自动通过
_PHONE_PATTERN = re.compile(r'^1[3-9]\d{9}$')


class AutoReviewService:
    """悬赏任务自动审核服务类"""

    @staticmethod
    def _validate_submission_schema(quest: Quest, claim: QuestClaim) -> None:
        """
        校验结构化提交字段

        :param quest: 任务实体
        :param claim: 领取记录
        :return:
        """
        schema = quest.submission_schema or {}
        if not isinstance(schema, dict):
            raise errors.RequestError(msg='任务提交字段配置错误')

        submission_data = claim.submission_data or {}
        if not isinstance(submission_data, dict):
            raise errors.RequestError(msg='请按要求填写任务提交内容')

        for field_name, field_config in schema.items():
            if not isinstance(field_config, dict):
                continue
            if not field_config.get('required'):
                continue
            value = submission_data.get(field_name)
            if value is None or str(value).strip() == '':
                label = field_config.get('label') or field_name
                raise errors.RequestError(msg=f'请填写{label}')

    @staticmethod
    async def _ensure_order_no_available(db: AsyncSession, claim: QuestClaim, order_no: str) -> None:
        """
        校验订单号存在且未在同任务重复使用

        :param db: 数据库会话
        :param claim: 领取记录
        :param order_no: 订单号
        :return:
        """
        actcode = await actcode_dao.get_by_code(db, order_no)
        if not actcode:
            raise errors.RequestError(msg='订单号不存在，请核对后重新填写')

        stmt = (
            select(QuestClaim.id)
            .where(
                QuestClaim.quest_id == claim.quest_id,
                QuestClaim.id != claim.id,
                QuestClaim.claim_status.in_((1, 2, 4)),
                QuestClaim.submission_data['order_no'].as_string() == order_no,
            )
            .limit(1)
        )
        existed = (await db.execute(stmt)).scalar_one_or_none()
        if existed:
            raise errors.ConflictError(msg='该订单号已提交过当前任务')

    @staticmethod
    async def _validate_order_phone_required(db: AsyncSession, claim: QuestClaim) -> None:
        """
        校验订单号和手机号

        :param db: 数据库会话
        :param claim: 领取记录
        :return:
        """
        submission_data = claim.submission_data or {}
        order_no = str(submission_data.get('order_no') or '').strip()
        phone = str(submission_data.get('phone') or '').strip()

        if not order_no:
            raise errors.RequestError(msg='请填写订单号')
        if not phone:
            raise errors.RequestError(msg='请填写开通手机号')
        if not _PHONE_PATTERN.match(phone):
            raise errors.RequestError(msg='开通手机号格式不正确')
        await AutoReviewService._ensure_order_no_available(db, claim, order_no)

    @staticmethod
    async def handle_after_submit(
        *,
        db: AsyncSession,
        quest: Quest,
        claim: QuestClaim,
    ) -> bool | None:
        """
        提交后执行自动审核

        :param db: 数据库会话
        :param quest: 任务实体
        :param claim: 领取记录
        :return:
        """
        strategy = (quest.review_strategy or REVIEW_STRATEGY_MANUAL).strip()
        AutoReviewService._validate_submission_schema(quest, claim)

        # manual 表示只做提交字段校验, 后续仍进入人工审核队列。
        if strategy == REVIEW_STRATEGY_MANUAL:
            return None

        # 自动审核策略只负责“能不能通过”, 奖励发放统一交给 reward_service。
        # 新增策略时, 不要在这里直接写第三方开通逻辑, 第三方开通应放到 reward fulfiller。
        if strategy == REVIEW_STRATEGY_ORDER_PHONE_REQUIRED:
            await AutoReviewService._validate_order_phone_required(db, claim)
        elif strategy != REVIEW_STRATEGY_AUTO_PASS:
            raise errors.RequestError(msg=f'未知自动审核策略: {strategy}')

        now = timezone.now()
        await quest_claim_dao.update_model(
            db,
            claim.id,
            {
                'claim_status': 2,
                'review_remark': '系统自动审核通过',
                'review_time': now,
            },
            commit=False,
        )
        await db.flush()

        approved_claim = await quest_claim_dao.select_model(db, claim.id)
        return await reward_service.grant_for_claim(db=db, claim=approved_claim, quest=quest)


auto_review_service: AutoReviewService = AutoReviewService()
