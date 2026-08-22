from __future__ import annotations

import argparse
import asyncio
import os
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('FBA_DEV', '1')

from backend.database.db import async_db_session  # noqa: E402
from backend.plugin.agent.service.adapter.qbank_v2_projection import qbank_v2_projection_service  # noqa: E402


async def run(*, run_id: int, user_id: int) -> None:
    async with async_db_session() as db:
        applied = await qbank_v2_projection_service.replay_run(db=db, run_id=run_id, user_id=user_id)
        await db.commit()
    print(f'run_id={run_id} projection_applied={applied}')


def main() -> None:
    parser = argparse.ArgumentParser(description='补做历史申论 Agent 成功运行的题库 V2 投影')
    parser.add_argument('--run-id', type=int, required=True)
    parser.add_argument('--user-id', type=int, required=True)
    args = parser.parse_args()
    asyncio.run(run(run_id=args.run_id, user_id=args.user_id))


if __name__ == '__main__':
    main()
