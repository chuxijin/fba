#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import sys

from datetime import timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from backend.app.cms.model import CmsSlot
from backend.app.quest.model import Quest
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


ADMIN_USER_ID = 1


async def seed_quests(db) -> dict[str, int]:
    """
    插入 3 条 quest 种子任务

    :param db: 异步会话
    :return:
    """
    now = timezone.now()
    code_to_id: dict[str, int] = {}

    presets = [
        {
            'code': 'daily_checkin_2026',
            'name': '每日签到送积分',
            'brief': '每天打开小程序签到,即可领取 10 积分',
            'info': '签到任务无需提交内容,完成后自动发放奖励',
            'detail': (
                '<p>每日签到任务说明:</p>'
                '<ul>'
                '<li>每天可领取一次</li>'
                '<li>奖励 <b>10 积分</b></li>'
                '<li>积分可在积分商城兑换</li>'
                '</ul>'
            ),
            'cover_image': 'https://img.icons8.com/color/96/calendar.png',
            'start_time': now - timedelta(days=1),
            'end_time': now + timedelta(days=30),
            'status': 1,
            'total_quota': 0,
            'claimed_count': 0,
            'max_claims_per_user': 1,
            'claim_expire_seconds': 0,
            'submission_required': False,
            'review_required': False,
            'reward_type': 'points',
            'reward_data': {'amount': 10, 'family_code': 'default'},
            'sort': 100,
            'created_by': ADMIN_USER_ID,
        },
        {
            'code': 'share_to_friend_2026',
            'name': '分享给好友赢奖励',
            'brief': '分享小程序给好友,提交分享截图领取 50 积分',
            'info': '请提交清晰的分享聊天截图,管理员审核通过后发放奖励',
            'detail': (
                '<p>分享任务规则:</p>'
                '<ol>'
                '<li>分享小程序给至少 1 位好友</li>'
                '<li>截图保留聊天界面</li>'
                '<li>提交截图等待审核</li>'
                '<li>审核通过后发放 <b>50 积分</b></li>'
                '</ol>'
            ),
            'cover_image': 'https://img.icons8.com/color/96/share.png',
            'start_time': now - timedelta(days=1),
            'end_time': now + timedelta(days=60),
            'status': 1,
            'total_quota': 100,
            'claimed_count': 0,
            'max_claims_per_user': 3,
            'claim_expire_seconds': 86400,
            'submission_required': True,
            'review_required': True,
            'reward_type': 'points',
            'reward_data': {'amount': 50, 'family_code': 'default'},
            'sort': 90,
            'created_by': ADMIN_USER_ID,
        },
        {
            'code': 'first_practice_2026',
            'name': '完成首次练习',
            'brief': '完成任意一次能力练习,提交截图领取 20 积分',
            'info': '完成首次练习后提交练习截图,管理员审核',
            'detail': (
                '<p>新人任务:</p>'
                '<p>引导新用户体验核心功能,完成首次练习后可领取 <b>20 积分</b>。</p>'
            ),
            'cover_image': 'https://img.icons8.com/color/96/training.png',
            'start_time': None,
            'end_time': None,
            'status': 1,
            'total_quota': 0,
            'claimed_count': 0,
            'max_claims_per_user': 1,
            'claim_expire_seconds': 0,
            'submission_required': True,
            'review_required': True,
            'reward_type': 'points',
            'reward_data': {'amount': 20, 'family_code': 'default'},
            'sort': 80,
            'created_by': ADMIN_USER_ID,
        },
    ]

    for item in presets:
        existing = (await db.execute(select(Quest).where(Quest.code == item['code']))).scalar_one_or_none()
        if existing is not None:
            print(f'[skip] quest {item["code"]} 已存在 id={existing.id}')
            code_to_id[item['code']] = existing.id
            continue

        obj = Quest(**item)
        db.add(obj)
        await db.flush()
        code_to_id[item['code']] = obj.id
        print(f'[insert] quest {item["code"]} -> id={obj.id}')

    return code_to_id


async def seed_slots(db, quest_ids: dict[str, int]) -> None:
    """
    插入 2 条 cms_slot 种子数据

    :param db: 异步会话
    :param quest_ids: 任务码到 ID 的映射
    :return:
    """
    share_quest_id = quest_ids.get('share_to_friend_2026')
    checkin_quest_id = quest_ids.get('daily_checkin_2026')

    presets = [
        {
            'code': 'welcome_curtain_2026',
            'name': '启动幕布-分享任务',
            'slot_type': 'curtain',
            'scene': 'app_launch',
            'title': '新春活动开启',
            'subtitle': '分享给好友赢 50 积分',
            'image_url': 'https://img.icons8.com/color/240/gift.png',
            'detail': (
                '<p style="text-align:center;font-size:16px;">'
                '🎉 新年快乐!分享小程序给好友,即可领取 <b>50 积分</b> 大奖!'
                '</p>'
            ),
            'jump_type': 'quest' if share_quest_id else 'none',
            'jump_target': str(share_quest_id) if share_quest_id else None,
            'jump_extra': None,
            'start_time': None,
            'end_time': None,
            'status': 1,
            'priority': 100,
            'target_user_type': 0,
            'target_min_member_level': 0,
            'target_extra': None,
            'max_show_per_user': 5,
            'max_show_per_day_per_user': 1,
            'close_dismiss_count': 2,
            'can_close': True,
            'extra': {'position': 'center', 'animation': 'fade'},
            'created_by': ADMIN_USER_ID,
        },
        {
            'code': 'home_banner_checkin_2026',
            'name': '首页 Banner-签到入口',
            'slot_type': 'banner',
            'scene': 'home',
            'title': '每日签到',
            'subtitle': '签到送积分,连续签到有惊喜',
            'image_url': 'https://img.icons8.com/color/240/calendar-plus.png',
            'detail': None,
            'jump_type': 'quest' if checkin_quest_id else 'none',
            'jump_target': str(checkin_quest_id) if checkin_quest_id else None,
            'jump_extra': None,
            'start_time': None,
            'end_time': None,
            'status': 1,
            'priority': 50,
            'target_user_type': 0,
            'target_min_member_level': 0,
            'target_extra': None,
            'max_show_per_user': 0,
            'max_show_per_day_per_user': 0,
            'close_dismiss_count': 0,
            'can_close': True,
            'extra': {'carousel_interval': 3000},
            'created_by': ADMIN_USER_ID,
        },
    ]

    for item in presets:
        existing = (await db.execute(select(CmsSlot).where(CmsSlot.code == item['code']))).scalar_one_or_none()
        if existing is not None:
            print(f'[skip] slot {item["code"]} 已存在 id={existing.id}')
            continue

        obj = CmsSlot(**item)
        db.add(obj)
        await db.flush()
        print(f'[insert] slot {item["code"]} -> id={obj.id} jump_target={item["jump_target"]}')


async def main() -> None:
    """主入口"""
    async with async_db_session.begin() as db:
        quest_ids = await seed_quests(db)
        await seed_slots(db, quest_ids)
        print('\n[done] 种子数据写入完成')


if __name__ == '__main__':
    asyncio.run(main())
