"""V2考试到时兜底。每场独立事务，失败保留原状态，由下轮再次尝试。"""

from sqlalchemy import select

from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.app.question_bank_v2.model.practice import QbPracticeSession
from backend.app.question_bank_v2.service.practice_service import practice_service
from backend.app.task.celery import celery_app
from backend.common.log import log
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


@celery_app.task(name='qbank_v2:expire_practice_sessions')
async def expire_practice_sessions() -> dict[str, int]:
    async with async_db_session() as db:
        rows = (
            await db.execute(
                select(QbPracticeSession.session_key, QbPracticeSession.user_id)
                .where(
                    QbPracticeSession.deleted == 0,
                    QbPracticeSession.status.in_({'created', 'in_progress'}),
                    QbPracticeSession.expires_time <= timezone.now(),
                )
                .order_by(QbPracticeSession.expires_time, QbPracticeSession.id)
                .limit(200)
            )
        ).all()
    settled = failed = 0
    for session_key, user_id in rows:
        result = await _settle_one(session_key, user_id)
        settled += int(result is True)
        failed += int(result is None)
    return {'settled': settled, 'failed': failed}


async def _settle_one(session_key: str, user_id: int) -> bool | None:
    try:
        async with async_db_session.begin() as db:
            session = await practice_session_dao.get_by_key(db, session_key, user_id=user_id, for_update=True)
            return session is not None and await practice_service._expire_if_due(db=db, session=session)
    except Exception:
        log.exception('V2考试过期结算失败 session_key={}', session_key)
        return None
