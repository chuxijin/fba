from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_question import question_dao
from backend.app.question_bank_v2.model.asset import QbQuestionAsset
from backend.app.question_bank_v2.model.material import QbMaterial, QbMaterialRevision, QbQuestionMaterial
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer, QbQuestionExplanation
from backend.app.question_bank_v2.schema.external_practice import ImportPracticeQuestionParam
from backend.app.question_bank_v2.schema.review import ExternalMaterialParam
from backend.app.question_bank_v2.utils.external_practice import (
    EXTERNAL_PRACTICE_ORIGIN,
    import_digest,
    question_content_digest,
)
from backend.common.exception import errors
from backend.utils.timezone import timezone


class CRUDExternalPractice:
    """复用现有题目、材料和作答表，来源关联存放在会话快照中。"""

    @staticmethod
    async def get_session(
        db: AsyncSession, *, user_id: int, log_id: int, for_update: bool = False
    ) -> QbPracticeSession | None:
        stmt = select(QbPracticeSession).where(
            QbPracticeSession.user_id == user_id,
            QbPracticeSession.source_ref == f'external-practice:{log_id}',
            QbPracticeSession.source_snapshot['origin'].as_string() == EXTERNAL_PRACTICE_ORIGIN,
            QbPracticeSession.deleted == 0,
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def get_items(db: AsyncSession, *, session_id: int) -> list[QbPracticeSessionItem]:
        return list(
            (
                await db.scalars(
                    select(QbPracticeSessionItem)
                    .where(
                        QbPracticeSessionItem.session_id == session_id,
                        QbPracticeSessionItem.deleted == 0,
                    )
                    .order_by(QbPracticeSessionItem.position)
                )
            ).all()
        )

    @staticmethod
    async def get_attempt_ids(db: AsyncSession, *, session_id: int) -> dict[int, int]:
        rows = await db.execute(
            select(QbQuestionAttempt.session_item_id, QbQuestionAttempt.id).where(
                QbQuestionAttempt.session_id == session_id,
                QbQuestionAttempt.deleted == 0,
            )
        )
        return {row.session_item_id: row.id for row in rows}

    @staticmethod
    async def find_reusable_question(db: AsyncSession, *, user_id: int, content_hash: str) -> QbQuestion | None:
        """按内容指纹复用用户已有私有题，跨来源（错题导入 / 刷题记录）共用一份题目"""
        stmt = (
            select(QbQuestion)
            .where(
                QbQuestion.owner_id == user_id,
                QbQuestion.visibility == 'private',
                QbQuestion.status == 'active',
                QbQuestion.deleted == 0,
                QbQuestion.content_hash == content_hash,
            )
            .order_by(QbQuestion.id)
            .limit(1)
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    async def ensure_question(
        db: AsyncSession, *, user_id: int, platform: str, item: ImportPracticeQuestionParam
    ) -> QbQuestion:
        core = item.model_dump(mode='json', include={'stem', 'content_format', 'question_type', 'options'})
        content_hash = question_content_digest(**core)
        code = 'external.' + import_digest(user_id, platform, item.source_question_key, core)[:48]
        question = await external_practice_dao.find_reusable_question(db, user_id=user_id, content_hash=content_hash)
        if question is None:
            question = await question_dao.get_by_code(db, code)
        if question is None:
            try:
                async with db.begin_nested():
                    question = await question_dao.create(
                        db,
                        code=code,
                        owner_id=user_id,
                        visibility='private',
                        origin_type='imported',
                        status='active',
                        stem=item.stem,
                        content_format=item.content_format,
                        question_type=item.question_type,
                        option_data=core['options'],
                        default_score=item.max_score if item.max_score is not None else Decimal(1),
                        difficulty=None,
                        content_hash=content_hash,
                        created_by=user_id,
                    )
            except IntegrityError:
                question = await question_dao.get_by_code(db, code)
                if question is None:
                    raise
        # 相同题目跨报告补充时持有题目行锁，防止重复建立答案、解析和资源关联。
        question = await question_dao.get(db, question.id, for_update=True)
        if question.owner_id != user_id or question.visibility != 'private':
            raise errors.ConflictError(msg='导入题目标识已被其他内容占用')
        return question

    @staticmethod
    async def ensure_material(db: AsyncSession, *, user_id: int, item: ExternalMaterialParam) -> tuple[int, int]:
        code = 'external.' + import_digest(user_id, item.title, item.content, item.content_format)[:48]
        stmt = select(QbMaterial).where(QbMaterial.code == code, QbMaterial.deleted == 0)
        material = (await db.execute(stmt)).scalar_one_or_none()
        if material is None:
            try:
                async with db.begin_nested():
                    material = QbMaterial(code=code, status='active', created_by=user_id)
                    db.add(material)
                    await db.flush()
                    revision = QbMaterialRevision(
                        material_id=material.id,
                        revision_no=1,
                        title=item.title,
                        content=item.content,
                        content_format=item.content_format,
                        status='published',
                        content_hash=import_digest(item.title, item.content, item.content_format),
                        created_by=user_id,
                        published_by=user_id,
                        published_time=timezone.now(),
                    )
                    db.add(revision)
                    await db.flush()
                    material.current_revision_id = revision.id
                    await db.flush()
            except IntegrityError:
                material = (await db.execute(stmt)).scalar_one_or_none()
                if material is None:
                    raise
        if material.created_by != user_id or material.current_revision_id is None:
            raise errors.ConflictError(msg='材料引用状态不完整')
        return material.id, material.current_revision_id

    @staticmethod
    async def supplement_content(
        db: AsyncSession, *, user_id: int, question_id: int, item: ImportPracticeQuestionParam
    ) -> None:
        if item.answer is not None:
            answer = (
                await db.scalars(
                    select(QbQuestionAnswer).where(
                        QbQuestionAnswer.question_id == question_id,
                        QbQuestionAnswer.deleted == 0,
                    )
                )
            ).first()
            if answer is None:
                db.add(QbQuestionAnswer(question_id=question_id, created_by=user_id, **item.answer.model_dump()))
        explanations = set(
            (
                await db.scalars(
                    select(QbQuestionExplanation.explanation_type).where(
                        QbQuestionExplanation.question_id == question_id,
                        QbQuestionExplanation.deleted == 0,
                    )
                )
            ).all()
        )
        for explanation in item.explanations:
            if explanation.explanation_type not in explanations:
                db.add(
                    QbQuestionExplanation(
                        question_id=question_id,
                        created_by=user_id,
                        status='published',
                        **explanation.model_dump(exclude={'version_no'}),
                    )
                )
        assets = (
            set(
                (
                    await db.scalars(
                        select(QbQuestionAsset.link_key).where(
                            QbQuestionAsset.question_id == question_id,
                            QbQuestionAsset.deleted == 0,
                        )
                    )
                ).all()
            )
            if item.assets
            else set()
        )
        for asset in item.assets:
            if asset.link_key not in assets:
                db.add(QbQuestionAsset(question_id=question_id, created_by=user_id, **asset.model_dump()))
        materials = (
            set(
                (
                    await db.execute(
                        select(QbQuestionMaterial.material_id, QbQuestionMaterial.role).where(
                            QbQuestionMaterial.question_id == question_id,
                            QbQuestionMaterial.deleted == 0,
                        )
                    )
                ).all()
            )
            if item.materials
            else set()
        )
        for material in item.materials:
            material_id, revision_id = await CRUDExternalPractice.ensure_material(db, user_id=user_id, item=material)
            if (material_id, material.role) not in materials:
                db.add(
                    QbQuestionMaterial(
                        question_id=question_id,
                        material_id=material_id,
                        material_revision_id=revision_id,
                        role=material.role,
                        sort_order=material.sort_order,
                        created_by=user_id,
                    )
                )
                materials.add((material_id, material.role))
        await db.flush()

    @staticmethod
    async def create_item(
        db: AsyncSession,
        *,
        session: QbPracticeSession,
        question_id: int,
        data: ImportPracticeQuestionParam,
    ) -> QbPracticeSessionItem:
        item = QbPracticeSessionItem(
            session_id=session.id,
            question_id=question_id,
            position=data.position - 1,
            max_score=data.max_score if data.max_score is not None else Decimal(0),
            display_config={'external_practice': data.model_dump(mode='json'), 'section_name': data.module_path[0]},
        )
        db.add(item)
        await db.flush()
        return item

    @staticmethod
    async def save_response(
        db: AsyncSession,
        *,
        session: QbPracticeSession,
        item: QbPracticeSessionItem,
        data: ImportPracticeQuestionParam,
        occurred_at: datetime,
    ) -> None:
        response = (
            await db.scalars(
                select(QbPracticeSessionResponse).where(
                    QbPracticeSessionResponse.session_item_id == item.id,
                    QbPracticeSessionResponse.deleted == 0,
                )
            )
        ).first()
        answered = data.status != 'unanswered'
        if response is None:
            response = QbPracticeSessionResponse(session_id=session.id, session_item_id=item.id)
            db.add(response)
        response.response_data = data.response_data
        response.status = 'graded' if answered else 'not_started'
        response.is_correct = data.status == 'correct' if answered else None
        response.score = data.score
        # 现有草稿时长非空；未知值在快照和作答事实中保留为 null，查询时优先采用快照。
        response.duration_ms = (data.duration_seconds or 0) * 1000
        response.grading_status = 'graded' if answered else 'not_requested'
        response.last_submitted_time = occurred_at if answered else None
        if answered:
            attempt = (
                await db.scalars(
                    select(QbQuestionAttempt).where(
                        QbQuestionAttempt.session_item_id == item.id,
                        QbQuestionAttempt.deleted == 0,
                    )
                )
            ).first()
            if attempt is None:
                attempt = QbQuestionAttempt(
                    user_id=session.user_id,
                    question_id=item.question_id,
                    session_id=session.id,
                    session_item_id=item.id,
                    response_data=data.response_data,
                    attempt_no=1,
                    submitted_time=occurred_at,
                    grading_status='graded',
                    grading_method='rule',
                    grading_result={
                        'origin': EXTERNAL_PRACTICE_ORIGIN,
                        'time_precision': 'date',
                        'source_status': data.status,
                        'practice_log_id': session.source_snapshot['practice_log_id'],
                        'source_question_key': data.source_question_key,
                    },
                )
                db.add(attempt)
            attempt.is_correct = response.is_correct
            attempt.score = data.score
            attempt.duration_ms = data.duration_seconds * 1000 if data.duration_seconds is not None else None
            attempt.content_hash = import_digest(data.model_dump(mode='json', include={'stem', 'options'}))
        await db.flush()

    @staticmethod
    async def remove_session(db: AsyncSession, *, session: QbPracticeSession) -> None:
        """软删本次导入的事实和投影；题目、材料及其他会话继续保留。"""
        now = timezone.now()
        for model in (QbQuestionAttempt, QbPracticeSessionResponse, QbPracticeSessionItem):
            await db.execute(
                update(model)
                .where(model.session_id == session.id, model.deleted == 0)
                .values(
                    deleted=model.id,
                    deleted_time=now,
                )
            )
        session.status = 'cancelled'
        session.deleted = session.id
        session.deleted_time = now
        await db.flush()

    @staticmethod
    async def sync_date(db: AsyncSession, *, session: QbPracticeSession, anchor: datetime) -> None:
        session.started_time = anchor
        await db.execute(
            update(QbQuestionAttempt)
            .where(
                QbQuestionAttempt.session_id == session.id,
                QbQuestionAttempt.deleted == 0,
            )
            .values(submitted_time=anchor)
        )
        await db.execute(
            update(QbPracticeSessionResponse)
            .where(
                QbPracticeSessionResponse.session_id == session.id,
                QbPracticeSessionResponse.status == 'graded',
                QbPracticeSessionResponse.deleted == 0,
            )
            .values(last_submitted_time=anchor)
        )


external_practice_dao = CRUDExternalPractice()
