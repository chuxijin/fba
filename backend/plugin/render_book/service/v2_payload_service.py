from collections import OrderedDict
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.bank import QbBank, QbBankItem, QbBankRevision, QbBankSection
from backend.app.question_bank_v2.model.knowledge import QbKnowledgePoint, QbQuestionKnowledgePoint
from backend.app.question_bank_v2.model.material import QbMaterialRevision, QbQuestionMaterial
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer, QbQuestionExplanation
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.model.user_content import QbQuestionFavorite, QbQuestionNote
from backend.plugin.render_book.schema.payload import (
    RenderBookMeta,
    RenderDocumentPayload,
    RenderMaterialPayload,
    RenderPaperPayload,
    RenderPlanPayload,
    RenderQuestionOptionPayload,
    RenderQuestionPayload,
    RenderSectionPayload,
)
from backend.plugin.render_book.schema.render import RenderJobCreate
from backend.utils.timezone import timezone

QUESTION_TYPE_LABELS = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'true_false': '判断题',
    'fill_blank': '填空题',
    'short_answer': '简答题',
    'composite': '材料题',
    'interactive': '交互题',
}


class V2RenderPayloadService:
    """将 question_bank_v2 的规范化题目组装为渲染插件统一载荷。"""

    @staticmethod
    def _parse_ids(value: Any) -> list[int]:
        values = value.split(',') if isinstance(value, str) else value
        if not isinstance(values, list):
            return []
        result: list[int] = []
        for item in values:
            if isinstance(item, bool):
                continue
            text = str(item).strip()
            if text.isdigit() and int(text) > 0:
                result.append(int(text))
        return list(dict.fromkeys(result))

    @staticmethod
    def _answer_text(answer_data: dict[str, Any] | None) -> str | None:
        if not answer_data or answer_data.get('correct') is None:
            return None
        correct = answer_data['correct']
        if isinstance(correct, list):
            return '、'.join(str(item) for item in correct)
        return str(correct)

    @staticmethod
    def _score_text(value: Decimal | None) -> str | None:
        if value is None:
            return None
        normalized = value.normalize()
        return format(normalized, 'f')

    @staticmethod
    def _difficulty_text(value: Decimal | None) -> str | None:
        if value is None:
            return None
        labels = {1: '简单', 2: '较易', 3: '中等', 4: '较难', 5: '困难'}
        number = int(value)
        return labels.get(number, format(value.normalize(), 'f'))

    @classmethod
    async def _load_questions(
        cls,
        *,
        db: AsyncSession,
        payload: RenderJobCreate,
    ) -> list[dict[str, Any]]:
        question_ids = cls._parse_ids(payload.filters.get('question_ids'))
        user_id = payload.metadata.get('user_id')
        if not question_ids or not isinstance(user_id, int):
            return []

        source_type = str(payload.metadata.get('source_type') or '')
        bank_id = payload.filters.get('bank_id') if isinstance(payload.filters.get('bank_id'), int) else None
        section_id = payload.filters.get('section_id') if isinstance(payload.filters.get('section_id'), int) else None
        if source_type == 'placement':
            if bank_id is None:
                return []
            allowed_stmt = (
                select(QbBankItem.question_id)
                .join(QbBankRevision, QbBankRevision.id == QbBankItem.bank_revision_id)
                .join(
                    QbBank,
                    and_(
                        QbBank.id == QbBankRevision.bank_id,
                        QbBank.current_revision_id == QbBankRevision.id,
                    ),
                )
                .where(
                    QbBank.id == bank_id,
                    QbBankItem.question_id.in_(question_ids),
                    QbBankItem.deleted == 0,
                    QbBankItem.is_active.is_(True),
                    QbBankRevision.deleted == 0,
                    QbBank.deleted == 0,
                )
            )
            if section_id is not None:
                allowed_stmt = allowed_stmt.where(QbBankItem.section_id == section_id)
        elif source_type == 'wrong':
            allowed_stmt = select(QbWrongQuestionState.question_id).where(
                QbWrongQuestionState.user_id == user_id,
                QbWrongQuestionState.question_id.in_(question_ids),
                QbWrongQuestionState.status == 'active',
                QbWrongQuestionState.deleted == 0,
            )
        elif source_type == 'favorite':
            allowed_stmt = select(QbQuestionFavorite.question_id).where(
                QbQuestionFavorite.user_id == user_id,
                QbQuestionFavorite.question_id.in_(question_ids),
                QbQuestionFavorite.deleted == 0,
            )
        elif source_type == 'note':
            allowed_stmt = select(QbQuestionNote.question_id).where(
                QbQuestionNote.user_id == user_id,
                QbQuestionNote.question_id.in_(question_ids),
                QbQuestionNote.deleted == 0,
            )
        else:
            return []
        allowed_question_ids = set((await db.execute(allowed_stmt)).scalars().all())
        question_ids = [question_id for question_id in question_ids if question_id in allowed_question_ids]
        if not question_ids:
            return []

        default_explanation = (
            select(QbQuestionExplanation.content)
            .where(
                QbQuestionExplanation.question_id == QbQuestion.id,
                QbQuestionExplanation.deleted == 0,
                QbQuestionExplanation.status.in_({'published', 'draft'}),
            )
            .order_by(QbQuestionExplanation.is_default.desc(), QbQuestionExplanation.id)
            .limit(1)
            .scalar_subquery()
        )
        requested_order = {question_id: index for index, question_id in enumerate(question_ids)}
        stmt = (
            select(
                QbQuestion.id,
                QbQuestion.stem,
                QbQuestion.question_type,
                QbQuestion.option_data,
                QbQuestion.default_score,
                QbQuestion.difficulty,
                QbQuestionAnswer.answer_data,
                default_explanation.label('explanation'),
            )
            .outerjoin(
                QbQuestionAnswer,
                and_(QbQuestionAnswer.question_id == QbQuestion.id, QbQuestionAnswer.deleted == 0),
            )
            .where(
                QbQuestion.id.in_(question_ids),
                QbQuestion.status == 'active',
                QbQuestion.deleted == 0,
                or_(QbQuestion.visibility != 'private', QbQuestion.owner_id == user_id),
            )
            .order_by(case(requested_order, value=QbQuestion.id, else_=len(requested_order)))
        )
        return [dict(row) for row in (await db.execute(stmt)).mappings().all()]

    @staticmethod
    async def _load_knowledge_points(
        *, db: AsyncSession, question_ids: list[int]
    ) -> dict[int, list[str]]:
        stmt = (
            select(QbQuestionKnowledgePoint.question_id, QbKnowledgePoint.name)
            .join(
                QbKnowledgePoint,
                and_(
                    QbKnowledgePoint.id == QbQuestionKnowledgePoint.knowledge_point_id,
                    QbKnowledgePoint.deleted == 0,
                ),
            )
            .where(
                QbQuestionKnowledgePoint.question_id.in_(question_ids),
                QbQuestionKnowledgePoint.deleted == 0,
            )
            .order_by(QbQuestionKnowledgePoint.question_id, QbQuestionKnowledgePoint.id)
        )
        result: dict[int, list[str]] = {}
        for row in (await db.execute(stmt)).mappings():
            result.setdefault(int(row['question_id']), []).append(row['name'])
        return result

    @staticmethod
    async def _load_contexts(
        *, db: AsyncSession, question_ids: list[int], bank_id: int | None, section_id: int | None
    ) -> dict[int, dict[str, Any]]:
        stmt = (
            select(
                QbBankItem.question_id,
                QbBankItem.id.label('placement_id'),
                QbBankItem.score,
                QbBankItem.section_id,
                QbBankSection.name.label('section_name'),
                QbBank.id.label('bank_id'),
                QbBankRevision.name.label('bank_name'),
                QbBankItem.exam_year,
            )
            .join(
                QbBankRevision,
                and_(QbBankRevision.id == QbBankItem.bank_revision_id, QbBankRevision.deleted == 0),
            )
            .join(QbBank, and_(QbBank.id == QbBankRevision.bank_id, QbBank.deleted == 0))
            .outerjoin(
                QbBankSection,
                and_(
                    QbBankSection.id == QbBankItem.section_id,
                    QbBankSection.bank_revision_id == QbBankItem.bank_revision_id,
                    QbBankSection.deleted == 0,
                ),
            )
            .where(
                QbBankItem.question_id.in_(question_ids),
                QbBankItem.deleted == 0,
                QbBankItem.is_active.is_(True),
            )
        )
        if bank_id is not None:
            stmt = stmt.where(QbBank.id == bank_id, QbBankItem.bank_revision_id == QbBank.current_revision_id)
        if section_id is not None:
            stmt = stmt.where(QbBankItem.section_id == section_id)
        rows = (await db.execute(stmt.order_by(QbBankItem.question_id, QbBankItem.id))).mappings().all()
        return {int(row['question_id']): dict(row) for row in rows}

    @staticmethod
    async def _load_materials(
        *, db: AsyncSession, question_ids: list[int]
    ) -> tuple[dict[int, list[int]], list[RenderMaterialPayload]]:
        stmt = (
            select(
                QbQuestionMaterial.question_id,
                QbQuestionMaterial.material_id,
                QbMaterialRevision.title,
                QbMaterialRevision.content,
                QbMaterialRevision.source_name,
            )
            .join(
                QbMaterialRevision,
                and_(
                    QbMaterialRevision.id == QbQuestionMaterial.material_revision_id,
                    QbMaterialRevision.material_id == QbQuestionMaterial.material_id,
                    QbMaterialRevision.deleted == 0,
                ),
            )
            .where(
                QbQuestionMaterial.question_id.in_(question_ids),
                QbQuestionMaterial.deleted == 0,
            )
            .order_by(QbQuestionMaterial.question_id, QbQuestionMaterial.sort_order)
        )
        links: dict[int, list[int]] = {}
        materials: OrderedDict[int, RenderMaterialPayload] = OrderedDict()
        for row in (await db.execute(stmt)).mappings():
            question_id = int(row['question_id'])
            material_id = int(row['material_id'])
            links.setdefault(question_id, []).append(material_id)
            materials.setdefault(
                material_id,
                RenderMaterialPayload(
                    id=material_id,
                    title=row['title'],
                    content_text=row['content'],
                    source_text=row['source_name'],
                ),
            )
        return links, list(materials.values())

    @classmethod
    async def build_payload(cls, *, db: AsyncSession, payload: RenderJobCreate) -> RenderDocumentPayload:
        # 延迟导入避免与原 payload service 的模块初始化形成环。
        from backend.plugin.render_book.service.payload_service import RenderPayloadService

        questions = await cls._load_questions(db=db, payload=payload)
        if not questions:
            raise ValueError('未找到可访问的 V2 题目，无法生成题本。')

        question_ids = [int(item['id']) for item in questions]
        bank_id = payload.filters.get('bank_id') if isinstance(payload.filters.get('bank_id'), int) else None
        section_id = payload.filters.get('section_id') if isinstance(payload.filters.get('section_id'), int) else None
        knowledge_points = await cls._load_knowledge_points(db=db, question_ids=question_ids)
        contexts = await cls._load_contexts(
            db=db,
            question_ids=question_ids,
            bank_id=bank_id,
            section_id=section_id,
        )
        material_links, materials = await cls._load_materials(db=db, question_ids=question_ids)

        book_kind = RenderPayloadService.resolve_book_kind(payload)
        content_mode, answer_layout, delivery_mode = RenderPayloadService.resolve_export_config(payload)
        solution_mode = RenderPayloadService.resolve_solution_mode(payload)
        render_variants = RenderPayloadService.resolve_render_variants(payload, solution_mode)
        section_map: OrderedDict[str, RenderSectionPayload] = OrderedDict()
        for index, question in enumerate(questions, start=1):
            question_id = int(question['id'])
            context = contexts.get(question_id, {})
            type_code = question['question_type']
            section_title = context.get('section_name') or QUESTION_TYPE_LABELS.get(type_code, type_code)
            source_parts = [context.get('bank_name'), context.get('section_name')]
            if context.get('exam_year'):
                source_parts.append(str(context['exam_year']))
            source_text = ' / '.join(dict.fromkeys(item for item in source_parts if item)) or None
            options = sorted(
                question['option_data'] or [],
                key=lambda item: (item.get('sort_order', 0), item['option_code']),
            )
            answer_data = question.get('answer_data')
            item = RenderQuestionPayload(
                number=index,
                question_id=question_id,
                placement_id=context.get('placement_id'),
                type=type_code,
                type_label=QUESTION_TYPE_LABELS.get(type_code, type_code),
                stem_text=question['stem'],
                options=[
                    RenderQuestionOptionPayload(key=option['option_code'], content_text=option['content'])
                    for option in options
                ],
                answer_text=cls._answer_text(answer_data),
                answer_raw=answer_data,
                analysis_text=question.get('explanation'),
                source_text=source_text,
                source_label=context.get('bank_name'),
                difficulty=cls._difficulty_text(question.get('difficulty')),
                score=cls._score_text(context.get('score') or question.get('default_score')),
                knowledge_points=knowledge_points.get(question_id, []),
                bank_id=context.get('bank_id'),
                bank_name=context.get('bank_name'),
                chapter_id=context.get('section_id'),
                chapter_name=context.get('section_name'),
                material_ids=material_links.get(question_id, []),
                tags=[QUESTION_TYPE_LABELS.get(type_code, type_code)],
            )
            section_map.setdefault(
                section_title,
                RenderSectionPayload(key=section_title, title=section_title, questions=[]),
            ).questions.append(item)

        bank_name = next((item.get('bank_name') for item in contexts.values() if item.get('bank_name')), None)
        section_name = next((item.get('section_name') for item in contexts.values() if item.get('section_name')), None)
        meta_lines = [f'题量：{len(questions)}']
        if bank_name:
            meta_lines.append(f'题库：{bank_name}')
        if section_name:
            meta_lines.append(f'篇章：{section_name}')
        return RenderDocumentPayload(
            template_key=payload.template_key,
            render_plan=RenderPlanPayload(
                book_kind=book_kind,
                content_mode=content_mode,
                answer_layout=answer_layout,
                delivery_mode=delivery_mode,
                solution_mode=solution_mode,
                output_targets=payload.output_targets,
                render_variants=render_variants,
            ),
            book=RenderBookMeta(title=payload.title.strip(), subtitle=payload.subtitle, meta_lines=meta_lines),
            options=payload.options,
            paper=RenderPaperPayload(
                question_count=len(questions),
                material_count=len(materials),
                sections=list(section_map.values()),
                materials=materials,
            ),
            metadata={
                **payload.metadata,
                'filters': payload.filters,
                'question_ids': question_ids,
                'bank_id': bank_id,
                'bank_name': bank_name,
                'section_id': section_id,
                'section_name': section_name,
                'render_variants': render_variants,
                'generated_at': timezone.now().isoformat(),
            },
        )


v2_render_payload_service = V2RenderPayloadService()
