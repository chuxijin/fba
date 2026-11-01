"""uv run python -m backend.scripts.qbank.audit_practice_statistics --question-id 123

仅SELECT，不修复、不重放；在目标环境经授权后手动运行。
"""

import argparse
import asyncio
import json

from backend.app.question_bank_v2.service.statistics_audit_service import audit_question_statistics
from backend.database.db import async_db_session


async def main(question_ids: list[int]) -> None:
    async with async_db_session() as db:
        reports = await audit_question_statistics(db=db, question_ids=question_ids)
    print(json.dumps(reports, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='只读核对V2题目统计（最多100道）')
    parser.add_argument('--question-id', type=int, action='append', required=True)
    args = parser.parse_args()
    if len(args.question_id) > 100 or any(question_id <= 0 for question_id in args.question_id):
        parser.error('题目ID必须为正整数，每次最多100道')
    asyncio.run(main(args.question_id))
