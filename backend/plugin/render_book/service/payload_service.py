#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re

from collections import OrderedDict
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model import Question, QuestionAnalysis
from backend.app.question_bank.schema.question import QuestionCollectParam
from backend.app.question_bank.service.question_selector_service import question_selector_service
from backend.app.question_bank.service.question_service import question_service
from backend.plugin.render_book.schema.payload import (
    RenderBookMeta,
    RenderDocumentPayload,
    RenderMaterialPayload,
    RenderPaperPayload,
    RenderPlanPayload,
    RenderQuestionOptionPayload,
    RenderQuestionPayload,
    RenderSectionPayload,
    RenderWordPayload,
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

QUESTION_TYPE_LABELS = {
    'single': '单选题',
    'multiple': '多选题',
    'judgement': '判断题',
    'fill': '填空题',
    'shortAnswer': '简答题',
}

DIFFICULTY_LABELS = {
    'easy': '简单',
    'medium': '中等',
    'hard': '困难',
}

REGION_TOKENS = [
    '内蒙古自治区',
    '广西壮族自治区',
    '西藏自治区',
    '宁夏回族自治区',
    '新疆维吾尔自治区',
    '北京市',
    '天津市',
    '上海市',
    '重庆市',
    '黑龙江省',
    '辽宁省',
    '吉林省',
    '河北省',
    '河南省',
    '山东省',
    '山西省',
    '陕西省',
    '江苏省',
    '浙江省',
    '安徽省',
    '福建省',
    '江西省',
    '湖北省',
    '湖南省',
    '广东省',
    '海南省',
    '四川省',
    '贵州省',
    '云南省',
    '青海省',
    '甘肃省',
    '台湾省',
    '香港特别行政区',
    '澳门特别行政区',
    '北京',
    '天津',
    '上海',
    '重庆',
    '黑龙江',
    '辽宁',
    '吉林',
    '河北',
    '河南',
    '山东',
    '山西',
    '陕西',
    '江苏',
    '浙江',
    '安徽',
    '福建',
    '江西',
    '湖北',
    '湖南',
    '广东',
    '海南',
    '四川',
    '贵州',
    '云南',
    '青海',
    '甘肃',
    '台湾',
    '香港',
    '澳门',
    '内蒙古',
    '广西',
    '西藏',
    '宁夏',
    '新疆',
    '市地级',
    '副省级',
    '县乡级',
    '乡镇',
    '行政执法',
]
REGION_TOKENS = sorted(REGION_TOKENS, key=len, reverse=True)
SOURCE_LABEL_NOISE_TOKENS = (
    '网友回忆',
    '考生回忆',
    '回忆版',
    '行测',
    '申论',
    '行政职业能力测验',
    '笔试',
    '面试',
    '真题',
    '试卷',
    '模拟',
    '卷',
)
EXAM_TYPE_PATTERNS = (
    (re.compile(r'国家公务员|国考'), '国考'),
    (re.compile(r'省公务员|省考'), '省考'),
    (re.compile(r'选调生|选调'), '选调'),
    (re.compile(r'事业单位|事业编'), '事业单位'),
    (re.compile(r'公安联考'), '公安联考'),
    (re.compile(r'三支一扶'), '三支一扶'),
    (re.compile(r'军队文职'), '军队文职'),
)
YEAR_PATTERN = re.compile(r'((?:19|20)\d{2})')
BRACKET_CONTENT_PATTERN = re.compile(r'[（(]([^()（）]+)[)）]')


class RenderPayloadService:
    TEMPLATE_BOOK_KIND_MAP: dict[str, BookKind] = {
        'exam_paper': 'exam',
        'practice': 'custom',
        'wrong_question': 'wrong',
        'basic_calculation': 'custom',
        'hanyu': 'custom',
    }

    @staticmethod
    def _parse_int_list(value: Any) -> list[int]:
        if value is None:
            return []
        if isinstance(value, str):
            return question_service.parse_int_csv(value)
        if isinstance(value, list):
            result: list[int] = []
            for item in value:
                if isinstance(item, bool):
                    continue
                if isinstance(item, int) and item > 0:
                    result.append(item)
                    continue
                if isinstance(item, str) and item.strip().isdigit():
                    parsed = int(item.strip())
                    if parsed > 0:
                        result.append(parsed)
            return list(dict.fromkeys(result))
        return []

    @staticmethod
    def _parse_text_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return question_service.parse_text_csv(value)
        if isinstance(value, list):
            values = [str(item).strip() for item in value if str(item).strip()]
            return list(dict.fromkeys(values))
        return []

    @staticmethod
    def _format_answer_text(answer_data: dict[str, Any] | None) -> str | None:
        if not answer_data:
            return None
        correct_value = answer_data.get('correct')
        if correct_value is None:
            return None
        if isinstance(correct_value, list):
            return '、'.join(str(item) for item in correct_value if str(item).strip())
        text = str(correct_value).strip()
        return text or None

    @staticmethod
    def _flatten_knowledge_points(raw_items: list[Any] | None) -> list[str]:
        result: list[str] = []
        for item in raw_items or []:
            if isinstance(item, dict):
                text = str(item.get('name') or item.get('label') or item.get('title') or '').strip()
            else:
                text = str(item).strip()
            if text:
                result.append(text)
        return list(dict.fromkeys(result))

    @staticmethod
    def _format_score(score: Decimal | None) -> str | None:
        if score is None:
            return None
        return format(score.normalize() if score != score.to_integral() else score.quantize(Decimal('1')), 'f')

    @staticmethod
    def _pick_placement(question: Question, bank_id: int | None, chapter_id: int | None):
        return question_service._pick_placement(question=question, bank_id=bank_id, chapter_id=chapter_id)

    @staticmethod
    def _normalize_source_text(value: str | None) -> str:
        if not value:
            return ''
        normalized = re.sub(r'\s+', '', value)
        normalized = normalized.replace('（', '(').replace('）', ')')
        return normalized

    @classmethod
    def _extract_source_year(cls, *values: str | None, material_year: int | None = None) -> str | None:
        for value in values:
            normalized = cls._normalize_source_text(value)
            if not normalized:
                continue
            matched = YEAR_PATTERN.search(normalized)
            if matched:
                return matched.group(1)
        if material_year:
            return str(material_year)
        return None

    @classmethod
    def _extract_source_region(cls, *values: str | None) -> str | None:
        normalized_values = [cls._normalize_source_text(value) for value in values if cls._normalize_source_text(value)]
        for value in normalized_values:
            for token in REGION_TOKENS:
                if token in value:
                    return token
        for value in normalized_values:
            for matched in BRACKET_CONTENT_PATTERN.findall(value):
                token = matched.strip()
                if not token or any(noise in token for noise in SOURCE_LABEL_NOISE_TOKENS):
                    continue
                for region_token in REGION_TOKENS:
                    if region_token in token:
                        return region_token
        return None

    @classmethod
    def _extract_exam_type(cls, *values: str | None) -> str | None:
        combined = ' '.join(value for value in values if value).strip()
        if not combined:
            return None
        for pattern, label in EXAM_TYPE_PATTERNS:
            if pattern.search(combined):
                return label
        return None

    @classmethod
    def _build_source_label(
        cls,
        *,
        bank_name: str | None,
        material_year: int | None,
        material_source: str | None,
    ) -> str | None:
        year = cls._extract_source_year(bank_name, material_source, material_year=material_year)
        region = cls._extract_source_region(bank_name, material_source)
        exam_type = cls._extract_exam_type(bank_name, material_source)
        parts: list[str] = []
        for value in (year, region, exam_type):
            if value and value not in parts:
                parts.append(value)
        return ' '.join(parts) or None

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
        if payload.template_key == 'hanyu':
            return ['combined_appendix']
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
            questions.append(
                {
                    'number': index,
                    'expression': expression,
                    'answer_text': answer_text,
                    'section_title': section_title or '基础计算',
                }
            )

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
    def _build_source_text(
        cls, *, question: Question, bank_id: int | None, chapter_id: int | None
    ) -> tuple[str | None, int | None, str | None, int | None, str | None, int | None]:
        placement = cls._pick_placement(question, bank_id=bank_id, chapter_id=chapter_id)
        source_parts: list[str] = []

        resolved_bank_id = placement.bank_id if placement else None
        resolved_bank_name = placement.bank.name if placement and placement.bank else None
        resolved_chapter_id = placement.chapter_id if placement else None
        resolved_chapter_name = placement.chapter.name if placement and placement.chapter else None

        if resolved_bank_name:
            source_parts.append(resolved_bank_name)
        if resolved_chapter_name:
            source_parts.append(resolved_chapter_name)

        first_material = question.materials[0] if question.materials else None
        if first_material:
            if first_material.year:
                source_parts.append(str(first_material.year))
            if first_material.source:
                source_parts.append(first_material.source)

        return (
            ' / '.join(dict.fromkeys(part for part in source_parts if part)) or None,
            resolved_bank_id,
            resolved_bank_name,
            resolved_chapter_id,
            resolved_chapter_name,
            placement.id if placement else None,
        )

    @staticmethod
    def _build_materials(questions: Sequence[Question]) -> list[RenderMaterialPayload]:
        material_map: OrderedDict[int, RenderMaterialPayload] = OrderedDict()
        for question in questions:
            for material in question.materials or []:
                if material.id in material_map:
                    continue
                material_map[material.id] = RenderMaterialPayload(
                    id=material.id,
                    title=material.title,
                    content_text=material.content,
                    source_text=material.source,
                    year=material.year,
                    bank_id=material.bank_id,
                    bank_name=material.bank.name if getattr(material, 'bank', None) else None,
                )
        return list(material_map.values())

    @staticmethod
    def _pick_section_title(*, template_key: str, question: Question, bank_id: int | None, chapter_id: int | None) -> str:
        placement = question_service._pick_placement(question=question, bank_id=bank_id, chapter_id=chapter_id)
        if template_key in {'exam_paper', 'wrong_question', 'practice'} and placement and placement.chapter:
            return placement.chapter.name
        if question.materials:
            first_material = question.materials[0]
            if first_material.title:
                return first_material.title
        return QUESTION_TYPE_LABELS.get(question.type, question.type)

    @classmethod
    def _match_question_filters(
        cls,
        *,
        question: Question,
        bank_id: int | None,
        chapter_id: int | None,
        question_types: set[str],
        difficulties: set[str],
        knowledge_points: set[str],
    ) -> bool:
        if bank_id is not None and not any(item.bank_id == bank_id for item in question.placements or []):
            return False
        if chapter_id is not None and not any(item.chapter_id == chapter_id for item in question.placements or []):
            return False
        if question_types and question.type not in question_types:
            return False
        if difficulties and question.difficulty not in difficulties:
            return False
        if knowledge_points:
            question_kps = {item.lower() for item in cls._flatten_knowledge_points(question.knowledge_point)}
            if not question_kps.intersection(knowledge_points):
                return False
        return True

    @classmethod
    async def _load_questions(cls, *, db: AsyncSession, payload: RenderJobCreate) -> list[Question]:
        filters = payload.filters
        metadata_source_type = payload.metadata.get('source_type') if isinstance(payload.metadata, dict) else None
        if metadata_source_type in {'placement', 'wrong', 'favorite', 'note'}:
            source_type = metadata_source_type
        else:
            source_type = 'wrong' if payload.template_key == 'wrong_question' else 'placement'
        bank_id = filters.get('bank_id') if isinstance(filters.get('bank_id'), int) else None
        chapter_id = filters.get('chapter_id') if isinstance(filters.get('chapter_id'), int) else None
        cat_id = filters.get('cat_id') if isinstance(filters.get('cat_id'), int) else None
        region = str(filters.get('region') or '').strip() or None
        year_start = filters.get('year_start') if isinstance(filters.get('year_start'), int) else None
        year_end = filters.get('year_end') if isinstance(filters.get('year_end'), int) else None
        stem_keyword = str(filters.get('stem_keyword') or '').strip() or None
        option_keyword = str(filters.get('option_keyword') or '').strip() or None
        analysis_keyword = str(filters.get('analysis_keyword') or '').strip() or None
        question_ids = cls._parse_int_list(filters.get('question_ids'))
        question_count = filters.get('question_count') if isinstance(filters.get('question_count'), int) else None
        solution_mode = cls.resolve_solution_mode(payload)
        include_analysis = (
            payload.options.include_answer
            or payload.options.include_analysis
            or solution_mode in {'separate', 'inline', 'appendix'}
            or payload.output_targets.solution_pdf
        )
        question_types = set(cls._parse_text_list(filters.get('question_types')))
        difficulties = set(cls._parse_text_list(filters.get('difficulties')))
        knowledge_points = cls._parse_text_list(filters.get('knowledge_points'))

        collect_result = await question_selector_service.collect_question_ids(
            db=db,
            params=QuestionCollectParam(
                source_type=source_type,
                question_ids=question_ids or None,
                bank_id=bank_id,
                chapter_id=chapter_id,
                cat_id=cat_id,
                region=region,
                year_start=year_start,
                year_end=year_end,
                knowledge_point=knowledge_points or None,
                question_types=list(question_types) or None,
                difficulties=list(difficulties) or None,
                stem_keyword=stem_keyword,
                option_keyword=option_keyword,
                analysis_keyword=analysis_keyword,
                content_status=10,
                is_active=True if source_type == 'placement' else None,
                limit=question_count,
                recent_days=filters.get('wrong_only_recent_days')
                if isinstance(filters.get('wrong_only_recent_days'), int)
                else None,
            ),
            user_id=payload.metadata.get('user_id') if isinstance(payload.metadata.get('user_id'), int) else None,
        )
        return list(
            await question_dao.get_by_ids(
                db,
                collect_result.question_ids,
                include_analysis=include_analysis,
                include_materials=True,
            )
        )

    @classmethod
    async def _build_hanyu_payload(cls, *, db: AsyncSession, payload: RenderJobCreate) -> RenderDocumentPayload:
        filters = payload.filters or {}
        hanyu_ids = cls._parse_int_list(filters.get('hanyu_ids'))
        hanyu_type = str(filters.get('hanyu_type') or 'all').strip().lower()

        from sqlalchemy import select
        from backend.app.gongkao.model import GkHanyu

        stmt = select(GkHanyu)
        if hanyu_ids:
            stmt = stmt.where(GkHanyu.id.in_(hanyu_ids))
            stmt = stmt.order_by(GkHanyu.frequency.desc(), GkHanyu.id.asc())
        else:
            user_id = payload.metadata.get('user_id')
            if user_id is not None:
                from backend.app.gongkao.model.hanyu_notebook import GkHanyuNotebook
                stmt = stmt.join(GkHanyuNotebook, GkHanyuNotebook.hanyu_id == GkHanyu.id)
                stmt = stmt.where(GkHanyuNotebook.user_id == user_id)
                stmt = stmt.order_by(GkHanyuNotebook.id.desc())
            else:
                stmt = stmt.order_by(GkHanyu.frequency.desc(), GkHanyu.id.asc())

            if hanyu_type == 'idiom':
                stmt = stmt.where(GkHanyu.type == '成语')
            elif hanyu_type == 'word':
                stmt = stmt.where(GkHanyu.type != '成语')

        # 限制导出范围数量
        limit_val = filters.get('limit')
        if limit_val is not None:
            try:
                limit_val = int(limit_val)
                if limit_val > 0:
                    stmt = stmt.limit(limit_val)
            except (ValueError, TypeError):
                pass

        result = await db.execute(stmt)
        hanyu_list = result.scalars().all()

        # 加强版：自动获取近义词的详细内容并合并进来
        layout_mode = getattr(payload.options, 'layout_mode', 'standard')
        if layout_mode == 'standard' and hanyu_list:
            synonym_names = set()
            for h in hanyu_list:
                if h.synonyms and isinstance(h.synonyms, list):
                    for syn in h.synonyms:
                        if isinstance(syn, str) and syn.strip():
                            synonym_names.add(syn.strip())
            
            if synonym_names:
                existing_names = {h.name for h in hanyu_list}
                query_syns = list(synonym_names - existing_names)
                if query_syns:
                    syn_stmt = select(GkHanyu).where(GkHanyu.name.in_(query_syns))
                    syn_stmt = syn_stmt.order_by(GkHanyu.frequency.desc(), GkHanyu.id.asc())
                    syn_res = await db.execute(syn_stmt)
                    syn_records = list(syn_res.scalars().all())
                    
                    # 自动创建尚未录入的近义词
                    found_names = {r.name for r in syn_records}
                    missing_names = set(query_syns) - found_names
                    if missing_names:
                        from backend.app.gongkao.schema.hanyu import CreateHanyuParam
                        from backend.app.gongkao.service.hanyu_service import hanyu_service
                        for name in missing_names:
                            create_obj = CreateHanyuParam(name=name, type='成语')
                            new_h = await hanyu_service.create(db, create_obj, created_by=1)
                            syn_records.append(new_h)
                    
                    # 对所有收集到的近义词记录批量补充和静默填充完整信息
                    from backend.app.gongkao.service.hanyu_service import HanyuService
                    completed_syns = []
                    for r in syn_records:
                        filled = await HanyuService.ensure_data_complete(db, r)
                        completed_syns.append(filled)
                        
                    hanyu_list = list(hanyu_list) + completed_syns

        if not hanyu_list:
            raise ValueError('未找到符合条件的汉语词汇，无法生成手册。')

        idioms = []
        words = []
        for h in hanyu_list:
            def_text = None
            if h.definition_info and isinstance(h.definition_info, dict):
                def_text = h.definition_info.get('definition') or ''
            elif isinstance(h.definition_info, str):
                def_text = h.definition_info

            chu_chu_val = None
            if h.chu_chu and isinstance(h.chu_chu, list) and len(h.chu_chu) > 0:
                cc_source = h.chu_chu[0].get('source') or ''
                if cc_source:
                    chu_chu_val = {"text": cc_source}

            detail_means_val = []
            if h.detail_means and isinstance(h.detail_means, list):
                detail_means_val = h.detail_means

            word_payload = RenderWordPayload(
                name=h.name,
                type=h.type or '词语',
                pinyin=h.pinyin or '',
                baobian=h.baobian or '',
                structure=h.structure or '',
                definition_info=def_text or '',
                detail_means=detail_means_val,
                liju=h.liju[:1] if h.liju else [],
                synonyms=h.synonyms or [],
                antonym=h.antonym or [],
                chu_chu=chu_chu_val,
                yin_zheng=h.yin_zheng,
                frequency=h.frequency or 0,
            )

            if h.type == '成语':
                idioms.append(word_payload)
            else:
                words.append(word_payload)

        sections = []
        if idioms:
            sections.append(
                RenderSectionPayload(
                    key='idioms',
                    title='高频成语',
                    words=idioms,
                )
            )
        if words:
            sections.append(
                RenderSectionPayload(
                    key='words',
                    title='高频词语',
                    words=words,
                )
            )

        book_kind = cls.resolve_book_kind(payload)
        content_mode, answer_layout, delivery_mode = cls.resolve_export_config(payload)
        solution_mode = cls.resolve_solution_mode(payload)
        render_variants = cls.resolve_render_variants(payload, solution_mode)

        meta_lines = [f'词汇总数：{len(hanyu_list)} 个']
        if idioms:
            meta_lines.append(f'成语：{len(idioms)} 个')
        if words:
            meta_lines.append(f'词语：{len(words)} 个')

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
                title=payload.title.strip() or '汉语词汇手册',
                subtitle=payload.subtitle,
                meta_lines=meta_lines,
            ),
            options=payload.options,
            paper=RenderPaperPayload(
                question_count=0,
                material_count=0,
                sections=sections,
                materials=[],
            ),
            metadata={
                **payload.metadata,
                'filters': payload.filters,
                'subject': payload.subject or '汉语',
                'template_key': payload.template_key,
                'book_kind': book_kind,
                'content_mode': content_mode,
                'answer_layout': answer_layout,
                'delivery_mode': delivery_mode,
                'solution_mode': solution_mode,
                'render_variants': render_variants,
                'hanyu_ids': [h.id for h in hanyu_list],
                'generated_at': timezone.now().isoformat(),
            },
        )

    @classmethod
    async def build_payload(cls, *, db: AsyncSession, payload: RenderJobCreate) -> RenderDocumentPayload:
        if payload.template_key == 'basic_calculation':
            return cls._build_basic_calculation_payload(payload)
        if payload.template_key == 'hanyu':
            return await cls._build_hanyu_payload(db=db, payload=payload)

        questions = await cls._load_questions(db=db, payload=payload)
        if not questions:
            raise ValueError('未找到符合条件的题目，无法生成题本渲染数据。')

        filters = payload.filters
        book_kind = cls.resolve_book_kind(payload)
        content_mode, answer_layout, delivery_mode = cls.resolve_export_config(payload)
        solution_mode = cls.resolve_solution_mode(payload)
        render_variants = cls.resolve_render_variants(payload, solution_mode)
        bank_id = filters.get('bank_id') if isinstance(filters.get('bank_id'), int) else None
        chapter_id = filters.get('chapter_id') if isinstance(filters.get('chapter_id'), int) else None
        bank = await bank_dao.get(db, bank_id) if bank_id else None
        chapter = await chapter_dao.get(db, chapter_id) if chapter_id else None

        meta_lines: list[str] = [f'题量：{len(questions)}']
        if bank:
            meta_lines.append(f'题库：{bank.name}')
        if chapter:
            meta_lines.append(f'章节：{chapter.name}')

        question_types = cls._parse_text_list(filters.get('question_types'))
        if question_types:
            meta_lines.append(f'题型：{" / ".join(QUESTION_TYPE_LABELS.get(item, item) for item in question_types)}')

        difficulties = cls._parse_text_list(filters.get('difficulties'))
        if difficulties:
            meta_lines.append(f'难度：{" / ".join(DIFFICULTY_LABELS.get(item, item) for item in difficulties)}')

        section_map: OrderedDict[str, RenderSectionPayload] = OrderedDict()
        for index, question in enumerate(questions, start=1):
            analysis: QuestionAnalysis | None = question_service._pick_default_analysis(question.analyses)
            first_material = question.materials[0] if question.materials else None
            source_text, resolved_bank_id, resolved_bank_name, resolved_chapter_id, resolved_chapter_name, placement_id = (
                cls._build_source_text(question=question, bank_id=bank_id, chapter_id=chapter_id)
            )
            item = RenderQuestionPayload(
                number=index,
                question_id=question.id,
                placement_id=placement_id,
                type=question.type,
                type_label=QUESTION_TYPE_LABELS.get(question.type, question.type),
                stem_text=question.stem,
                options=[
                    RenderQuestionOptionPayload(key=option['option_code'], content_text=option['content'])
                    for option in sorted(
                        [row for row in question.options or [] if row.get('is_active', True)],
                        key=lambda row: (row.get('sort_order', 0), row['option_code']),
                    )
                ],
                answer_text=cls._format_answer_text(analysis.answer_data if analysis else None),
                answer_raw=analysis.answer_data if analysis else None,
                analysis_text=analysis.content if analysis else None,
                source_text=source_text,
                source_label=cls._build_source_label(
                    bank_name=resolved_bank_name,
                    material_year=first_material.year if first_material else None,
                    material_source=first_material.source if first_material else None,
                ),
                difficulty=question.difficulty,
                score=cls._format_score(question.default_score),
                knowledge_points=cls._flatten_knowledge_points(question.knowledge_point),
                bank_id=resolved_bank_id,
                bank_name=resolved_bank_name,
                chapter_id=resolved_chapter_id,
                chapter_name=resolved_chapter_name,
                material_ids=[material.id for material in question.materials or []],
                tags=[QUESTION_TYPE_LABELS.get(question.type, question.type)],
            )
            section_title = cls._pick_section_title(
                template_key=payload.template_key,
                question=question,
                bank_id=bank_id,
                chapter_id=chapter_id,
            )
            if section_title not in section_map:
                section_map[section_title] = RenderSectionPayload(key=section_title, title=section_title, questions=[])
            section_map[section_title].questions.append(item)

        materials = cls._build_materials(questions)
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
                title=payload.title.strip() or (bank.name if bank else payload.template_key),
                subtitle=payload.subtitle,
                meta_lines=meta_lines,
            ),
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
                'subject': payload.subject,
                'template_key': payload.template_key,
                'book_kind': book_kind,
                'content_mode': content_mode,
                'answer_layout': answer_layout,
                'delivery_mode': delivery_mode,
                'solution_mode': solution_mode,
                'render_variants': render_variants,
                'bank_id': bank_id,
                'bank_name': bank.name if bank else None,
                'chapter_id': chapter_id,
                'chapter_name': chapter.name if chapter else None,
                'question_ids': [item.id for item in questions],
                'generated_at': timezone.now().isoformat(),
                'window_recent_days': filters.get('wrong_only_recent_days'),
            },
        )


render_payload_service = RenderPayloadService()
