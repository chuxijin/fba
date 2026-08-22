#!/usr/bin/env python3
"""Run one real development-environment Shenlun grading smoke test."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('FBA_DEV', '1')

from backend.app.question_bank_v2.schema.practice import (  # noqa: E402
    CreatePracticeSessionParam,
    SubmitPracticeItemParam,
)
from backend.app.question_bank_v2.service.practice_service import practice_service  # noqa: E402
from backend.database.db import async_db_session  # noqa: E402
from backend.plugin.agent.schema.grading import StartShenlunGradingParam  # noqa: E402
from backend.plugin.agent.service.shenlun_service import shenlun_grading_service  # noqa: E402

DEFAULT_ANSWER = (
    'H市坚持规划引领、分类管控城市用光：制定总体规划，划分亮度管理区域，生态区域只保留功能照明，'
    '限制新增媒体墙和灯光秀，并控制商业、旅游场所灯光亮度、色温和辐射范围。坚持绿色节能，推广'
    '太阳能路灯和低耗LED，科学确定安装位置。突出城市特色，结合自然地理、历史文化分区设计夜景。'
    '推进智慧管理，通过统一控制和实时监测掌握能耗、故障，及时调度维修，并建设多功能智慧灯杆、'
    '感应式公交候车亭。坚持以人为本，设置平日、周末、节假日模式，减少居民干扰，同时整治老旧'
    '小区和背街小巷照明暗盲区。'
)


async def run(*, user_id: int, bank_id: int, model_name: str, timeout_seconds: int) -> None:
    session_key = f'shenlun-smoke-{user_id}-{bank_id}'
    async with async_db_session() as db:
        session = await practice_service.create(
            db=db,
            user_id=user_id,
            obj=CreatePracticeSessionParam(
                source_type='bank',
                bank_id=bank_id,
                question_types=['short_answer'],
                mode='practice',
                limit=1,
                shuffle=False,
                session_key=session_key,
            ),
        )
        item = session.items[0]
        submission = await practice_service.submit_item(
            db=db,
            session_key=session.session_key,
            user_id=user_id,
            session_item_id=item.id,
            obj=SubmitPracticeItemParam(
                response_data=DEFAULT_ANSWER,
                duration_ms=420_000,
            ),
        )
        await db.commit()
        started = await shenlun_grading_service.start(
            db=db,
            attempt_id=submission.attempt_id,
            user_id=user_id,
            params=StartShenlunGradingParam(force_regenerate=True, model_name=model_name),
        )

    deadline = asyncio.get_running_loop().time() + timeout_seconds
    detail = None
    while asyncio.get_running_loop().time() < deadline:
        async with async_db_session() as db:
            detail = await shenlun_grading_service.get_detail(
                db=db,
                run_id=started.run_id,
                user_id=user_id,
            )
        print(
            json.dumps(
                {
                    'run_id': detail.id,
                    'status': detail.status,
                    'stage': detail.stage,
                    'progress': detail.progress,
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if detail.status in {'succeeded', 'failed', 'cancelled'}:
            break
        await asyncio.sleep(2)
    else:
        raise TimeoutError(f'Agent run {started.run_id} did not finish in {timeout_seconds}s')

    result = detail.result_payload or {}
    print(
        json.dumps(
            {
                'session_key': session_key,
                'attempt_id': submission.attempt_id,
                'run_id': detail.id,
                'status': detail.status,
                'error_code': detail.error_code,
                'error_message': detail.error_message,
                'score': result.get('score'),
                'display_score': result.get('display_score'),
                'score_status': result.get('score_status'),
                'report_length': len(str(result.get('report_markdown') or '')),
                'point_match_count': len(result.get('point_matches') or []),
                'step_keys': [step.node_key for step in detail.steps],
            },
            ensure_ascii=False,
            default=str,
        ),
        flush=True,
    )
    if detail.status != 'succeeded':
        raise RuntimeError(detail.error_message or f'Agent run failed: {detail.status}')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--user-id', type=int, default=20)
    parser.add_argument('--bank-id', type=int, default=2703)
    parser.add_argument('--model-name', default='gpt-5.4')
    parser.add_argument('--timeout-seconds', type=int, default=600)
    args = parser.parse_args()
    asyncio.run(
        run(
            user_id=args.user_id,
            bank_id=args.bank_id,
            model_name=args.model_name,
            timeout_seconds=args.timeout_seconds,
        )
    )


if __name__ == '__main__':
    main()
