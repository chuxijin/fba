#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排名服务类"""
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import User
from backend.app.question_bank.crud.crud_check_in import check_in_dao
from backend.app.question_bank.crud.crud_daily_rank import daily_rank_dao
from backend.app.question_bank.model import PracticeRecord, UserAccount, UserPracticeStats
from backend.app.question_bank.schema.home import RankItem, RankListData, RankUserInfo, UserRankInfo
from backend.utils.timezone import timezone


class RankService:
    """排名服务类"""

    @staticmethod
    async def get_user_rank_info(*, db: AsyncSession, user_id: int) -> UserRankInfo:
        """
        获取用户排名信息（优先从预计算表读取）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        rank_record = await daily_rank_dao.get_by_user_and_date(db, user_id, yesterday)

        if rank_record:
            previous_record = await daily_rank_dao.get_by_user_and_date(
                db, user_id, yesterday - timedelta(days=1)
            )
            rank_change = None
            if previous_record:
                rank_change = previous_record.rank - rank_record.rank

            return UserRankInfo(
                beat_percentage=rank_record.beat_percentage,
                current_rank=rank_record.rank,
                total_users=rank_record.total_users,
                yesterday_rank=rank_record.rank,
                rank_change=rank_change,
            )

        return await RankService._calculate_rank_realtime(db, user_id)

    @staticmethod
    async def _calculate_rank_realtime(db: AsyncSession, user_id: int) -> UserRankInfo:
        """
        实时计算用户排名（降级方案）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        today_start = datetime.combine(today, datetime.min.time())

        stmt = (
            select(
                UserAccount.user_id.label('user_id'),
                func.count(PracticeRecord.id).label('practice_count'),
            )
            .outerjoin(
                PracticeRecord,
                (PracticeRecord.user_id == UserAccount.user_id)
                & (PracticeRecord.created_time >= yesterday_start)
                & (PracticeRecord.created_time < today_start),
            )
            .group_by(UserAccount.user_id)
            .order_by(func.count(PracticeRecord.id).desc())
        )

        result = await db.execute(stmt)
        all_ranks = result.all()

        total_users = len(all_ranks)
        current_rank = 1

        for i, row in enumerate(all_ranks, 1):
            if row.user_id == user_id:
                current_rank = i
                break

        beat_percentage = Decimal((total_users - current_rank) / total_users * 100) if total_users > 0 else Decimal(0)

        return UserRankInfo(
            beat_percentage=beat_percentage.quantize(Decimal('0.01')),
            current_rank=current_rank,
            total_users=total_users,
            yesterday_rank=None,
            rank_change=None,
        )

    @staticmethod
    async def get_rank_list(
        *, db: AsyncSession, rank_type: str, current_user_id: int, limit: int = 100
    ) -> RankListData:
        """
        获取排行榜列表

        :param db: 数据库会话
        :param rank_type: 排行榜类型（practice_count/accuracy_rate/streak_days）
        :param current_user_id: 当前用户 ID
        :param limit: 返回数量限制
        :return:
        """
        if rank_type == 'practice_count':
            return await RankService._get_practice_count_rank(db, current_user_id, limit)
        elif rank_type == 'accuracy_rate':
            return await RankService._get_accuracy_rate_rank(db, current_user_id, limit)
        elif rank_type == 'streak_days':
            return await RankService._get_streak_days_rank(db, current_user_id, limit)
        else:
            raise ValueError(f'Invalid rank_type: {rank_type}')

    @staticmethod
    async def _get_practice_count_rank(
        db: AsyncSession, current_user_id: int, limit: int
    ) -> RankListData:
        """获取刷题数量排行榜"""
        stmt = (
            select(
                UserPracticeStats.user_id.label('user_id'),
                User.nickname,
                User.avatar,
                UserPracticeStats.total_count.label('practice_count'),
            )
            .join(User, User.id == UserPracticeStats.user_id)
            .where(UserPracticeStats.total_count > 0)
            .order_by(UserPracticeStats.total_count.desc())
            .limit(limit)
        )

        result = await db.execute(stmt)
        rows = result.all()

        top_users = []
        current_user_rank = None

        for i, row in enumerate(rows, 1):
            rank_item = RankItem(
                rank=i,
                user=RankUserInfo(
                    user_id=row.user_id,
                    nickname=row.nickname or f'用户{row.user_id}',
                    avatar=row.avatar,
                ),
                value=row.practice_count,
                is_current_user=row.user_id == current_user_id,
            )

            top_users.append(rank_item)

            if row.user_id == current_user_id:
                current_user_rank = rank_item

        return RankListData(
            rank_type='practice_count',
            current_user_rank=current_user_rank,
            top_users=top_users,
        )

    @staticmethod
    async def _get_accuracy_rate_rank(
        db: AsyncSession, current_user_id: int, limit: int
    ) -> RankListData:
        """获取正确率排行榜"""
        stmt = (
            select(
                UserPracticeStats.user_id.label('user_id'),
                User.nickname,
                User.avatar,
                UserPracticeStats.total_count,
                UserPracticeStats.correct_count,
            )
            .join(User, User.id == UserPracticeStats.user_id)
            .where(UserPracticeStats.total_count >= 10)
        )

        result = await db.execute(stmt)
        rows = result.all()

        users_with_accuracy = []
        for row in rows:
            total = row.total_count or 0
            correct = row.correct_count or 0
            accuracy = Decimal((correct / total) * 100).quantize(Decimal('0.01')) if total > 0 else Decimal(0)

            users_with_accuracy.append({
                'user_id': row.user_id,
                'nickname': row.nickname,
                'avatar': row.avatar,
                'accuracy': accuracy,
            })

        users_with_accuracy.sort(key=lambda x: x['accuracy'], reverse=True)
        users_with_accuracy = users_with_accuracy[:limit]

        top_users = []
        current_user_rank = None

        for i, user_data in enumerate(users_with_accuracy, 1):
            rank_item = RankItem(
                rank=i,
                user=RankUserInfo(
                    user_id=user_data['user_id'],
                    nickname=user_data['nickname'] or f'用户{user_data["user_id"]}',
                    avatar=user_data['avatar'],
                ),
                value=user_data['accuracy'],
                is_current_user=user_data['user_id'] == current_user_id,
            )

            top_users.append(rank_item)

            if user_data['user_id'] == current_user_id:
                current_user_rank = rank_item

        return RankListData(
            rank_type='accuracy_rate',
            current_user_rank=current_user_rank,
            top_users=top_users,
        )

    @staticmethod
    async def _get_streak_days_rank(
        db: AsyncSession, current_user_id: int, limit: int
    ) -> RankListData:
        """获取坚持天数（连续打卡）排行榜"""
        all_users_stmt = (
            select(UserAccount.user_id.label('user_id'), User.nickname, User.avatar)
            .join(User, User.id == UserAccount.user_id)
        )
        users_result = await db.execute(all_users_stmt)
        all_users = users_result.all()

        users_with_streak = []

        for user in all_users:
            streak = await check_in_dao.get_streak(db, user.user_id)
            if streak > 0:
                users_with_streak.append({
                    'user_id': user.user_id,
                    'nickname': user.nickname,
                    'avatar': user.avatar,
                    'streak': streak,
                })

        users_with_streak.sort(key=lambda x: x['streak'], reverse=True)
        users_with_streak = users_with_streak[:limit]

        top_users = []
        current_user_rank = None

        for i, user_data in enumerate(users_with_streak, 1):
            rank_item = RankItem(
                rank=i,
                user=RankUserInfo(
                    user_id=user_data['user_id'],
                    nickname=user_data['nickname'] or f'用户{user_data["user_id"]}',
                    avatar=user_data['avatar'],
                ),
                value=user_data['streak'],
                is_current_user=user_data['user_id'] == current_user_id,
            )

            top_users.append(rank_item)

            if user_data['user_id'] == current_user_id:
                current_user_rank = rank_item

        return RankListData(
            rank_type='streak_days',
            current_user_rank=current_user_rank,
            top_users=top_users,
        )


rank_service: RankService = RankService()
