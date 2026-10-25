from copy import deepcopy
from datetime import datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.model.practice_log import GongkaoPracticeLog
from backend.app.gongkao.schema.practice_log import ImportPracticeReportParam
from backend.app.question_bank_v2.crud.crud_external_practice import external_practice_dao
from backend.app.question_bank_v2.crud.crud_material import question_material_dao
from backend.app.question_bank_v2.crud.crud_practice import practice_session_dao
from backend.app.question_bank_v2.crud.crud_review import review_reference_dao
from backend.app.question_bank_v2.model.practice import QbPracticeSession
from backend.app.question_bank_v2.schema.external_practice import (
    GetImportedPracticeDetail,
    GetImportedPracticeQuestion,
    ImportPracticeDetailResult,
    ImportPracticeQuestionParam,
)
from backend.app.question_bank_v2.schema.practice import (
    GetPracticeSessionDetail,
    GetPracticeSessionReport,
    GetPracticeSessionSolutionItem,
)
from backend.app.question_bank_v2.utils.external_practice import EXTERNAL_PRACTICE_ORIGIN, imported_session_key
from backend.common.exception import errors
from backend.utils.timezone import timezone


class ExternalPracticeImportService:
    """外部历史归档。调用方持有报告行锁和事务，不走在线判题、奖励或复习排期。"""

    @staticmethod
    def _date_anchor(log: GongkaoPracticeLog) -> datetime:
        # 现有会话开始时间为非空，零点仅作日期索引。查询对外返回 date 精度、未知开始时间。
        return datetime.combine(log.practiced_at, time.min, tzinfo=timezone.tz_info)

    @staticmethod
    def _merge_question(previous: dict[str, Any], incoming: ImportPracticeQuestionParam) -> dict[str, Any]:
        merged = deepcopy(previous)
        current = incoming.model_dump(mode='json')
        immutable = (
            'source_question_key',
            'position',
            'stem',
            'content_format',
            'question_type',
            'options',
            'status',
            'response_data',
        )
        for field in immutable:
            if previous[field] != current[field]:
                raise errors.ConflictError(msg=f'第 {incoming.position} 题的 {field} 与原记录冲突，不能覆盖历史作答')
        old_path, new_path = previous['module_path'], current['module_path']
        if old_path[: len(new_path)] != new_path and new_path[: len(old_path)] != old_path:
            raise errors.ConflictError(msg=f'第 {incoming.position} 题的模块路径与原记录冲突')
        if len(new_path) > len(old_path):
            merged['module_path'] = new_path
        for field in ('answer', 'duration_seconds', 'score', 'max_score'):
            if current[field] is None:
                continue
            if previous[field] is not None and previous[field] != current[field]:
                raise errors.ConflictError(msg=f'第 {incoming.position} 题的 {field} 已存在且不同，不能自动替换')
            merged[field] = current[field]
        for field, key_fields in (
            ('explanations', ('explanation_type',)),
            ('materials', ('link_key', 'role')),
            ('assets', ('link_key',)),
        ):
            merged[field] = ExternalPracticeImportService._merge_parts(
                merged[field],
                current[field],
                key_fields,
                incoming.position,
                field,
            )
        return ImportPracticeQuestionParam.model_validate(merged).model_dump(mode='json')

    @staticmethod
    def _merge_parts(
        previous: list[dict[str, Any]],
        incoming: list[dict[str, Any]],
        keys: tuple[str, ...],
        position: int,
        field: str,
    ) -> list[dict[str, Any]]:
        values = {tuple(value[key] for key in keys): value for value in previous}
        for value in incoming:
            key = tuple(value[name] for name in keys)
            if key in values and values[key] != value:
                raise errors.ConflictError(msg=f'第 {position} 题的 {field} 明细已存在且不同')
            values[key] = value
        return list(values.values())

    @staticmethod
    def _validate_totals(questions: list[dict[str, Any]], summary: dict[str, Any]) -> None:
        """仅对互斥的一级模块校验总量，不累加可能重叠的细分知识点。"""
        scopes = [(questions, summary)]
        scopes.extend(
            ([q for q in questions if q['module_path'][0] == module['module_name']], module)
            for module in summary['modules']
        )
        for rows, expected in scopes:
            total = expected['total_questions']
            correct = sum(row['status'] == 'correct' for row in rows)
            unanswered = sum(row['status'] == 'unanswered' for row in rows)
            wrong = sum(row['status'] == 'wrong' for row in rows)
            expected_unanswered = expected.get('unanswered_count')
            if (
                len(rows) > total
                or correct > expected['correct_count']
                or wrong > total - expected['correct_count'] - (expected_unanswered or 0)
                or (expected_unanswered is not None and unanswered > expected_unanswered)
            ):
                raise errors.RequestError(msg='逐题作答数量与报告或一级模块统计冲突')
            if len(rows) == total and (
                correct != expected['correct_count']
                or (expected_unanswered is not None and unanswered != expected_unanswered)
            ):
                raise errors.RequestError(msg='完整逐题明细的正确数或未答数与原报告不一致')
            known_times = [row['duration_seconds'] for row in rows if row['duration_seconds'] is not None]
            duration = expected.get('duration_seconds')
            if duration is not None and (
                sum(known_times) > duration or (len(known_times) == total and sum(known_times) != duration)
            ):
                raise errors.RequestError(msg='逐题用时与报告或一级模块用时不一致')

    @staticmethod
    def _summary(obj: ImportPracticeReportParam, session: QbPracticeSession | None) -> dict[str, Any]:
        incoming = obj.model_dump(mode='json', exclude={'questions'})
        if session is None:
            return incoming
        previous = deepcopy(session.source_snapshot['summary'])
        for field in (
            'total_questions',
            'correct_count',
            'unanswered_count',
            'duration_seconds',
            'score',
            'full_score',
        ):
            if incoming[field] is None:
                continue
            if previous.get(field) is not None and previous[field] != incoming[field]:
                raise errors.ConflictError(msg=f'原报告的 {field} 与已归档数据不一致')
            previous[field] = incoming[field]
        # 重读时允许新增题型层级；一级模块统计须相同，防止部分上传改变分组含义。
        original_roots = {
            m['module_name']: (m['total_questions'], m['correct_count'], m['duration_seconds'])
            for m in previous['modules']
        }
        incoming_roots = {
            m['module_name']: (m['total_questions'], m['correct_count'], m['duration_seconds'])
            for m in incoming['modules']
        }
        if original_roots != incoming_roots or previous['subject_name'] != incoming['subject_name']:
            raise errors.ConflictError(msg='报告科目或一级模块统计与已归档数据不一致')
        return previous

    @staticmethod
    def _detail_status(questions: list[dict[str, Any]], total: int) -> str:
        return (
            'complete'
            if len(questions) == total and all(q['answer'] and q['explanations'] for q in questions)
            else 'partial'
        )

    @staticmethod
    async def import_questions(
        *, db: AsyncSession, log: GongkaoPracticeLog, obj: ImportPracticeReportParam
    ) -> ImportPracticeDetailResult:
        session = await external_practice_dao.get_session(db, user_id=log.user_id, log_id=log.id, for_update=True)
        summary = ExternalPracticeImportService._summary(obj, session)
        stored = await external_practice_dao.get_items(db, session_id=session.id) if session else []
        by_key = {item.display_config['external_practice']['source_question_key']: item for item in stored}
        by_position = {
            item.position + 1: item.display_config['external_practice']['source_question_key'] for item in stored
        }
        snapshots = {key: deepcopy(item.display_config['external_practice']) for key, item in by_key.items()}
        pending: list[tuple[ImportPracticeQuestionParam, bool]] = []
        for incoming in obj.questions or []:
            if incoming.position in by_position and by_position[incoming.position] != incoming.source_question_key:
                raise errors.ConflictError(msg=f'第 {incoming.position} 题已关联其他来源题目')
            old = snapshots.get(incoming.source_question_key)
            merged = (
                ExternalPracticeImportService._merge_question(old, incoming)
                if old
                else incoming.model_dump(mode='json')
            )
            snapshots[incoming.source_question_key] = merged
            if merged != old:
                pending.append((ImportPracticeQuestionParam.model_validate(merged), old is None))
        ExternalPracticeImportService._validate_totals(list(snapshots.values()), summary)
        asset_ids = {asset.asset_id for item, _new in pending for asset in item.assets}
        valid = await review_reference_dao.get_valid_asset_ids(db, user_id=log.user_id, asset_ids=list(asset_ids))
        if missing := asset_ids - valid:
            raise errors.NotFoundError(msg=f'题目资源不存在、未就绪或不可访问: {sorted(missing)}')
        anchor = ExternalPracticeImportService._date_anchor(log)
        if session is None:
            session = await practice_session_dao.create(
                db,
                {
                    'session_key': imported_session_key(log.user_id, log.source_platform, log.source_key),
                    'user_id': log.user_id,
                    'bank_revision_id': None,
                    'source_type': 'custom',
                    'source_ref': f'external-practice:{log.id}',
                    'title_snapshot': log.material_title,
                    'mode': 'exam' if obj.material_type == 'exam' else 'practice',
                    'status': 'graded',
                    'started_time': anchor,
                    'submitted_time': None,
                    'delivery_config': {'read_only': True},
                    'source_snapshot': {
                        'origin': EXTERNAL_PRACTICE_ORIGIN,
                        'practice_log_id': log.id,
                        'platform': obj.source_platform,
                        'source_key': obj.source_key,
                        'source_url': obj.source_url,
                        'time_precision': 'date',
                        'practiced_at': log.practiced_at.isoformat(),
                        'summary': summary,
                    },
                },
            )
        added = supplemented = 0
        # 同用户跨报告导入同题时按稳定键顺序加锁，避免交叉顺序导致死锁。
        for data, new in sorted(pending, key=lambda pair: pair[0].source_question_key):
            if new:
                question = await external_practice_dao.ensure_question(
                    db,
                    user_id=log.user_id,
                    platform=obj.source_platform,
                    item=data,
                )
                item = await external_practice_dao.create_item(db, session=session, question_id=question.id, data=data)
                by_key[data.source_question_key] = item
                added += 1
            else:
                item = by_key[data.source_question_key]
                item.display_config = {**item.display_config, 'external_practice': data.model_dump(mode='json')}
                item.max_score = data.max_score if data.max_score is not None else Decimal(0)
                supplemented += 1
                await external_practice_dao.ensure_question(
                    db, user_id=log.user_id, platform=obj.source_platform, item=data
                )
            await external_practice_dao.supplement_content(
                db, user_id=log.user_id, question_id=item.question_id, item=data
            )
            await external_practice_dao.save_response(db, session=session, item=item, data=data, occurred_at=anchor)
        rows = list(snapshots.values())
        state = ExternalPracticeImportService._detail_status(rows, obj.total_questions)
        session.total_items = len(rows)
        session.answered_items = sum(row['status'] != 'unanswered' for row in rows)
        session.correct_items = sum(row['status'] == 'correct' for row in rows)
        session.score = Decimal(str(summary['score'])) if summary['score'] is not None else Decimal(0)
        session.source_snapshot = {
            **session.source_snapshot,
            'summary': summary,
            'detail_status': state,
            'imported_questions': len(rows),
        }
        await db.flush()
        return ImportPracticeDetailResult(
            session_key=session.session_key,
            imported_questions=len(rows),
            detail_status=state,
            added_questions=added,
            supplemented_questions=supplemented,
        )

    @staticmethod
    async def get_items(*, db: AsyncSession, session: QbPracticeSession) -> list[GetImportedPracticeQuestion]:
        items = await external_practice_dao.get_items(db, session_id=session.id)
        attempt_ids = await external_practice_dao.get_attempt_ids(db, session_id=session.id)
        return [
            GetImportedPracticeQuestion(
                **item.display_config['external_practice'],
                session_item_id=item.id,
                question_id=item.question_id,
                attempt_id=attempt_ids.get(item.id),
                missing_content=[
                    key for key in ('answer', 'explanations') if not item.display_config['external_practice'].get(key)
                ],
            )
            for item in items
        ]

    @staticmethod
    async def get_detail(*, db: AsyncSession, log: GongkaoPracticeLog) -> GetImportedPracticeDetail:
        session = await external_practice_dao.get_session(db, user_id=log.user_id, log_id=log.id)
        if session is None:
            return GetImportedPracticeDetail(
                practice_log_id=log.id,
                total_questions=log.total_questions,
                practiced_at=log.practiced_at,
            )
        items = await ExternalPracticeImportService.get_items(db=db, session=session)
        return GetImportedPracticeDetail(
            practice_log_id=log.id,
            session_key=session.session_key,
            detail_status=session.source_snapshot['detail_status'],
            imported_questions=len(items),
            total_questions=session.source_snapshot['summary']['total_questions'],
            practiced_at=log.practiced_at,
            source_summary=session.source_snapshot['summary'],
            items=items,
        )

    @staticmethod
    async def session_detail(*, db: AsyncSession, session: dict[str, Any]) -> GetPracticeSessionDetail:
        """题目读取复用原接口，但导入会话始终读取当次快照。"""
        rows = await external_practice_dao.get_items(db, session_id=session['id'])
        materials = await question_material_dao.get_all_by_questions(db, [row.question_id for row in rows])
        catalog: dict[int, dict[str, Any]] = {}
        items = []
        for row in rows:
            data = row.display_config['external_practice']
            references = []
            for material in materials:
                if material['question_id'] != row.question_id or not any(
                    material['title'] == original['title']
                    and material['content'] == original['content']
                    and material['content_format'] == original['content_format']
                    and material['role'] == original['role']
                    for original in data['materials']
                ):
                    continue
                references.append({
                    key: material[key]
                    for key in (
                        'id',
                        'question_id',
                        'material_id',
                        'material_revision_id',
                        'role',
                        'sort_order',
                        'display_config',
                    )
                })
                catalog[material['material_revision_id']] = {
                    key: material[key]
                    for key in (
                        'material_id',
                        'material_revision_id',
                        'title',
                        'content',
                        'content_format',
                        'structured_data',
                        'source_name',
                        'source_url',
                        'content_hash',
                    )
                }
            items.append({
                'id': row.id,
                'position': row.position,
                'question_id': row.question_id,
                'section_name': data['module_path'][0],
                'max_score': data['max_score'],
                'display_config': {key: data[key] for key in ('source_question_key', 'module_path', 'assets')},
                'question_type': data['question_type'],
                'stem': data['stem'],
                'content_format': data['content_format'],
                'option_data': data['options'],
                'materials': references,
                'response_data': data['response_data'],
                'response_status': 'not_started' if data['status'] == 'unanswered' else 'graded',
                'is_correct': None if data['status'] == 'unanswered' else data['status'] == 'correct',
                'score': data['score'],
                'is_flagged': False,
                'duration_ms': data['duration_seconds'] * 1000 if data['duration_seconds'] is not None else None,
                'save_version': 0,
            })
        values = {
            **session,
            'started_time': None,
            'submitted_time': None,
            'practiced_at': session['source_snapshot']['practiced_at'],
            'score': session['source_snapshot']['summary']['score'],
        }
        return GetPracticeSessionDetail(**values, items=items, materials=list(catalog.values()))

    @staticmethod
    async def session_report(*, db: AsyncSession, session: dict[str, Any]) -> GetPracticeSessionReport:
        rows = await external_practice_dao.get_items(db, session_id=session['id'])
        summary = session['source_snapshot']['summary']
        if len(rows) != summary['total_questions']:
            raise errors.RequestError(msg='逐题作答尚未导入齐全，请先查看导入详情中的缺失状态')
        items = [
            {
                'session_item_id': row.id,
                'position': row.position,
                'question_id': row.question_id,
                'section_name': row.display_config['external_practice']['module_path'][0],
                'status': row.display_config['external_practice']['status'],
                'duration_ms': row.display_config['external_practice']['duration_seconds'] * 1000
                if row.display_config['external_practice']['duration_seconds'] is not None
                else None,
                'score': row.display_config['external_practice']['score'],
                'max_score': row.display_config['external_practice']['max_score'],
            }
            for row in rows
        ]
        correct = sum(item['status'] == 'correct' for item in items)
        wrong = sum(item['status'] == 'wrong' for item in items)
        return GetPracticeSessionReport(
            session_id=session['id'],
            session_key=session['session_key'],
            mode=session['mode'],
            source_type=session['source_type'],
            title_snapshot=session['title_snapshot'],
            status=session['status'],
            total_items=len(items),
            answered_items=correct + wrong,
            graded_items=correct + wrong,
            correct_items=correct,
            wrong_items=wrong,
            pending_items=0,
            unanswered_items=len(items) - correct - wrong,
            accuracy_rate=Decimal(correct) / Decimal(len(items)),
            accuracy_basis='all_questions',
            score=summary['score'],
            total_score=summary['full_score'],
            total_duration_ms=summary['duration_seconds'] * 1000 if summary['duration_seconds'] is not None else None,
            started_time=None,
            submitted_time=None,
            practiced_at=session['source_snapshot']['practiced_at'],
            source_snapshot=session['source_snapshot'],
            items=items,
            wrong_question_ids=[item['question_id'] for item in items if item['status'] == 'wrong'],
        )

    @staticmethod
    def solution_data(item: dict[str, Any]) -> dict[str, Any]:
        answer = item['answer']
        return {
            'answer_data': answer['answer_data'] if answer else None,
            'grading_method': answer['grading_method'] if answer else None,
            'grading_config': answer['grading_config'] if answer else {},
            'explanations': item['explanations'],
        }

    @staticmethod
    async def session_solutions(
        *, db: AsyncSession, session: QbPracticeSession
    ) -> list[GetPracticeSessionSolutionItem]:
        rows = await external_practice_dao.get_items(db, session_id=session.id)
        result = []
        for row in rows:
            data = row.display_config['external_practice']
            result.append(
                GetPracticeSessionSolutionItem(
                    session_item_id=row.id,
                    position=row.position,
                    question_id=row.question_id,
                    response_data=data['response_data'],
                    is_correct=None if data['status'] == 'unanswered' else data['status'] == 'correct',
                    score=data['score'],
                    max_score=data['max_score'],
                    grading_status='not_requested' if data['status'] == 'unanswered' else 'graded',
                    **ExternalPracticeImportService.solution_data(data),
                )
            )
        return result

    @staticmethod
    async def remove(*, db: AsyncSession, log: GongkaoPracticeLog) -> None:
        session = await external_practice_dao.get_session(db, user_id=log.user_id, log_id=log.id, for_update=True)
        if session is not None:
            await external_practice_dao.remove_session(db, session=session)

    @staticmethod
    async def sync_log(*, db: AsyncSession, log: GongkaoPracticeLog) -> None:
        session = await external_practice_dao.get_session(db, user_id=log.user_id, log_id=log.id, for_update=True)
        if session is None:
            return
        session.title_snapshot = log.material_title
        if session.source_snapshot['practiced_at'] != log.practiced_at.isoformat():
            session.source_snapshot = {**session.source_snapshot, 'practiced_at': log.practiced_at.isoformat()}
            await external_practice_dao.sync_date(
                db, session=session, anchor=ExternalPracticeImportService._date_anchor(log)
            )
        await db.flush()


external_practice_import_service = ExternalPracticeImportService()
