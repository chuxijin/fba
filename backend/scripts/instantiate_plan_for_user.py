#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import asyncio
import sys

from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.study_plan.schema.template import InstantiateStudyPlanTemplateParam  # noqa: E402
from backend.app.study_plan.service.template_service import instantiate_template  # noqa: E402
from backend.database.db import async_db_session  # noqa: E402


def build_args() -> argparse.Namespace:
    """构建命令行参数"""
    parser = argparse.ArgumentParser(description='为指定用户基于学习规划模板实例化一份计划')
    parser.add_argument('--user', type=int, required=True, help='目标学员 user_id')
    parser.add_argument('--template', type=int, required=True, help='来源 template_id')
    parser.add_argument('--title', type=str, default=None, help='计划标题（默认沿用模板名）')
    parser.add_argument('--start', type=str, default=None, help='起始日期 YYYY-MM-DD（默认今天）')
    parser.add_argument('--creator', type=int, default=1, help='创建者 user_id（默认 admin=1）')
    return parser.parse_args()


async def main() -> int:
    """
    脚本入口
    """
    args = build_args()
    start_date = date.fromisoformat(args.start) if args.start else date.today()

    async with async_db_session.begin() as db:
        from backend.app.study_plan.crud import study_plan_template_dao

        template = await study_plan_template_dao.get(db, args.template)
        if template is None:
            print(f'[ERROR] template {args.template} not found', file=sys.stderr)
            return 1

        title = args.title or template.name
        param = InstantiateStudyPlanTemplateParam(
            template_id=args.template,
            user_id=args.user,
            title=title,
            start_date=start_date,
        )
        plan = await instantiate_template(db, param, creator_id=args.creator)
        print(
            f'[OK] plan id={plan.id} created for user={args.user} '
            f'title="{plan.title}" '
            f'range={plan.start_date}~{plan.end_date} domain={plan.domain}'
        )

    return 0


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
