"""用 capture 事件保存多批次归属；兼容旧状态元数据，不制造复盘或新作答。"""

import hashlib

from typing import Any

from sqlalchemy import exists, func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.schema.review import ENTRY_METADATA_BATCH_KEY, IMPORT_CAPTURE_BATCH_KEY
from backend.common.exception import errors


def import_capture_key(batch_id: str, state_id: int) -> str:
    return f'import:{hashlib.sha256(f"{batch_id}:{state_id}".encode()).hexdigest()}'


def import_capture_data(batch_id: str, metadata: dict[str, Any], *, reused: bool) -> dict[str, Any]:
    return {
        IMPORT_CAPTURE_BATCH_KEY: {
            'id': batch_id,
            'source': metadata.get('source'),
            'section_name': metadata.get('section_name'),
            'reused': reused,
        }
    }


class CRUDWrongImportBatch:
    @staticmethod
    def memberships(user_id: int) -> Any:
        """每个批次/状态一条关联，已撤销的显式事件屏蔽旧 metadata 回退。"""
        saved = QbQuestionReview.review_data[IMPORT_CAPTURE_BATCH_KEY]
        legacy_batch = func.nullif(
            func.trim(QbWrongQuestionState.entry_metadata[ENTRY_METADATA_BATCH_KEY].as_string()), ''
        )
        explicit = select(
            QbQuestionReview.wrong_state_id.label('state_id'),
            saved['id'].as_string().label('batch_id'),
            saved['source'].as_string().label('source'),
            saved['section_name'].as_string().label('section_name'),
            QbQuestionReview.reviewed_time.label('imported_time'),
        ).where(
            QbQuestionReview.user_id == user_id,
            QbQuestionReview.event_type == 'capture',
            QbQuestionReview.deleted == 0,
            saved['id'].as_string().is_not(None),
        )
        explicit_recorded = exists(
            select(QbQuestionReview.id).where(
                QbQuestionReview.user_id == user_id,
                QbQuestionReview.wrong_state_id == QbWrongQuestionState.id,
                QbQuestionReview.event_type == 'capture',
                saved['id'].as_string() == legacy_batch,
            )
        )
        legacy = select(
            QbWrongQuestionState.id.label('state_id'),
            legacy_batch.label('batch_id'),
            QbWrongQuestionState.entry_metadata['source'].as_string().label('source'),
            QbWrongQuestionState.entry_metadata['section_name'].as_string().label('section_name'),
            QbWrongQuestionState.created_time.label('imported_time'),
        ).where(
            QbWrongQuestionState.user_id == user_id,
            QbWrongQuestionState.deleted == 0,
            legacy_batch.is_not(None),
            ~explicit_recorded,
        )
        return union_all(legacy, explicit).subquery('import_memberships')

    @classmethod
    def contains(cls, user_id: int, batch_id: str | None = None) -> Any:
        memberships = cls.memberships(user_id)
        conditions = [memberships.c.state_id == QbWrongQuestionState.id]
        if batch_id is not None:
            conditions.append(memberships.c.batch_id == batch_id)
        return exists(select(memberships.c.state_id).where(*conditions))

    @staticmethod
    async def link(
        db: AsyncSession,
        *,
        user_id: int,
        batch_id: str,
        state_id: int,
        question_id: int,
        metadata: dict[str, Any],
        reused: bool,
    ) -> None:
        """在调用方用户锁及逐题 savepoint 内幂等关联，不修改原错题状态。"""
        key = import_capture_key(batch_id, state_id)
        existing = (
            await db.execute(
                select(QbQuestionReview.id, QbQuestionReview.deleted).where(
                    QbQuestionReview.user_id == user_id,
                    QbQuestionReview.idempotency_key == key,
                )
            )
        ).first()
        if existing is not None:
            if existing.deleted:
                raise errors.RequestError(msg='该批次已撤销，请重新发起导入')
            return
        db.add(
            QbQuestionReview(
                user_id=user_id,
                question_id=question_id,
                wrong_state_id=state_id,
                idempotency_key=key,
                event_type='capture',
                review_data=import_capture_data(batch_id, metadata, reused=reused),
                created_by=user_id,
            )
        )
        await db.flush()

    @classmethod
    async def get_states(cls, db: AsyncSession, *, user_id: int, batch_id: str) -> Any:
        return (
            await db.execute(
                select(
                    QbWrongQuestionState.id,
                    QbWrongQuestionState.question_id,
                    QbWrongQuestionState.entry_metadata,
                )
                .where(
                    QbWrongQuestionState.user_id == user_id,
                    QbWrongQuestionState.deleted == 0,
                    cls.contains(user_id, batch_id),
                )
                .with_for_update()
            )
        ).all()


wrong_import_batch_dao = CRUDWrongImportBatch()
