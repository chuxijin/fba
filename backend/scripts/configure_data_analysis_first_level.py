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

from backend.app.challenge.model import ChallengeLevel, ChallengeLevelSection
from backend.database.db import async_db_session

FIRST_LEVEL_RULE = {
    'mode': 'consecutive_attempts',
    'required_attempts': 5,
    'min_accuracy_rate': '75',
    'max_total_time': 120,
    'attempt_requirements': [
        {
            'seq_no': 1,
            'title': '认识四概念',
            'description': '先稳住，不抢速',
            'min_accuracy_rate': '75',
            'max_total_time': 120,
        },
        {
            'seq_no': 2,
            'title': '提速识别',
            'description': '同样准确率，压缩一点时间',
            'min_accuracy_rate': '75',
            'max_total_time': 100,
        },
        {
            'seq_no': 3,
            'title': '四概念全对',
            'description': '基期、现期、增长率、增长量都要稳',
            'min_accuracy_rate': '100',
            'max_total_time': 120,
        },
        {
            'seq_no': 4,
            'title': '全对加速',
            'description': '全对并控制节奏',
            'min_accuracy_rate': '100',
            'max_total_time': 100,
        },
        {
            'seq_no': 5,
            'title': '登堂入室',
            'description': '全对且更快完成',
            'min_accuracy_rate': '100',
            'max_total_time': 80,
        },
    ],
}

FIRST_LEVEL_SECTION = {
    'seq_no': 1,
    'name': '四概念识别',
    'source_type': 'pool',
    'question_count': 8,
    'source_config': {
        'mode': 'anchor_role_pool',
        'anchor_roles': [
            'current_value',
            'base_value',
            'growth_rate',
            'growth_amount',
        ],
        'display_scope': 'block',
        'min_candidates': 4,
    },
    'required_correct_count': None,
    'enabled': True,
}


def build_display_config(raw_config: dict | None) -> dict:
    """
    构建第一关展示配置

    :param raw_config: 原展示配置
    :return:
    """
    display_config = dict(raw_config) if isinstance(raw_config, dict) else {}
    display_config['completion_rule'] = FIRST_LEVEL_RULE
    display_config['concepts'] = ['现期', '基期', '增长率', '增长量']
    display_config['training_focus'] = '四概念识别'
    return display_config


async def configure_first_level(execute: bool) -> None:
    """
    同步资料分析简单第一关配置

    :param execute: 是否提交
    :return:
    """
    async with async_db_session() as db:
        stmt = (
            sa.select(ChallengeLevel)
            .where(
                ChallengeLevel.challenge_key == 'data_analysis',
                ChallengeLevel.stage == 'easy',
                ChallengeLevel.level_no == 1,
                ChallengeLevel.deleted == 0,
            )
            .with_for_update()
        )
        level = (await db.execute(stmt)).scalars().first()
        if level is None:
            level = ChallengeLevel(
                challenge_key='data_analysis',
                stage='stage_1',
                level_no=1,
                global_no=1,
                title='四概念识别',
                description='只考基期、现期、增长率、增长量四个基础概念。',
                previous_level_id=None,
                question_count=8,
                time_limit=120,
                pass_rate=Decimal('75'),
                star_two_rate=Decimal('100'),
                star_three_rate=Decimal('100'),
                required_section_pass=False,
                display_config=build_display_config(None),
                status='draft',
                config_version=1,
                sort_order=1,
                created_by=0,
                updated_by=0,
            )
            db.add(level)
            await db.flush()
            action = 'create'
        else:
            level.title = '四概念识别'
            level.description = '只考基期、现期、增长率、增长量四个基础概念。'
            level.question_count = 8
            level.time_limit = 120
            level.pass_rate = Decimal('75')
            level.star_two_rate = Decimal('100')
            level.star_three_rate = Decimal('100')
            level.required_section_pass = False
            level.display_config = build_display_config(level.display_config)
            level.config_version += 1
            action = 'update'

        await db.execute(
            sa.delete(ChallengeLevelSection).where(ChallengeLevelSection.level_id == level.id)
        )
        db.add(ChallengeLevelSection(level_id=level.id, **FIRST_LEVEL_SECTION))

        print(
            '[FIRST_LEVEL]'
            f' action={action}'
            f' id={level.id}'
            f' execute={execute}'
            ' source_type=anchor_role_pool'
            ' concepts=现期,基期,增长率,增长量'
            ' question_count=8'
            ' required_attempts=5'
        )

        if not execute:
            await db.rollback()
            print('[DRY_RUN] 未提交，追加 --execute 后才会写入数据库')
            return

        await db.commit()
        print('[COMMIT] 已提交第一关配置')


async def main() -> None:
    """脚本入口"""
    await configure_first_level(bool(ARGS.execute))


if __name__ == '__main__':
    import asyncio

    asyncio.run(main())
