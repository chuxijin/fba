#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import sys

from decimal import Decimal
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_ENV_FILE = PROJECT_ROOT / 'backend' / '.env.prod'


def normalize_env_value(raw_value: str) -> str:
    """
    标准化 dotenv 值

    :param raw_value: 原始值
    :return:
    """
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    if ' #' in value:
        value = value.split(' #', 1)[0].strip()
    return value


def load_env_file(env_file: Path) -> None:
    """
    加载脚本环境变量

    :param env_file: 环境文件
    :return:
    """
    if not env_file.exists():
        raise FileNotFoundError(f'env file not found: {env_file}')

    for line in env_file.read_text(encoding='utf-8').splitlines():
        text_line = line.strip()
        if not text_line or text_line.startswith('#') or '=' not in text_line:
            continue
        key, raw_value = text_line.split('=', 1)
        env_key = key.strip()
        if env_key:
            os.environ[env_key] = normalize_env_value(raw_value)


def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--env-file', default=str(DEFAULT_ENV_FILE))
    parser.add_argument('--execute', action='store_true')
    return parser.parse_args()


ARGS = parse_args()
ENV_FILE = Path(str(ARGS.env_file)).expanduser()
if not ENV_FILE.is_absolute():
    ENV_FILE = PROJECT_ROOT / ENV_FILE
load_env_file(ENV_FILE)

import sqlalchemy as sa

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.challenge.model import ChallengeLevel, ChallengeLevelSection
from backend.database.db import async_db_session

SECOND_LEVEL_RULE = {
    'mode': 'consecutive_attempts',
    'required_attempts': 5,
    'min_accuracy_rate': '75',
    'max_total_time': 120,
    'attempt_requirements': [
        {
            'seq_no': 1,
            'title': '辨认比较口径',
            'description': '先分清同比、环比与变化表达',
            'min_accuracy_rate': '75',
            'max_total_time': 120,
        },
        {
            'seq_no': 2,
            'title': '稳定识别',
            'description': '同样准确率，减少犹豫',
            'min_accuracy_rate': '75',
            'max_total_time': 100,
        },
        {
            'seq_no': 3,
            'title': '四概念全对',
            'description': '同比、环比、变化量、变化幅度都要稳',
            'min_accuracy_rate': '100',
            'max_total_time': 120,
        },
        {
            'seq_no': 4,
            'title': '全对加速',
            'description': '保持全对并压缩时间',
            'min_accuracy_rate': '100',
            'max_total_time': 100,
        },
        {
            'seq_no': 5,
            'title': '口径通关',
            'description': '全对且快速完成',
            'min_accuracy_rate': '100',
            'max_total_time': 80,
        },
    ],
}

SECOND_LEVEL_SECTION = {
    'seq_no': 1,
    'name': '比较口径与变化表达',
    'source_type': 'generator',
    'question_count': 8,
    'source_config': {
        'generator_key': 'data_analysis_concept_identification_v1',
        'params': {
            'concept_ids': [
                'yoy',
                'mom',
                'change_amount',
                'change_rate',
            ],
        },
    },
    'required_correct_count': None,
    'enabled': True,
}


def build_display_config(raw_config: dict | None) -> dict:
    """
    构建第二关展示配置

    :param raw_config: 原展示配置
    :return:
    """
    display_config = dict(raw_config) if isinstance(raw_config, dict) else {}
    display_config['completion_rule'] = SECOND_LEVEL_RULE
    display_config['concepts'] = ['同比', '环比', '变化量', '变化幅度']
    display_config['training_focus'] = '比较口径与变化表达'
    return display_config


async def get_first_level_id(db: AsyncSession) -> int | None:
    """
    获取资料分析第一关 ID

    :param db: 数据库会话
    :return:
    """
    stmt = sa.select(ChallengeLevel.id).where(
        ChallengeLevel.challenge_key == 'data_analysis',
        ChallengeLevel.stage == 'easy',
        ChallengeLevel.level_no == 1,
        ChallengeLevel.deleted == 0,
    )
    return (await db.execute(stmt)).scalars().first()


async def configure_second_level(execute: bool) -> None:
    """
    同步资料分析简单第二关配置

    :param execute: 是否提交
    :return:
    """
    async with async_db_session() as db:
        first_level_id = await get_first_level_id(db)
        stmt = (
            sa.select(ChallengeLevel)
            .where(
                ChallengeLevel.challenge_key == 'data_analysis',
                ChallengeLevel.stage == 'easy',
                ChallengeLevel.level_no == 2,
                ChallengeLevel.deleted == 0,
            )
            .with_for_update()
        )
        level = (await db.execute(stmt)).scalars().first()
        if level is None:
            level = ChallengeLevel(
                challenge_key='data_analysis',
                stage='stage_1',
                level_no=2,
                global_no=2,
                title='比较口径与变化表达',
                description='只考同比、环比、变化量、变化幅度四个概念。',
                previous_level_id=first_level_id,
                question_count=8,
                time_limit=120,
                pass_rate=Decimal('75'),
                star_two_rate=Decimal('100'),
                star_three_rate=Decimal('100'),
                required_section_pass=False,
                display_config=build_display_config(None),
                status='published',
                config_version=1,
                sort_order=2,
                created_by=0,
                updated_by=0,
            )
            db.add(level)
            await db.flush()
            action = 'create'
        else:
            level.title = '比较口径与变化表达'
            level.description = '只考同比、环比、变化量、变化幅度四个概念。'
            level.previous_level_id = first_level_id
            level.question_count = 8
            level.time_limit = 120
            level.pass_rate = Decimal('75')
            level.star_two_rate = Decimal('100')
            level.star_three_rate = Decimal('100')
            level.required_section_pass = False
            level.display_config = build_display_config(level.display_config)
            level.config_version += 1
            action = 'update'

        await db.execute(sa.delete(ChallengeLevelSection).where(ChallengeLevelSection.level_id == level.id))
        db.add(ChallengeLevelSection(level_id=level.id, **SECOND_LEVEL_SECTION))

        print(
            '[SECOND_LEVEL]'
            f' action={action}'
            f' id={level.id}'
            f' previous_level_id={first_level_id}'
            f' execute={execute}'
            ' concepts=同比,环比,变化量,变化幅度'
            ' question_count=8'
            ' required_attempts=5'
        )

        if not execute:
            await db.rollback()
            print('[DRY_RUN] 未提交，追加 --execute 后才会写入数据库')
            return

        await db.commit()
        print('[COMMIT] 已提交第二关配置')


async def main() -> None:
    """脚本入口"""
    await configure_second_level(bool(ARGS.execute))


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
