#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import OrderedDict
from decimal import Decimal
import re
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
from backend.plugin.render_book.schema.render import (
    BookKind,
    RenderAnswerLayout,
    RenderContentMode,
    RenderDeliveryMode,
    RenderJobCreate,
    RenderOutputTargets,
    RenderVariant,
    SolutionMode,
)
from backend.utils.timezone import timezone


def clean_html_text(text: str | None) -> str:
    """清理题干、解析与材料中的 HTML 标签与格式噪音"""
    if not text:
        return ""
    text = re.sub(r'<\s*br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</\s*p\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&nbsp;', ' ').replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    lines = [line.strip() for line in text.split('\n')]
    return '\n'.join([line for line in lines if line])


def clean_opt_text(text: str | None, key: str) -> str:
    """清理选项文本中的 HTML 标签及冗余选项序号前缀（如 A. A.）"""
    cleaned = clean_html_text(text)
    return re.sub(rf'^{re.escape(key)}[\.\、\s\:]+', '', cleaned, flags=re.IGNORECASE).strip()

QUESTION_TYPE_LABELS = {
    'single_choice': '单选题',
    'multiple_choice': '多选题',
    'true_false': '判断题',
    'fill_blank': '填空题',
    'short_answer': '简答题',
    'composite': '材料题',
    'interactive': '交互题',
    # 兼容题型
    'single': '单选题',
    'multiple': '多选题',
    'judgement': '判断题',
    'fill': '填空题',
    'shortAnswer': '简答题',
}


