import io
import logging
import re

from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from backend.app.question_bank_v2.crud.crud_bank import bank_category_dao, bank_dao, bank_revision_dao
from backend.app.question_bank_v2.crud.crud_catalog import collection_bank_dao, collection_dao
from backend.app.question_bank_v2.crud.crud_knowledge import knowledge_point_dao, knowledge_system_dao
from backend.app.question_bank_v2.crud.crud_question import question_dao
from backend.app.question_bank_v2.schema.bank import CreateBankRevisionParam
from backend.app.question_bank_v2.schema.import_task import BankImportResult, ImportRowResult
from backend.app.question_bank_v2.service.bank_service import bank_service
from backend.common.exception import errors

log = logging.getLogger(__name__)
MAX_IMPORT_ROWS = 5_000

TYPE_MAPPING: dict[str, str] = {
    '单': 'single_choice',
    '单选': 'single_choice',
    '单选题': 'single_choice',
    '多': 'multiple_choice',
    '多选': 'multiple_choice',
    '多选题': 'multiple_choice',
    '判断': 'true_false',
    '判断题': 'true_false',
    '填空': 'fill_blank',
    '填空题': 'fill_blank',
    '简答': 'short_answer',
    '简答题': 'short_answer',
    'single_choice': 'single_choice',
    'multiple_choice': 'multiple_choice',
    'true_false': 'true_false',
    'fill_blank': 'fill_blank',
    'short_answer': 'short_answer',
}

COLUMNS = [
    'question_type', 'stem', 'answer', 'explanation_default', 'explanation_official', 'explanation_expert',
    'option_A', 'option_B', 'option_C', 'option_D', 'option_E',
    'score',
    'section_l1', 'section_l2', 'section_l3',
    'knowledge_point', 'item_key',
]


