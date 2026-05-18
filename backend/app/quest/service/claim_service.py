#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.quest.crud.crud_quest import quest_claim_dao, quest_dao
from backend.app.quest.model import Quest, QuestClaim
from backend.app.quest.schema.quest import GetClaimDetail, SubmitClaimParam
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class ClaimService:
    """悬赏任务领取/提交服务类"""

    @staticmethod
    def _ensure_quest_claimable(quest: Quest) -> None:
        """
        校验任务是否可被领取

        :param quest: 任务实体
        :return:
        """
        if quest.status == 0:
            raise errors.RequestError(msg='任务尚未发布')
        if quest.status == 2:
            raise errors.RequestError(msg='任务已暂停')
        if quest.status == 3:
            raise errors.RequestError(msg='任务已结束')

        now = timezone.now()
        if quest.start_time and now < quest.start_time:
            raise errors.RequestError(msg='任务尚未开始')
        if quest.end_time and now > quest.end_time:
            raise errors.RequestError(msg='任务已过期')

    @staticmethod
    async def claim_quest(*, db: AsyncSession, quest_id: int, user_id: int) -> GetClaimDetail:
        """
        领取任务

        :param db: 数据库会话（必须为 transaction 模式）
        :param quest_id: 任务 ID
        :param user_id: 当前用户 ID
        :return:
        """
        quest = await quest_dao.lock_for_claim(db, quest_id)
        if not quest:
            raise errors.NotFoundError(msg='任务不存在')

        ClaimService._ensure_quest_claimable(quest)

        if quest.total_quota and quest.claimed_count >= quest.total_quota:
            raise errors.ConflictError(msg='名额已满')

        user_claim_count = await quest_claim_dao.count_active_by_user(db, quest_id, user_id)
        if quest.max_claims_per_user > 0 and user_claim_count >= quest.max_claims_per_user:
            raise errors.ConflictError(msg='已达个人领取上限')

        now = timezone.now()
        expire_time = None
        if quest.claim_expire_seconds > 0:
            expire_time = now + timedelta(seconds=quest.claim_expire_seconds)

        claim = QuestClaim(
            quest_id=quest_id,
            user_id=user_id,
            claim_status=0,
            claim_time=now,
            expire_time=expire_time,
        )
        db.add(claim)
        await db.flush()

        await quest_dao.increment_claimed_count(db, quest_id)
        await db.flush()
        await db.refresh(claim)
        return GetClaimDetail.model_validate(claim)

    @staticmethod
    async def submit_claim(
        *, db: AsyncSession, claim_id: int, user_id: int, obj: SubmitClaimParam
    ) -> GetClaimDetail:
        """
        提交任务内容

        :param db: 数据库会话
        :param claim_id: 领取记录 ID
        :param user_id: 当前用户 ID
        :param obj: 提交内容
        :return:
        """
        claim = await quest_claim_dao.select_model(db, claim_id)
        if not claim:
            raise errors.NotFoundError(msg='领取记录不存在')

        if claim.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作他人的领取记录')

        if claim.claim_status not in (0, 3):
            raise errors.RequestError(msg='当前状态不允许提交')

        if claim.expire_time and timezone.now() > claim.expire_time and claim.claim_status == 0:
            raise errors.RequestError(msg='领取已超时，请重新领取')

        quest = await quest_dao.select_model(db, claim.quest_id)
        if not quest:
            raise errors.NotFoundError(msg='关联任务不存在')

        if quest.submission_required:
            if quest.require_link and not obj.submission_links:
                raise errors.RequestError(msg='该任务必须提交链接')
            if quest.require_image and not obj.submission_images:
                raise errors.RequestError(msg='该任务必须提交图片')
            if quest.require_note and not obj.submission_note:
                raise errors.RequestError(msg='该任务必须填写文字说明')
            # 兼容：如果都配置成 false，但 submission_required=True，那么至少提交任意一种
            if not (quest.require_link or quest.require_image or quest.require_note):
                if not (obj.submission_links or obj.submission_images or obj.submission_note):
                    raise errors.RequestError(msg='请填写任务提交内容')

        update_data: dict[str, Any] = {
            'submission_links': obj.submission_links,
            'submission_images': obj.submission_images,
            'submission_note': obj.submission_note,
            'submit_time': timezone.now(),
            'claim_status': 1,
        }
        await quest_claim_dao.update_model(db, claim_id, update_data, commit=False)

        # 不需要审核时，提交即触发发奖（避免循环依赖，本地导入）
        if not quest.review_required:
            from backend.app.quest.service.reward_service import reward_service

            await db.flush()
            updated_claim = await quest_claim_dao.select_model(db, claim_id)
            await reward_service.grant_for_claim(db=db, claim=updated_claim, quest=quest)
            await db.commit()
            updated_claim = await quest_claim_dao.select_model(db, claim_id)
            return GetClaimDetail.model_validate(updated_claim)

        await db.commit()
        updated_claim = await quest_claim_dao.select_model(db, claim_id)
        return GetClaimDetail.model_validate(updated_claim)

    @staticmethod
    async def abandon_claim(*, db: AsyncSession, claim_id: int, user_id: int) -> int:
        """
        放弃领取

        :param db: 数据库会话
        :param claim_id: 领取记录 ID
        :param user_id: 当前用户 ID
        :return:
        """
        claim = await quest_claim_dao.select_model(db, claim_id)
        if not claim:
            raise errors.NotFoundError(msg='领取记录不存在')
        if claim.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作他人的领取记录')
        if claim.claim_status not in (0,):
            raise errors.RequestError(msg='当前状态不允许放弃')

        return await quest_claim_dao.update_model(db, claim_id, {'claim_status': 5})

    @staticmethod
    async def get_my_claims(
        *,
        db: AsyncSession,
        user_id: int,
        claim_status: int | None = None,
    ) -> dict[str, Any]:
        """
        获取我的领取列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param claim_status: 状态过滤
        :return:
        """
        stmt = await quest_claim_dao.get_select(user_id=user_id, claim_status=claim_status)
        return await paging_data(db, stmt)

    @staticmethod
    async def get_claims_for_admin(
        *,
        db: AsyncSession,
        quest_id: int | None = None,
        user_id: int | None = None,
        claim_status: int | None = None,
    ) -> dict[str, Any]:
        """
        管理端获取领取列表

        :param db: 数据库会话
        :param quest_id: 任务 ID
        :param user_id: 用户 ID
        :param claim_status: 状态
        :return:
        """
        stmt = await quest_claim_dao.get_select(
            quest_id=quest_id, user_id=user_id, claim_status=claim_status
        )
        return await paging_data(db, stmt)


claim_service: ClaimService = ClaimService()
