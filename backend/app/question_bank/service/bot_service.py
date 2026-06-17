#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""排行榜机器人模拟服务"""

import logging
import random

from datetime import timedelta

import httpx

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.model import User
from backend.app.admin.model.m2m import user_role
from backend.app.question_bank.model import UserAccount, UserPracticeStats
from backend.app.question_bank.model.statistics import UserCheckIn
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)

# 机器人角色名称（需提前在 sys_role 中创建）
BOT_ROLE_NAME = 'bot'

# 外部 API 配置
AVATAR_API_URL = 'https://v2.xxapi.cn/api/head'
NICKNAME_API_URL = 'https://cn.apihz.cn/api/zici/xingming.php'
NICKNAME_API_ID = '10016332'
NICKNAME_API_KEY = 'f7a0227f2527d8b98623d9bdcbc3f66c'

# 本地 fallback 昵称池
BOT_NICKNAMES_FALLBACK = [
    '努力上岸',
    '每天进步一点',
    '冲鸭同学',
    '学无止境',
    '岸上见',
    '追梦人',
    '一定会上岸',
    '加油备考',
    '坚持就是胜利',
    '奋斗的鱼',
    '逢考必过',
    '努力变优秀',
    '静待花开',
    '全力以赴',
    '不负韶华',
    '默默努力',
    '暗暗加油',
    '悄悄拔尖',
    '低调学习',
    '闷声上岸',
]

# 头像池（DiceBear Adventurer 风格）
AVATAR_STYLES = ['adventurer', 'avataaars', 'bottts', 'fun-emoji', 'lorelei', 'micah', 'miniavs', 'personas']

# 机器人性格类型及参数
# per_round: 每轮（2小时）的刷题数范围
# active_prob: 每轮活跃概率（每天 12 轮，学霸大概 12*0.6=7 轮活跃）
# total_cap: 累计总题数上限，到达后降低活跃度
BOT_PERSONALITIES = {
    'hardcore': {'weight': 10, 'active_prob': 0.60, 'per_round_min': 8, 'per_round_max': 20, 'total_cap': 15000},
    'diligent': {'weight': 25, 'active_prob': 0.40, 'per_round_min': 4, 'per_round_max': 10, 'total_cap': 8000},
    'normal': {'weight': 40, 'active_prob': 0.20, 'per_round_min': 2, 'per_round_max': 6, 'total_cap': 3000},
    'casual': {'weight': 25, 'active_prob': 0.08, 'per_round_min': 1, 'per_round_max': 4, 'total_cap': 1000},
}


def _pick_personality() -> str:
    """按权重随机选择性格类型"""
    types = list(BOT_PERSONALITIES.keys())
    weights = [BOT_PERSONALITIES[t]['weight'] for t in types]
    return random.choices(types, weights=weights, k=1)[0]


