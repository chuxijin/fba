import argparse
import asyncio

from backend.database.db import async_db_session
from backend.plugin.agent.schema.coach import CoachMessageParam
from backend.plugin.agent.service.coach_service import shenlun_coach_service


async def run(*, user_id: int, grading_run_id: int, request_id: str) -> None:
    async with async_db_session() as db:
        session = await shenlun_coach_service.create_session(
            db=db,
            user_id=user_id,
            title='真实教练冒烟',
            grading_run_id=grading_run_id,
        )
        result = await shenlun_coach_service.send_message(
            db=db,
            session_id=session.id,
            user_id=user_id,
            params=CoachMessageParam(
                content='请结合我刚才这道申论题的批改结果，指出我下一次最应该优先改进的一件事。',
                request_id=request_id,
            ),
        )
        print(f'session_id={session.id}')
        print(f'message_count={len(result.messages)}')
        print(f'coach_reply={result.messages[-1].content}')


def main() -> None:
    parser = argparse.ArgumentParser(description='申论教练真实模型冒烟验证')
    parser.add_argument('--user-id', type=int, required=True)
    parser.add_argument('--grading-run-id', type=int, required=True)
    parser.add_argument('--request-id', required=True)
    args = parser.parse_args()
    asyncio.run(run(user_id=args.user_id, grading_run_id=args.grading_run_id, request_id=args.request_id))


if __name__ == '__main__':
    main()
