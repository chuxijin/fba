#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
from datetime import datetime


def parse_online_status(online_json: str | None) -> dict:
    """
    解析在线状态

    :param online_json: online 字段的 JSON 字符串
    :return: {'is_online': bool, 'status_text': str, 'offline_msg': str | None}
    """
    if not online_json:
        # 未配置默认在线
        return {'is_online': True, 'status_text': '在线', 'offline_msg': None}

    try:
        config = json.loads(online_json)
    except json.JSONDecodeError:
        return {'is_online': True, 'status_text': '在线', 'offline_msg': None}

    mode = config.get('mode', 'always')
    offline_msg = config.get('offline_msg')

    # 全天在线
    if mode == 'always':
        return {'is_online': True, 'status_text': '在线', 'offline_msg': None}

    # 离线模式
    if mode == 'offline':
        return {'is_online': False, 'status_text': '离线', 'offline_msg': offline_msg}

    # 按时间段判断
    if mode == 'schedule':
        schedule = config.get('schedule', [])
        if _is_in_schedule(schedule):
            return {'is_online': True, 'status_text': '在线', 'offline_msg': None}
        else:
            return {'is_online': False, 'status_text': '离线', 'offline_msg': offline_msg}

    return {'is_online': True, 'status_text': '在线', 'offline_msg': None}


def is_dark_theme() -> bool:
    """判断当前是否使用暗色主题（23:00-06:00）"""
    hour = datetime.now().hour
    return hour >= 23 or hour < 6


def _is_in_schedule(schedule: list) -> bool:
    """
    判断当前时间是否在排班时间内

    :param schedule: 排班列表
    :return:
    """
    now = datetime.now()
    current_weekday = now.isoweekday()  # 1=周一, 7=周日
    current_time = now.strftime('%H:%M')

    for slot in schedule:
        days_str = slot.get('days', '')
        time_str = slot.get('time', '')

        # 解析星期
        if not _match_day(days_str, current_weekday):
            continue

        # 解析时间段
        if _match_time(time_str, current_time):
            return True

    return False


def _match_day(days_str: str, weekday: int) -> bool:
    """
    判断星期是否匹配

    :param days_str: 星期字符串，如 "1-5", "6,7", "1-7"
    :param weekday: 当前星期 (1-7)
    :return:
    """
    if not days_str:
        return False

    # 处理范围格式 "1-5"
    if '-' in days_str and ',' not in days_str:
        parts = days_str.split('-')
        if len(parts) == 2:
            try:
                start = int(parts[0])
                end = int(parts[1])
                return start <= weekday <= end
            except ValueError:
                return False

    # 处理枚举格式 "6,7"
    days = []
    for part in days_str.replace(' ', '').split(','):
        if '-' in part:
            # 处理混合格式 "1-5,7"
            range_parts = part.split('-')
            if len(range_parts) == 2:
                try:
                    start = int(range_parts[0])
                    end = int(range_parts[1])
                    days.extend(range(start, end + 1))
                except ValueError:
                    pass
        else:
            try:
                days.append(int(part))
            except ValueError:
                pass

    return weekday in days


def _match_time(time_str: str, current_time: str) -> bool:
    """
    判断时间是否在范围内

    :param time_str: 时间范围字符串，如 "09:00-18:00"
    :param current_time: 当前时间，如 "14:30"
    :return:
    """
    if not time_str or '-' not in time_str:
        return False

    parts = time_str.split('-')
    if len(parts) != 2:
        return False

    start_time = parts[0].strip()
    end_time = parts[1].strip()

    return start_time <= current_time <= end_time