class ImportTaskService:

    @staticmethod
    async def _parse_excel(content: bytes) -> list[dict[str, Any]]:
        import pandas as pd

        excel_bytes = io.BytesIO(content)
        try:
            df = await run_in_threadpool(pd.read_excel, excel_bytes, sheet_name=0, dtype=str)
        except Exception as e:
            raise errors.RequestError(msg=f'读取 Excel 失败: {e}')

        df = df.where(df.notna(), None)
        rows: list[dict[str, Any]] = []
        for _, pandas_row in df.iterrows():
            row: dict[str, Any] = {}
            for col in df.columns:
                col_clean = str(col).strip().replace(' ', '_').replace('-', '_')
                val = pandas_row[col]
                if pd.notna(val) and val is not None:
                    row[col_clean] = str(val).strip()
            if not row.get('stem'):
                continue
            rows.append(row)
            if len(rows) > MAX_IMPORT_ROWS:
                raise errors.RequestError(msg=f'单次最多导入 {MAX_IMPORT_ROWS} 道题')

        if not rows:
            raise errors.RequestError(msg='Excel 中没有有效题目数据（至少需要 stem 列）')
        return rows

    @staticmethod
    async def build_import_template() -> bytes:
        from openpyxl import Workbook

        def _build() -> bytes:
            wb = Workbook()
            ws = wb.active
            ws.title = '题目'
            ws.append(COLUMNS)
            ws.append([
                'single_choice', '地球上最大的海洋是什么？',
                'A', '太平洋是地球上面积最大的海洋。', None, None,
                '大西洋', '印度洋', '北冰洋', None, None,
                '1',
                '地理', '海洋', None,
                None, None,
            ])
            buf = io.BytesIO()
            wb.save(buf)
            return buf.getvalue()

        return await run_in_threadpool(_build)

    @staticmethod
    def _resolve_question_type(raw: str | None) -> str:
        if not raw:
            raise ValueError('题型不能为空')
        raw = raw.strip()
        mapped = TYPE_MAPPING.get(raw)
        if not mapped:
            raise ValueError(f'不支持的题型: {raw}')
        return mapped

    @staticmethod
    def _parse_answer(answer_str: str | None, question_type: str) -> dict[str, Any]:
        if not answer_str:
            raise ValueError('答案不能为空')
        answer_str = answer_str.strip()
        if question_type == 'single_choice':
            codes = re.findall(r'[A-Za-z]', answer_str.upper())
            if not codes:
                raise ValueError(f'单选题答案必须是选项编码: {answer_str}')
            return {'correct': codes[0]}
        if question_type == 'multiple_choice':
            codes = re.findall(r'[A-Za-z]', answer_str.upper())
            if not codes:
                raise ValueError(f'多选题答案必须是选项编码列表: {answer_str}')
            return {'correct': sorted(set(codes))}
        if question_type == 'true_false':
            normalized = answer_str.lower().strip()
            if normalized in ('对', '正确', 'true', 't', '1', '是', 'right', 'yes', 'y'):
                return {'correct': True}
            if normalized in ('错', '错误', 'false', 'f', '0', '否', 'wrong', 'no', 'n'):
                return {'correct': False}
            raise ValueError(f'判断题答案必须是对/错: {answer_str}')
        if question_type in ('fill_blank', 'short_answer'):
            parts = [p.strip() for p in answer_str.replace('，', ',').split(',') if p.strip()]
            return {'correct': parts or [answer_str]}
        return {'correct': answer_str}

    @staticmethod
    def _parse_options(row: dict[str, Any]) -> list[dict[str, Any]]:
        options: list[dict[str, Any]] = []
        for letter in 'ABCDE':
            val = row.get(f'option_{letter}')
            if val is not None and str(val).strip():
                options.append({
                    'option_code': letter,
                    'content': str(val).strip(),
                    'sort_order': ord(letter) - ord('A'),
                })
        return options

    @staticmethod
    def _parse_explanations(row: dict[str, Any]) -> list[dict[str, Any]]:
        """解析 explanation_XXX 列，返回 [{explanation_type, content}]"""
        result: list[dict[str, Any]] = []
        for key, val in row.items():
            key_clean = key.strip().replace(' ', '_').replace('-', '_')
            if key_clean.startswith('explanation_'):
                exp_type = key_clean[len('explanation_'):]
                if exp_type and val:
                    result.append({'explanation_type': exp_type, 'content': str(val).strip()})
        if not result:
            result.append({'explanation_type': 'default', 'content': '暂无解析'})
        return result

    @classmethod
    def _validate_row(cls, row: dict[str, Any], row_number: int) -> dict[str, Any] | str:
        """验证单行数据，返回规范化后的 dict 或错误信息"""
        try:
            question_type = cls._resolve_question_type(row.get('question_type'))
            options = cls._parse_options(row)
            answer_data = cls._parse_answer(row.get('answer'), question_type)
            default_score = Decimal(str(row.get('score') or '1'))
            stem = row['stem']
            item_key = row.get('item_key') or f'q{row_number - 2:04d}'
            explanations = cls._parse_explanations(row)

            if question_type in ('single_choice', 'multiple_choice') and len(options) < 2:
                return f'选择题至少需要两个选项（第 {row_number} 行）'
            if answer_data.get('correct') is not None and question_type != 'composite':
                pass  # all good

            return {
                'question_type': question_type,
                'stem': stem,
                'options': options,
                'answer_data': answer_data,
                'default_score': default_score,
                'item_key': item_key,
                'explanations': explanations,
                'section_l1': row.get('section_l1'),
                'section_l2': row.get('section_l2'),
                'section_l3': row.get('section_l3'),
                'knowledge_point': row.get('knowledge_point'),
            }
        except ValueError as e:
            return str(e)

    @classmethod
    async def import_bank(  # noqa: C901
        cls,
        *,
        db: AsyncSession,
        user_id: int,
        file_content: bytes,
        bank_name: str,
        bank_code: str | None = None,
        bank_kind: str = 'practice',
        collection_id: int | None = None,
        category_ids: list[int] | None = None,
        primary_category_id: int | None = None,
        description: str | None = None,
        knowledge_system_id: int | None = None,
    ) -> BankImportResult:
        import random
        import time

        from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankSection
        from backend.app.question_bank_v2.model.catalog import QbCollectionBank
        from backend.app.question_bank_v2.model.knowledge import QbQuestionKnowledgePoint
        from backend.app.question_bank_v2.model.question import QbQuestionAnswer, QbQuestionExplanation

        # 1. 解析文件
        raw_rows = await cls._parse_excel(file_content)
        total = len(raw_rows)

        # 2. 两阶段：先验证全部行
        validated_rows: list[dict[str, Any]] = []
        validation_results: list[ImportRowResult] = []
        for idx, row in enumerate(raw_rows, start=2):
            result = cls._validate_row(row, idx)
            if isinstance(result, str):
                validation_results.append(ImportRowResult(
                    row_number=idx, success=False, error_message=result,
                ))
            else:
                validated_rows.append(result)

        if not validated_rows:
            return BankImportResult(
                bank_id=0, bank_revision_id=0,
                total=total, success_count=0, fail_count=total,
                details=validation_results,
            )

        # Resolve knowledge-point labels before creating any database objects.
        knowledge_labels = {row['knowledge_point'] for row in validated_rows if row.get('knowledge_point')}
        knowledge_ids: dict[str, int] = {}
        if knowledge_labels:
            if knowledge_system_id is None:
                raise errors.RequestError(msg='Excel 含知识点列，必须指定 knowledge_system_id 以明确挂载到哪套知识体系')
            system = await knowledge_system_dao.get(db, knowledge_system_id)
            if system is None or system.status != 'active':
                raise errors.NotFoundError(msg='知识体系不存在或未启用')
            points = await knowledge_point_dao.get_all(db, knowledge_system_id)
            by_name: dict[str, list[int]] = {}
            for point in points:
                by_name.setdefault(point.name.strip(), []).append(point.id)
            for label in knowledge_labels:
                matches = by_name.get(label.strip(), [])
                if len(matches) != 1:
                    raise errors.RequestError(msg=f'知识点名称无法唯一匹配: {label}')
                knowledge_ids[label] = matches[0]

        # 3. 生成题库编码
        if not bank_code:
            bank_code = f'imp_{int(time.time())}'
        if await bank_dao.get_by_code(db, bank_code):
            bank_code = f'imp_{int(time.time())}_{random.randint(100, 999)}'

        # 4. 校验合集
        if collection_id is not None:
            collection = await collection_dao.get(db, collection_id)
            if collection is None or collection.status != 'active':
                raise errors.NotFoundError(msg='目标合集不存在或未启用')

        # 5. 创建题库 + 草稿版本
        bank = await bank_dao.create_bank(
            db, code=bank_code, owner_id=None,
            visibility='public', status='active',
            created_by=user_id,
        )
        revision = await bank_revision_dao.create(
            db, bank_id=bank.id, revision_no=1,
            created_by=user_id,
            obj=CreateBankRevisionParam(
                name=bank_name,
                bank_kind=bank_kind,
                description=description,
            ),
        )
        await db.flush()

        # 6. 收集章节路径 → 创建章节
        paths: set[tuple[str | None, str | None, str | None]] = set()
        paths.update((vr['section_l1'], vr['section_l2'], vr['section_l3']) for vr in validated_rows)

        section_cache: dict[str, int] = {}

        async def _get_or_create_sec(key: str, name: str, parent_id: int | None, depth: int) -> int:
            if key in section_cache:
                return section_cache[key]
            sec = QbBankSection(
                bank_revision_id=revision.id,
                code=key,
                name=name,
                parent_id=parent_id,
                depth=depth,
                sort_order=0,
            )
            db.add(sec)
            await db.flush()
            section_cache[key] = sec.id
            return sec.id

        for l1, l2, l3 in sorted(paths):
            if l1:
                p1 = await _get_or_create_sec(f'l1/{l1}', l1, None, 0)
                if l2:
                    p2 = await _get_or_create_sec(f'l2/{l2}', l2, p1, 1)
                    if l3:
                        await _get_or_create_sec(f'l3/{l3}', l3, p2, 2)

        await db.flush()

        # section_path → section_id 映射
        section_map: dict[str, int | None] = {}
        for l1, l2, l3 in paths:
            parts = [p for p in [l1, l2, l3] if p]
            key = '/'.join(parts) if parts else ''
            if not key:
                section_map[''] = None
            elif l3:
                section_map[key] = section_cache.get(f'l3/{l3}')
            elif l2:
                section_map[key] = section_cache.get(f'l2/{l2}')
            elif l1:
                section_map[key] = section_cache.get(f'l1/{l1}')

        # 7. 导入有效行
        success_count = 0
        import_results: list[ImportRowResult] = []
        for idx, vr in enumerate(validated_rows):
            row_number = idx + 2  # row numbers start from 2 in original file
            try:
                question_code = f'{bank_code}_{vr["item_key"]}'
                if await question_dao.get_by_code(db, question_code):
                    question_code = f'{bank_code}_{vr["item_key"]}_{random.randint(100, 999)}'

                parts = [p for p in [vr['section_l1'], vr['section_l2'], vr['section_l3']] if p]
                section_path = '/'.join(parts) if parts else ''
                section_id = section_map.get(section_path)

                question = await question_dao.create(
                    db, code=question_code, owner_id=None,
                    visibility='public', origin_type='imported',
                    status='active', stem=vr['stem'],
                    content_format='html', question_type=vr['question_type'],
                    option_data=vr['options'], default_score=vr['default_score'],
                    difficulty=None, content_hash=None,
                    created_by=user_id,
                )

                db.add(QbQuestionAnswer(
                    question_id=question.id,
                    answer_data=vr['answer_data'],
                    grading_method='exact',
                    grading_config={},
                    created_by=user_id,
                ))

                is_first = True
                for exp in vr['explanations']:
                    db.add(QbQuestionExplanation(
                        question_id=question.id,
                        content=exp['content'],
                        explanation_type=exp['explanation_type'],
                        is_default=is_first,
                        status='published',
                        created_by=user_id,
                    ))
                    is_first = False

                if vr['knowledge_point']:
                    db.add(QbQuestionKnowledgePoint(
                        question_id=question.id,
                        knowledge_point_id=knowledge_ids[vr['knowledge_point']],
                        created_by=user_id,
                    ))

                db.add(QbBankItem(
                    bank_revision_id=revision.id,
                    item_key=vr['item_key'],
                    question_id=question.id,
                    section_id=section_id,
                    score=vr['default_score'],
                    sort_order=idx,
                    is_required=True,
                    is_active=True,
                    settings={},
                    created_by=user_id,
                ))

                await db.flush()
                success_count += 1
                import_results.append(ImportRowResult(
                    row_number=row_number, success=True, question_id=question.id,
                ))

            except Exception as e:
                log.warning(f'导入第 {row_number} 行失败: {e}')
                raise errors.RequestError(msg=f'导入第 {row_number} 行失败: {e}') from e

        # 8. 发布版本
        if success_count > 0:
            await bank_service.publish_revision(
                db=db, bank_id=bank.id,
                revision_id=revision.id,
                published_by=user_id,
            )

        # 9. 挂载合集
        if collection_id is not None and success_count > 0:
            existing = await collection_bank_dao.get_by_bank(
                db, collection_id=collection_id, bank_id=bank.id,
            )
            if existing is None:
                db.add(QbCollectionBank(
                    collection_id=collection_id,
                    bank_id=bank.id,
                    bank_revision_id=None,
                    follow_latest=True,
                    display_name=bank_name,
                    sort_order=0,
                    is_active=True,
                    created_by=user_id,
                ))
                await db.flush()

        # 10. 设置分类
        if category_ids and success_count > 0:
            await bank_category_dao.replace(
                db, bank_id=bank.id,
                category_ids=category_ids,
                primary_category_id=primary_category_id,
                user_id=user_id,
            )
            await db.flush()

        await db.commit()

        all_results = validation_results + import_results
        return BankImportResult(
            bank_id=bank.id,
            bank_revision_id=revision.id,
            total=total,
            success_count=success_count,
            fail_count=total - success_count,
            details=all_results,
        )


import_task_service: ImportTaskService = ImportTaskService()