class RenderPayloadService:
    """统一题本渲染载荷组装服务（面向新题库 question_bank_v2）。"""

    TEMPLATE_BOOK_KIND_MAP: dict[str, BookKind] = {
        'gongkao_xingce': 'exam',
        'gongkao_practice': 'custom',
        'gongkao_mistake': 'wrong',
        'exam_paper': 'exam',
        'practice': 'custom',
        'wrong_question': 'wrong',
        'basic_calculation': 'custom',
        'hanyu': 'custom',
    }

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
    def resolve_book_kind(cls, payload: RenderJobCreate) -> BookKind:
        if payload.book_kind is not None:
            return payload.book_kind
        return cls.TEMPLATE_BOOK_KIND_MAP.get(payload.template_key, 'custom')

    @staticmethod
    def resolve_export_config_from_legacy(
        *,
        solution_mode: SolutionMode | None,
        output_targets: RenderOutputTargets | None = None,
        include_answer: bool = False,
        include_analysis: bool = False,
    ) -> tuple[RenderContentMode, RenderAnswerLayout | None, RenderDeliveryMode]:
        resolved_targets = output_targets or RenderOutputTargets()
        resolved_solution_mode = solution_mode

        if resolved_solution_mode is None:
            if resolved_targets.solution_pdf:
                resolved_solution_mode = 'separate'
            elif include_answer or include_analysis:
                resolved_solution_mode = 'appendix'
            else:
                resolved_solution_mode = 'none'

        if resolved_solution_mode == 'inline':
            return 'questions_with_answers', 'inline', 'single_pdf'
        if resolved_solution_mode == 'appendix':
            return 'questions_with_answers', 'appendix', 'single_pdf'
        if resolved_solution_mode == 'separate':
            return 'questions_with_answers', 'appendix', 'split_pdf'
        return 'questions_only', None, 'single_pdf'

    @classmethod
    def resolve_export_config(
        cls,
        payload: RenderJobCreate,
    ) -> tuple[RenderContentMode, RenderAnswerLayout | None, RenderDeliveryMode]:
        if payload.content_mode is None and payload.answer_layout is None and payload.delivery_mode is None:
            return cls.resolve_export_config_from_legacy(
                solution_mode=payload.solution_mode,
                output_targets=payload.output_targets,
                include_answer=payload.options.include_answer,
                include_analysis=payload.options.include_analysis,
            )

        content_mode: RenderContentMode = payload.content_mode or 'questions_only'
        answer_layout = payload.answer_layout
        delivery_mode: RenderDeliveryMode = payload.delivery_mode or 'single_pdf'

        if content_mode == 'questions_only':
            if answer_layout is not None:
                raise ValueError('仅题目模式不支持 answer_layout。')
            if delivery_mode != 'single_pdf':
                raise ValueError('仅题目模式当前仅支持 single_pdf。')
            return 'questions_only', None, 'single_pdf'

        if answer_layout is None:
            answer_layout = 'appendix'
        if answer_layout == 'inline' and delivery_mode != 'single_pdf':
            raise ValueError('inline 排版仅支持 single_pdf。')
        return content_mode, answer_layout, delivery_mode

    @classmethod
    def resolve_solution_mode(cls, payload: RenderJobCreate) -> SolutionMode:
        if payload.content_mode is None and payload.answer_layout is None and payload.delivery_mode is None:
            if payload.solution_mode is not None:
                return payload.solution_mode
            if payload.output_targets.solution_pdf:
                return 'separate'
            if payload.options.include_answer or payload.options.include_analysis:
                return 'appendix'
            return 'none'

        content_mode, answer_layout, delivery_mode = cls.resolve_export_config(payload)
        if content_mode == 'questions_only':
            return 'none'
        if answer_layout == 'inline':
            return 'inline'
        if delivery_mode == 'split_pdf':
            return 'separate'
        return 'appendix'

    @classmethod
    def resolve_render_variants(cls, payload: RenderJobCreate, solution_mode: SolutionMode) -> list[RenderVariant]:
        content_mode, answer_layout, delivery_mode = cls.resolve_export_config(payload)
        if content_mode == 'questions_only':
            return ['questions_only']
        if answer_layout == 'inline':
            return ['combined_inline']
        if delivery_mode == 'split_pdf':
            variants: list[RenderVariant] = []
            if payload.output_targets.question_pdf:
                variants.append('questions_only')
            if payload.output_targets.solution_pdf:
                variants.append('solutions_only')
            return variants or ['questions_only', 'solutions_only']
        if answer_layout == 'appendix':
            return ['combined_appendix']
        return ['questions_only']

    @staticmethod
    def _normalize_basic_calculation_questions(raw_questions: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_questions, list):
            return []

        questions: list[dict[str, Any]] = []
        for index, item in enumerate(raw_questions, start=1):
            if not isinstance(item, dict):
                continue
            expression = str(item.get('expression') or '').strip()
            if not expression:
                continue
            answer = item.get('answer')
            answer_text = '' if answer is None else str(answer).strip()
            section_title = str(item.get('section_title') or item.get('type_title') or '基础计算').strip()
            questions.append({
                'number': index,
                'expression': expression,
                'answer_text': answer_text,
                'section_title': section_title or '基础计算',
            })
        return questions[:200]

    @classmethod
    def _build_basic_calculation_payload(cls, payload: RenderJobCreate) -> RenderDocumentPayload:
        questions = cls._normalize_basic_calculation_questions(payload.metadata.get('questions'))
        if not questions:
            raise ValueError('未找到可导出的计算题，请先生成题目。')

        book_kind = cls.resolve_book_kind(payload)
        content_mode, answer_layout, delivery_mode = cls.resolve_export_config(payload)
        solution_mode = cls.resolve_solution_mode(payload)
        render_variants = cls.resolve_render_variants(payload, solution_mode)
        type_title = str(payload.metadata.get('type_title') or payload.subtitle or '基础计算').strip()
        type_hint = str(payload.metadata.get('type_hint') or '').strip()

        section_map: OrderedDict[str, RenderSectionPayload] = OrderedDict()
        for item in questions:
            section_title = item['section_title']
            if section_title not in section_map:
                section_map[section_title] = RenderSectionPayload(
                    key=f'basic_calculation_{len(section_map) + 1}',
                    title=section_title,
                    questions=[],
                )
            section_map[section_title].questions.append(
                RenderQuestionPayload(
                    number=item['number'],
                    question_id=item['number'],
                    type='calculation',
                    type_label='计算题',
                    stem_text=item['expression'],
                    answer_text=item['answer_text'],
                    tags=['基础计算', section_title],
                )
            )

        meta_lines = [f'题量：{len(questions)}', f'类型：{type_title}']
        if type_hint:
            meta_lines.append(type_hint)

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
            book=RenderBookMeta(
                title=payload.title.strip(),
                subtitle=payload.subtitle,
                meta_lines=meta_lines,
            ),
            options=payload.options,
            paper=RenderPaperPayload(
                question_count=len(questions),
                material_count=0,
                sections=list(section_map.values()),
                materials=[],
            ),
            metadata={
                **payload.metadata,
                'filters': payload.filters,
                'subject': payload.subject,
                'template_key': payload.template_key,
                'book_kind': book_kind,
                'content_mode': content_mode,
                'answer_layout': answer_layout,
                'delivery_mode': delivery_mode,
                'solution_mode': solution_mode,
                'render_variants': render_variants,
                'question_ids': [item['number'] for item in questions],
                'generated_at': timezone.now().isoformat(),
            },
        )

    @classmethod
    async def _load_questions(
        cls,
        *,
        db: AsyncSession,
        payload: RenderJobCreate,
    ) -> list[dict[str, Any]]:
        question_ids = cls._parse_ids(payload.filters.get('question_ids'))
        user_id = payload.metadata.get('user_id')
        if not isinstance(user_id, int):
            return []

        metadata_source = payload.metadata.get('source_type')
        if metadata_source in {'wrong', 'favorite', 'note'}:
            source_type = metadata_source
        elif payload.template_key == 'wrong_question':
            source_type = 'wrong'
        else:
            source_type = 'placement'

        bank_id = payload.filters.get('bank_id') if isinstance(payload.filters.get('bank_id'), int) else None
        section_id = payload.filters.get('section_id') if isinstance(payload.filters.get('section_id'), int) else None

        # 1. 如果没有显式传 question_ids，但传了 bank_id，自动按题库编排加载题目
        if not question_ids:
            if source_type == 'placement' and bank_id is not None:
                bank_items_stmt = (
                    select(QbBankItem.question_id)
                    .join(
                        QbBankRevision,
                        and_(
                            QbBankRevision.id == QbBankItem.bank_revision_id,
                            QbBankRevision.deleted == 0,
                        ),
                    )
                    .join(
                        QbBank,
                        and_(
                            QbBank.id == QbBankRevision.bank_id,
                            QbBank.current_revision_id == QbBankRevision.id,
                            QbBank.deleted == 0,
                        ),
                    )
                    .where(
                        QbBank.id == bank_id,
                        QbBankItem.deleted == 0,
                        QbBankItem.is_active.is_(True),
                    )
                    .order_by(QbBankItem.section_id, QbBankItem.sort_order, QbBankItem.id)
                )
                if section_id is not None:
                    bank_items_stmt = bank_items_stmt.where(QbBankItem.section_id == section_id)
                question_ids = list((await db.execute(bank_items_stmt)).scalars().all())
            elif source_type == 'wrong':
                wrong_stmt = (
                    select(QbWrongQuestionState.question_id)
                    .where(
                        QbWrongQuestionState.user_id == user_id,
                        QbWrongQuestionState.status == 'active',
                        QbWrongQuestionState.deleted == 0,
                    )
                    .order_by(QbWrongQuestionState.updated_time.desc())
                    .limit(100)
                )
                question_ids = list((await db.execute(wrong_stmt)).scalars().all())

        if not question_ids:
            return []

        # 2. 校验所选题目归属与用户权限
        if source_type == 'placement':
            if bank_id is None:
                # 题库题目若未指定 bank_id，允许通过基础查询
                allowed_question_ids = set(question_ids)
            else:
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
                allowed_question_ids = set((await db.execute(allowed_stmt)).scalars().all())
        elif source_type == 'wrong':
            allowed_stmt = select(QbWrongQuestionState.question_id).where(
                QbWrongQuestionState.user_id == user_id,
                QbWrongQuestionState.question_id.in_(question_ids),
                QbWrongQuestionState.status == 'active',
                QbWrongQuestionState.deleted == 0,
            )
            allowed_question_ids = set((await db.execute(allowed_stmt)).scalars().all())
        elif source_type == 'favorite':
            allowed_stmt = select(QbQuestionFavorite.question_id).where(
                QbQuestionFavorite.user_id == user_id,
                QbQuestionFavorite.question_id.in_(question_ids),
                QbQuestionFavorite.deleted == 0,
            )
            allowed_question_ids = set((await db.execute(allowed_stmt)).scalars().all())
        elif source_type == 'note':
            allowed_stmt = select(QbQuestionNote.question_id).where(
                QbQuestionNote.user_id == user_id,
                QbQuestionNote.question_id.in_(question_ids),
                QbQuestionNote.deleted == 0,
            )
            allowed_question_ids = set((await db.execute(allowed_stmt)).scalars().all())
        else:
            return []

        question_ids = [qid for qid in question_ids if qid in allowed_question_ids]
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
        requested_order = {qid: idx for idx, qid in enumerate(question_ids)}
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
        if not question_ids or db is None:
            return {}
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
        if not question_ids or db is None:
            return {}
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
        if not question_ids or db is None:
            return {}, []
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
                    title=clean_html_text(row['title']),
                    content_text=row['content'] or '',
                    source_text=row['source_name'],
                ),
            )
        return links, list(materials.values())

    @classmethod
    async def build_payload(cls, *, db: AsyncSession, payload: RenderJobCreate) -> RenderDocumentPayload:
        if payload.template_key == 'basic_calculation':
            return cls._build_basic_calculation_payload(payload)

        questions = await cls._load_questions(db=db, payload=payload)
        if not questions:
            raise ValueError('未找到符合条件的题目，无法生成题本。')

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

        book_kind = cls.resolve_book_kind(payload)
        content_mode, answer_layout, delivery_mode = cls.resolve_export_config(payload)
        solution_mode = cls.resolve_solution_mode(payload)
        render_variants = cls.resolve_render_variants(payload, solution_mode)
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
                stem_text=question['stem'] or '',
                options=[
                    RenderQuestionOptionPayload(
                        key=option['option_code'],
                        content_text=option['content'] or '',
                    )
                    for option in options
                ],
                answer_text=cls._answer_text(answer_data),
                answer_raw=answer_data,
                analysis_text=question.get('explanation') or '',
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


render_payload_service = RenderPayloadService()