async def _fetch_avatar() -> str:
    """从外部 API 获取随机头像"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(AVATAR_API_URL, params={'return': 'json'})
            data = resp.json()
            if data.get('code') == 200 and data.get('data'):
                return data['data']
    except Exception as e:
        logger.debug(f'头像 API 调用失败，使用 fallback: {e}')

    # fallback
    style = random.choice(AVATAR_STYLES)
    seed = random.randint(1000, 99999)
    return f'https://api.dicebear.com/7.x/{style}/svg?seed={seed}'


async def _fetch_nickname() -> str:
    """从外部 API 获取随机中文姓名"""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                NICKNAME_API_URL,
                params={'id': NICKNAME_API_ID, 'key': NICKNAME_API_KEY},
            )
            data = resp.json()
            if data.get('code') == 200 and data.get('name'):
                return data['name'].replace('·', '')
    except Exception as e:
        logger.debug(f'昵称 API 调用失败，使用 fallback: {e}')

    # fallback
    base = random.choice(BOT_NICKNAMES_FALLBACK)
    if random.random() > 0.5:
        return f'{base}{random.randint(10, 9999)}'
    return base


async def _get_bot_role_id(db: AsyncSession) -> int | None:
    """
    获取机器人角色 ID

    :param db: 数据库会话
    :return:
    """
    from backend.app.admin.model.role import Role

    stmt = select(Role.id).where(Role.name == BOT_ROLE_NAME)
    role_id = await db.scalar(stmt)
    return role_id


async def _get_all_bot_user_ids(db: AsyncSession, role_id: int) -> list[int]:
    """
    获取所有机器人用户 ID

    :param db: 数据库会话
    :param role_id: 机器人角色 ID
    :return:
    """
    stmt = select(user_role.c.user_id).where(user_role.c.role_id == role_id)
    result = await db.execute(stmt)
    return [row.user_id for row in result.all()]


async def create_bot_users(db: AsyncSession, role_id: int, count: int) -> list[int]:
    """
    创建机器人用户

    :param db: 数据库会话
    :param role_id: 机器人角色 ID
    :param count: 创建数量
    :return:
    """
    created_ids = []

    for _ in range(count):
        nickname = await _fetch_nickname()
        avatar = await _fetch_avatar()
        username = f'bot_{random.randint(10000000, 99999999)}'

        # 创建系统用户
        new_user = User(
            username=username,
            nickname=nickname,
            password='',
            salt=b'',
            avatar=avatar,
            status=1,
            is_superuser=False,
            is_staff=False,
            is_multi_login=False,
        )
        db.add(new_user)
        await db.flush()

        # 关联机器人角色
        await db.execute(insert(user_role).values(user_id=new_user.id, role_id=role_id, status=1))

        # 创建题库账户
        new_account = UserAccount(user_id=new_user.id, register_channel='bot')
        db.add(new_account)
        await db.flush()

        # 创建统计快照（初始数据，模拟已有一段时间的使用）
        personality = _pick_personality()
        params = BOT_PERSONALITIES[personality]
        # 初始化一些基础数据，让新机器人看起来不是完全从零开始
        init_days = random.randint(1, 14)
        init_total = sum(
            random.randint(params['per_round_min'] * 3, params['per_round_max'] * 5) for _ in range(init_days)
        )
        init_correct = int(init_total * random.uniform(0.55, 0.85))

        new_stats = UserPracticeStats(
            user_id=new_user.id,
            total_count=init_total,
            correct_count=init_correct,
            total_duration=init_total * random.randint(15, 45),
            practice_days=init_days,
            last_practice_date=timezone.now().date(),
            streak_days=random.randint(0, min(init_days, 5)),
        )
        db.add(new_stats)
        await db.flush()

        created_ids.append(new_user.id)
        logger.info(f'创建机器人用户: {nickname} (ID={new_user.id}, 性格={personality})')

    return created_ids


async def simulate_round_activity(db: AsyncSession, role_id: int) -> dict[str, int]:
    """
    模拟机器人单轮活动（每 2 小时一轮）

    :param db: 数据库会话
    :param role_id: 机器人角色 ID
    :return:
    """
    bot_user_ids = await _get_all_bot_user_ids(db, role_id)
    if not bot_user_ids:
        return {'active_bots': 0, 'total_bots': 0}

    today = timezone.now().date()
    active_count = 0

    for user_id in bot_user_ids:
        # 获取该用户的统计数据
        stats_stmt = select(UserPracticeStats).where(UserPracticeStats.user_id == user_id)
        stats = (await db.execute(stats_stmt)).scalar_one_or_none()
        if not stats:
            continue

        # 根据累计数据推断性格类型
        personality = _infer_personality(stats)
        params = BOT_PERSONALITIES[personality]

        # 如果已经达到总题数上限，大幅降低活跃概率
        effective_prob = params['active_prob']
        if stats.total_count >= params['total_cap']:
            effective_prob *= 0.05  # 到顶后基本不再刷
        elif stats.total_count >= params['total_cap'] * 0.8:
            effective_prob *= 0.3  # 接近上限时放缓

        # 决定本轮是否活跃
        if random.random() > effective_prob:
            # 不活跃时检查是否需要中断连续天数
            if (
                stats.streak_days > 0
                and stats.last_practice_date
                and stats.last_practice_date < today - timedelta(days=1)
            ):
                await db.execute(
                    update(UserPracticeStats).where(UserPracticeStats.id == stats.id).values(streak_days=0)
                )
            continue

        # 生成本轮刷题数
        round_count = random.randint(params['per_round_min'], params['per_round_max'])
        round_correct = int(round_count * random.uniform(0.5, 0.9))
        round_duration = round_count * random.randint(15, 50)

        # 更新统计（增量累加，支持一天多次执行）
        is_first_today = stats.last_practice_date != today

        # 计算连续天数（仅首次今日更新时计算）
        if is_first_today:
            if stats.last_practice_date == today - timedelta(days=1):
                new_streak = stats.streak_days + 1
            elif stats.last_practice_date == today:
                new_streak = stats.streak_days
            else:
                new_streak = 1
        else:
            new_streak = stats.streak_days

        update_data: dict = {
            'total_count': UserPracticeStats.total_count + round_count,
            'correct_count': UserPracticeStats.correct_count + round_correct,
            'total_duration': UserPracticeStats.total_duration + round_duration,
            'last_practice_date': today,
            'streak_days': new_streak,
        }
        if is_first_today:
            update_data['practice_days'] = UserPracticeStats.practice_days + 1

        await db.execute(update(UserPracticeStats).where(UserPracticeStats.id == stats.id).values(**update_data))

        # 写入或更新打卡记录
        existing_checkin = (
            await db.execute(select(UserCheckIn).where(UserCheckIn.user_id == user_id, UserCheckIn.check_date == today))
        ).scalar_one_or_none()

        if existing_checkin:
            # 累加到已有打卡记录
            await db.execute(
                update(UserCheckIn)
                .where(UserCheckIn.id == existing_checkin.id)
                .values(
                    practice_count=UserCheckIn.practice_count + round_count,
                    practice_duration=UserCheckIn.practice_duration + round_duration,
                )
            )
        else:
            db.add(
                UserCheckIn(
                    user_id=user_id,
                    created_by=user_id,
                    check_date=today,
                    practice_count=round_count,
                    practice_duration=round_duration,
                )
            )

        active_count += 1

    return {'active_bots': active_count, 'total_bots': len(bot_user_ids)}


def _infer_personality(stats: UserPracticeStats) -> str:
    """
    根据统计数据推断性格类型

    :param stats: 用户统计快照
    :return:
    """
    days = max(stats.practice_days, 1)
    avg_daily = stats.total_count / days

    if avg_daily >= 50:
        return 'hardcore'
    elif avg_daily >= 20:
        return 'diligent'
    elif avg_daily >= 10:
        return 'normal'
    return 'casual'


async def run_bot_simulation() -> dict:
    """运行单轮机器人模拟（每 2 小时执行一次）"""
    async with async_db_session() as db:
        role_id = await _get_bot_role_id(db)
        if not role_id:
            logger.warning(f'未找到角色 "{BOT_ROLE_NAME}"，请先创建')
            return {'error': f'角色 "{BOT_ROLE_NAME}" 不存在'}

        # 1. 随机创建新机器人（每轮 0~2 个，日均 ~12-18 个）
        new_count = random.choices([0, 1, 2], weights=[25, 50, 25], k=1)[0]
        new_ids = []
        if new_count > 0:
            new_ids = await create_bot_users(db, role_id, new_count)
            logger.info(f'本轮新增 {new_count} 个机器人用户')

        # 2. 模拟所有机器人的本轮活动
        activity = await simulate_round_activity(db, role_id)
        logger.info(f'机器人活动模拟完成: {activity["active_bots"]}/{activity["total_bots"]} 本轮活跃')

        await db.commit()

        return {
            'new_bots': len(new_ids),
            'active_bots': activity['active_bots'],
            'total_bots': activity['total_bots'],
            'date': str(timezone.now().date()),
        }
