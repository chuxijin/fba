#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.quest.crud.crud_quest import quest_claim_dao, quest_dao
from backend.app.quest.schema.quest import ReviewClaimParam, ReviewClaimResult, RevokeClaimParam, RevokeClaimResult
from backend.app.quest.service.reward_service import reward_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


class ReviewService:
    """悬赏任务审核服务类"""

    @staticmethod
    async def review(
        *,
        db: AsyncSession,
        claim_id: int,
        reviewer_id: int,
        obj: ReviewClaimParam,
    ) -> ReviewClaimResult:
        """
        审核领取记录

        :param db: 数据库会话
        :param claim_id: 领取记录 ID
        :param reviewer_id: 审核人用户 ID
        :param obj: 审核参数
        :return:
        """
        claim = await quest_claim_dao.select_model(db, claim_id)
        if not claim:
            raise errors.NotFoundError(msg='领取记录不存在')

        if claim.claim_status != 1:
            raise errors.RequestError(msg='该记录当前不可审核')

        quest = await quest_dao.select_model(db, claim.quest_id)
        if not quest:
            raise errors.NotFoundError(msg='关联任务不存在')

        now = timezone.now()
        if obj.decision == 'reject':
            await quest_claim_dao.update_model(
                db,
                claim_id,
                {
                    'claim_status': 3,
                    'review_remark': obj.remark,
                    'reviewed_by': reviewer_id,
                    'review_time': now,
                },
                commit=False,
            )
            await db.commit()
            return ReviewClaimResult(
                claim_id=claim_id,
                claim_status=3,
                reward_granted=False,
                message='已拒绝',
            )

        await quest_claim_dao.update_model(
            db,
            claim_id,
            {
                'claim_status': 2,
                'review_remark': obj.remark,
                'reviewed_by': reviewer_id,
                'review_time': now,
            },
            commit=False,
        )
        await db.flush()
        updated_claim = await quest_claim_dao.select_model(db, claim_id)

        granted = await reward_service.grant_for_claim(db=db, claim=updated_claim, quest=quest)
        await db.commit()

        final_claim = await quest_claim_dao.select_model(db, claim_id)
        return ReviewClaimResult(
            claim_id=claim_id,
            claim_status=final_claim.claim_status,
            reward_granted=granted,
            message='审核通过并已发奖' if granted else '审核通过，但奖励发放失败，请稍后重试',
        )

    @staticmethod
    async def revoke(
        *,
        db: AsyncSession,
        claim_id: int,
        reviewer_id: int,
        obj: RevokeClaimParam,
    ) -> RevokeClaimResult:
        """
        撤销审核(硬撤销, 同时回收已发放的奖励)

        :param db: 数据库会话
        :param claim_id: 领取记录 ID
        :param reviewer_id: 操作人用户 ID
        :param obj: 撤销参数
        :return:
        """
        claim = await quest_claim_dao.select_model(db, claim_id)
        if not claim:
            raise errors.NotFoundError(msg='领取记录不存在')

        if claim.claim_status not in (2, 4):
            raise errors.RequestError(msg='只有已通过/已发奖的记录可以撤销')

        quest = await quest_dao.select_model(db, claim.quest_id)
        if not quest:
            raise errors.NotFoundError(msg='关联任务不存在')

        revoked = await reward_service.revoke_for_claim(db=db, claim=claim, quest=quest)

        if not revoked:
            raise errors.RequestError(msg='奖励撤销失败：可能用户可用经验不足或该奖励类型暂不支持自动撤销')

        await quest_claim_dao.update_model(
            db,
            claim_id,
            {
                'review_remark': f'[撤销] {obj.remark or ""}'.strip(),
                'reviewed_by': reviewer_id,
                'review_time': timezone.now(),
            },
            commit=False,
        )
        await db.commit()

        final_claim = await quest_claim_dao.select_model(db, claim_id)
        return RevokeClaimResult(
            claim_id=claim_id,
            claim_status=final_claim.claim_status,
            reward_revoked=True,
            message='奖励已撤销',
        )


review_service: ReviewService = ReviewService()
