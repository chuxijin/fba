from copy import deepcopy
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_annotation import question_annotation_dao
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.app.question_bank_v2.model.annotation import QbQuestionAnnotation
from backend.app.question_bank_v2.schema.annotation import AnnotationContext, GetAnnotationsDetail, SaveAnnotationsParam
from backend.app.question_bank_v2.service.user_content_service import user_content_service
from backend.app.question_bank_v2.utils.annotation_policy import persistent_annotations_enabled
from backend.common.exception import errors


class AnnotationService:
    @staticmethod
    async def _context(
        *, db: AsyncSession, user_id: int, question_id: int, obj: AnnotationContext, writing: bool = False
    ) -> tuple[str, list[dict[str, Any]], bool]:
        await user_content_service._resolve_question_context(
            db=db, user_id=user_id, question_id=question_id, bank_item_id=None
        )
        if obj.session_key is not None:
            owned = await practice_session_dao.get_owned_item(
                db,
                session_key=obj.session_key,
                user_id=user_id,
                session_item_id=obj.session_item_id,
                for_update=writing,
            )
            if owned is None or owned[1].question_id != question_id:
                raise errors.NotFoundError(msg='练习题目不存在')
            if writing and owned[0].status not in {'created', 'in_progress'}:
                raise errors.ConflictError(msg='本次练习已结束，请在复盘中补充标注')
            key = f'item:{owned[1].id}'
            if not persistent_annotations_enabled(owned[0]):
                if writing:
                    raise errors.ForbiddenError(msg='该练习不保存标注，请在正式刷题或错题复盘中使用')
                return key, [], False
            if getattr(owned[0], 'mode', 'practice') in {'exam', 'mock'} and owned[0].status not in {
                'submitted',
                'graded',
            }:
                return key, [], True
            previous = await question_annotation_dao.latest_document(
                db, user_id=user_id, question_id=question_id, exclude_context_key=key
            )
            return key, deepcopy(previous.annotations) if previous else [], True
        attempt = await question_annotation_dao.latest_attempt(
            db, user_id=user_id, question_id=question_id, wrong=obj.source == 'wrong'
        )
        original = (
            deepcopy(attempt.annotations or [])
            if attempt and persistent_annotations_enabled(getattr(attempt, 'session', None))
            else []
        )
        return f'review:{attempt.id if attempt else 0}', original, True

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int, question_id: int, obj: AnnotationContext) -> GetAnnotationsDetail:
        key, original, enabled = await AnnotationService._context(
            db=db, user_id=user_id, question_id=question_id, obj=obj
        )
        if not enabled:
            return GetAnnotationsDetail(enabled=False, owner_key=f'user:{user_id}', context_key=key)
        document = await question_annotation_dao.get_document(
            db, user_id=user_id, question_id=question_id, context_key=key
        )
        if obj.session_key is not None:
            annotations = document.annotations if document else []
        else:
            latest = await question_annotation_dao.latest_document(db, user_id=user_id, question_id=question_id)
            annotations = latest.annotations if latest else original
        return GetAnnotationsDetail(
            owner_key=f'user:{user_id}',
            context_key=key,
            annotations=annotations,
            original_annotations=original,
            save_version=document.save_version if document else 0,
        )

    @staticmethod
    async def save(
        *, db: AsyncSession, user_id: int, question_id: int, obj: SaveAnnotationsParam
    ) -> GetAnnotationsDetail:
        if obj.owner_key is not None and obj.owner_key != f'user:{user_id}':
            raise errors.ConflictError(msg='账号已变化，请重新加载标注')
        key, original, _ = await AnnotationService._context(
            db=db, user_id=user_id, question_id=question_id, obj=obj, writing=True
        )
        if obj.context_key != key:
            raise errors.ConflictError(msg='作答记录已变化，请刷新标注后重试')
        material_contexts = await question_annotation_dao.material_contexts(db, question_id)
        for mark in obj.annotations:
            if mark.target == 'material' and (mark.material_id, mark.material_revision_id) not in material_contexts:
                raise errors.RequestError(msg='标注材料不属于本题')
        document = await question_annotation_dao.get_document(
            db, user_id=user_id, question_id=question_id, context_key=key, for_update=True
        )
        version = document.save_version if document else 0
        data = [item.model_dump() for item in obj.annotations]
        # A repeated save after a lost response is idempotent; different stale edits conflict.
        if document and document.annotations == data:
            return GetAnnotationsDetail(
                owner_key=f'user:{user_id}',
                context_key=key,
                annotations=data,
                original_annotations=original,
                save_version=version,
            )
        if obj.save_version != version:
            raise errors.ConflictError(msg='标注已在其他设备更新，请刷新后重试')
        if document is None:
            try:
                async with db.begin_nested():
                    document = QbQuestionAnnotation(
                        user_id=user_id, question_id=question_id, context_key=key, annotations=data
                    )
                    db.add(document)
                    await db.flush()
            except IntegrityError as exc:
                raise errors.ConflictError(msg='标注已更新，请刷新后重试') from exc
        else:
            document.annotations = data
            document.save_version += 1
            await db.flush()
        return GetAnnotationsDetail(
            owner_key=f'user:{user_id}',
            context_key=key,
            annotations=data,
            original_annotations=original,
            save_version=document.save_version,
        )


annotation_service = AnnotationService()
