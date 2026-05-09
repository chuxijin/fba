#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.quest.crud.crud_quest import quest_claim_dao, quest_dao, quest_reward_log_dao
from backend.app.quest.model import Quest, QuestClaim, QuestRewardLog
from backend.common.log import log
from backend.common.reward import dispatch_reward, revoke_reward
from backend.utils.timezone import timezone


class RewardService:
    """悬赏任务奖励发放服务类"""

    SOURCE: str = 'quest'

    @staticmethod
    def _build_source_key(claim: QuestClaim) -> str:
        """
        构建奖励发放幂等键

        :param claim: 领取记录
        :return:
        """
        return f'quest:{claim.quest_id}:claim:{claim.id}'

    @staticmethod
    def _build_reward_data(quest: Quest, claim: QuestClaim, source_key: str) -> dict:
        """
        构建奖励发放参数

        :param quest: 任务
        :param claim: 领取记录
        :param source_key: 幂等键
        :return:
        """
        payload = dict(quest.reward_data or {})
        payload['source'] = RewardService.SOURCE
        payload['source_key'] = source_key
        payload.setdefault(
            'source_detail',
            f'quest_id={quest.id},claim_id={claim.id},user_id={claim.user_id}',
        )
        payload.setdefault('remark', f'悬赏任务奖励：{quest.name}')
        return payload

    @staticmethod
    async def grant_for_claim(
        *,
        db: AsyncSession,
        claim: QuestClaim,
        quest: Quest,
    ) -> bool:
        """
        为审核通过的领取记录发放奖励

        :param db: 数据库会话
        :param claim: 领取记录
        :param quest: 任务
        :return:
        """
        existing = await quest_reward_log_dao.get_by_claim(db, claim.id)
        if existing and existing.grant_status == 1:
            log.info(f'奖励已发放过，跳过: claim_id={claim.id}')
            await quest_claim_dao.update_model(
                db,
                claim.id,
                {'reward_status': 1, 'claim_status': 4},
                commit=False,
            )
            return True

        source_key = RewardService._build_source_key(claim)
        reward_data = RewardService._build_reward_data(quest, claim, source_key)

        if existing is None:
            log_record = QuestRewardLog(
                claim_id=claim.id,
                quest_id=quest.id,
                user_id=claim.user_id,
                reward_type=quest.reward_type,
                reward_data=reward_data,
                source_key=source_key,
                grant_status=0,
            )
            db.add(log_record)
            await db.flush()
        else:
            log_record = existing

        error_detail = ''
        try:
            success = await dispatch_reward(
                db=db,
                user_id=claim.user_id,
                reward_type=quest.reward_type,
                reward_data=reward_data,
            )
        except Exception as exc:
            success = False
            error_detail = str(exc)
            log.warning(
                f'悬赏任务奖励发放异常: claim_id={claim.id}, user_id={claim.user_id}, error={error_detail}'
            )

        if success:
            await quest_reward_log_dao.update_model(
                db,
                log_record.id,
                {'grant_status': 1, 'granted_at': timezone.now(), 'error_message': None},
                commit=False,
            )
            await quest_claim_dao.update_model(
                db,
                claim.id,
                {'reward_status': 1, 'claim_status': 4, 'granted_at': timezone.now()},
                commit=False,
            )
            log.info(f'悬赏任务奖励发放成功: claim_id={claim.id}, user_id={claim.user_id}')
        else:
            error_msg = error_detail or '奖励分发返回失败'
            await quest_reward_log_dao.update_model(
                db,
                log_record.id,
                {'grant_status': 2, 'error_message': error_msg},
                commit=False,
            )
            await quest_claim_dao.update_model(
                db,
                claim.id,
                {'reward_status': 2},
                commit=False,
            )
            log.warning(f'悬赏任务奖励发放失败: claim_id={claim.id}, user_id={claim.user_id}, reason={error_msg}')

        return success

    @staticmethod
    async def retry_grant(*, db: AsyncSession, claim_id: int) -> bool:
        """
        重试发放奖励（用于失败重发）

        :param db: 数据库会话
        :param claim_id: 领取记录 ID
        :return:
        """
        claim = await quest_claim_dao.select_model(db, claim_id)
        if not claim:
            return False

        quest = await quest_dao.select_model(db, claim.quest_id)
        if not quest:
            return False

        if claim.claim_status not in (2, 4):
            return False

        success = await RewardService.grant_for_claim(db=db, claim=claim, quest=quest)
        await db.commit()
        return success

    @staticmethod
    async def revoke_for_claim(
        *,
        db: AsyncSession,
        claim: QuestClaim,
        quest: Quest,
    ) -> bool:
        """
        撤销已发放的奖励

        :param db: 数据库会话
        :param claim: 领取记录
        :param quest: 任务
        :return:
        """
        log_record = await quest_reward_log_dao.get_by_claim(db, claim.id)
        if not log_record or log_record.grant_status != 1:
            log.warning(f'撤销跳过: claim_id={claim.id} 没有成功的发放流水')
            return False

        success = await revoke_reward(
            db=db,
            user_id=claim.user_id,
            reward_type=log_record.reward_type,
            reward_data=log_record.reward_data or {},
        )

        if success:
            await quest_reward_log_dao.update_model(
                db,
                log_record.id,
                {'grant_status': 3, 'error_message': '管理员撤销'},
                commit=False,
            )
            await quest_claim_dao.update_model(
                db,
                claim.id,
                {'claim_status': 6, 'reward_status': 3},
                commit=False,
            )
            log.info(f'悬赏任务奖励撤销成功: claim_id={claim.id}, user_id={claim.user_id}')
        else:
            log.warning(
                f'悬赏任务奖励撤销失败: claim_id={claim.id}, user_id={claim.user_id}, '
                f'可能原因为可用经验不足或奖励类型不支持撤销'
            )

        return success


reward_service: RewardService = RewardService()
