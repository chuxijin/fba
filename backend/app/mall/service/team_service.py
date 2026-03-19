#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
import secrets
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mall.crud.crud_group_buy import group_buy_activity_dao, group_buy_ladder_price_dao
from backend.app.mall.crud.crud_group_buy_team import group_buy_member_dao, group_buy_team_dao
from backend.app.mall.model.group_buy_team import GroupBuyMember, GroupBuyTeam
from backend.app.mall.schema.group_buy_team import (
    CreateGroupBuyTeamParam,
    GroupBuyTeamProgress,
    JoinGroupBuyTeamParam,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone

log = logging.getLogger(__name__)


class TeamService:
    """拼团团队服务类"""

    @staticmethod
    def _generate_share_code() -> str:
        """生成分享码"""
        return secrets.token_urlsafe(16)

    @staticmethod
    async def create_team(*, db: AsyncSession, obj: CreateGroupBuyTeamParam, user_id: int) -> GroupBuyTeam:
        """
        创建拼团团队（发起拼团）

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 用户 ID
        :return:
        """
        activity = await group_buy_activity_dao.get(db, obj.activity_id)
        if not activity:
            raise errors.NotFoundError(msg='拼团活动不存在')

        if activity.status != 'active':
            raise errors.ForbiddenError(msg='活动未开始或已结束')

        now = timezone.now()
        if now < activity.start_time or now > activity.end_time:
            raise errors.ForbiddenError(msg='活动未在有效期内')

        if activity.stock <= 0:
            raise errors.ForbiddenError(msg='活动库存不足')

        if obj.required_people < activity.min_people or obj.required_people > activity.max_people:
            raise errors.ForbiddenError(msg='成团人数超出活动范围')

        ladder_price = await group_buy_ladder_price_dao.get_by_people_count(db, obj.activity_id, obj.required_people)
        if not ladder_price:
            raise errors.NotFoundError(msg='未找到对应的拼团价格')

        already_joined = await group_buy_member_dao.check_user_in_activity(db, user_id, obj.activity_id)
        if already_joined:
            raise errors.ForbiddenError(msg='您已参与该活动的拼团')

        expire_time = now + timedelta(hours=activity.time_limit)
        share_code = TeamService._generate_share_code()

        team_data = {
            'activity_id': obj.activity_id,
            'leader_user_id': user_id,
            'required_people': obj.required_people,
            'current_people': 1,
            'team_price': ladder_price.price,
            'status': 'pending',
            'start_time': now,
            'expire_time': expire_time,
            'share_code': share_code,
        }
        team = await group_buy_team_dao.create_model(db, team_data)

        member_data = {
            'team_id': team.id,
            'activity_id': obj.activity_id,
            'user_id': user_id,
            'is_leader': True,
            'paid_amount': ladder_price.price,
            'join_time': now,
        }
        await group_buy_member_dao.create_model(db, member_data)

        log.info(f'用户 {user_id} 发起拼团，团队 ID: {team.id}')
        return team

    @staticmethod
    async def join_team(*, db: AsyncSession, obj: JoinGroupBuyTeamParam, user_id: int) -> GroupBuyMember:
        """
        参与拼团

        :param db: 数据库会话
        :param obj: 参与参数
        :param user_id: 用户 ID
        :return:
        """
        team = await group_buy_team_dao.get(db, obj.team_id)
        if not team:
            raise errors.NotFoundError(msg='拼团团队不存在')

        if team.status != 'pending':
            raise errors.ForbiddenError(msg='该团队已结束或已取消')

        now = timezone.now()
        if now > team.expire_time:
            raise errors.ForbiddenError(msg='该团队已过期')

        if team.current_people >= team.required_people:
            raise errors.ForbiddenError(msg='该团队已满员')

        already_in_team = await group_buy_member_dao.get_by_user_and_team(db, user_id, obj.team_id)
        if already_in_team:
            raise errors.ForbiddenError(msg='您已在该团队中')

        already_joined = await group_buy_member_dao.check_user_in_activity(db, user_id, team.activity_id)
        if already_joined:
            raise errors.ForbiddenError(msg='您已参与该活动的其他拼团')

        member_data = {
            'team_id': obj.team_id,
            'activity_id': team.activity_id,
            'user_id': user_id,
            'is_leader': False,
            'paid_amount': team.team_price,
            'join_time': now,
            'inviter_user_id': obj.inviter_user_id,
        }
        member = await group_buy_member_dao.create_model(db, member_data)

        await group_buy_team_dao.increment_people(db, obj.team_id)

        team = await group_buy_team_dao.get(db, obj.team_id)
        if team and team.current_people >= team.required_people:
            await TeamService._complete_team(db, team)

        log.info(f'用户 {user_id} 参与拼团，团队 ID: {obj.team_id}')
        return member

    @staticmethod
    async def _complete_team(db: AsyncSession, team: GroupBuyTeam) -> None:
        """
        完成拼团

        :param db: 数据库会话
        :param team: 团队对象
        :return:
        """
        now = timezone.now()
        await group_buy_team_dao.update_model(
            db,
            team.id,
            {
                'status': 'success',
                'success_time': now,
            },
        )
        log.info(f'拼团成功，团队 ID: {team.id}')

    @staticmethod
    async def get_team(*, db: AsyncSession, team_id: int, with_members: bool = False) -> GroupBuyTeam:
        """
        获取团队详情

        :param db: 数据库会话
        :param team_id: 团队 ID
        :param with_members: 是否包含成员列表
        :return:
        """
        if with_members:
            team = await group_buy_team_dao.get_with_members(db, team_id)
        else:
            team = await group_buy_team_dao.get(db, team_id)
        if not team:
            raise errors.NotFoundError(msg='拼团团队不存在')
        return team

    @staticmethod
    async def get_team_list(*, db: AsyncSession, activity_id: int, status: str | None = None) -> list[GroupBuyTeam]:
        """
        获取团队列表

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :param status: 团队状态
        :return:
        """
        return await group_buy_team_dao.get_by_activity(db, activity_id, status)

    @staticmethod
    async def get_pending_teams(*, db: AsyncSession, activity_id: int) -> list[GroupBuyTeam]:
        """
        获取进行中的团队列表

        :param db: 数据库会话
        :param activity_id: 活动 ID
        :return:
        """
        return await group_buy_team_dao.get_pending_teams(db, activity_id)

    @staticmethod
    async def get_user_teams(*, db: AsyncSession, user_id: int) -> list[GroupBuyTeam]:
        """
        获取用户参与的团队列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await group_buy_team_dao.get_by_user(db, user_id)

    @staticmethod
    async def get_team_progress(*, db: AsyncSession, team_id: int) -> GroupBuyTeamProgress:
        """
        获取拼团进度

        :param db: 数据库会话
        :param team_id: 团队 ID
        :return:
        """
        team = await group_buy_team_dao.get(db, team_id)
        if not team:
            raise errors.NotFoundError(msg='拼团团队不存在')

        now = timezone.now()
        return GroupBuyTeamProgress(
            team_id=team.id,
            required_people=team.required_people,
            current_people=team.current_people,
            remaining_people=team.required_people - team.current_people,
            status=team.status,
            expire_time=team.expire_time,
            is_expired=now > team.expire_time,
        )

    @staticmethod
    async def cancel_team(*, db: AsyncSession, team_id: int, user_id: int) -> int:
        """
        取消拼团（仅团长可操作）

        :param db: 数据库会话
        :param team_id: 团队 ID
        :param user_id: 用户 ID
        :return:
        """
        team = await group_buy_team_dao.get(db, team_id)
        if not team:
            raise errors.NotFoundError(msg='拼团团队不存在')

        if team.leader_user_id != user_id:
            raise errors.ForbiddenError(msg='只有团长可以取消拼团')

        if team.status != 'pending':
            raise errors.ForbiddenError(msg='该团队已结束或已取消')

        count = await group_buy_team_dao.update_model(db, team_id, {'status': 'cancelled'})
        log.info(f'用户 {user_id} 取消拼团，团队 ID: {team_id}')
        return count

    @staticmethod
    async def process_expired_teams(*, db: AsyncSession) -> int:
        """
        处理过期团队（定时任务调用）

        :param db: 数据库会话
        :return:
        """
        expired_teams = await group_buy_team_dao.get_expired_teams(db)
        count = 0

        for team in expired_teams:
            activity = await group_buy_activity_dao.get(db, team.activity_id)
            if not activity:
                continue

            if activity.enable_mock_team and team.current_people >= (team.required_people - (activity.mock_team_threshold or 1)):
                await group_buy_team_dao.update_model(
                    db,
                    team.id,
                    {
                        'status': 'success',
                        'success_time': timezone.now(),
                        'is_mock': True,
                        'current_people': team.required_people,
                    },
                )
                log.info(f'模拟成团，团队 ID: {team.id}')
            else:
                await group_buy_team_dao.update_model(db, team.id, {'status': 'failed'})
                log.info(f'拼团失败，团队 ID: {team.id}')

            count += 1

        return count


team_service = TeamService()
