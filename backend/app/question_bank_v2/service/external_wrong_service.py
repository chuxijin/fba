"""同题内容复用、按真实报告追加错误；同报告重导只补未知字段。"""

import re

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_external_practice import external_practice_dao
from backend.app.question_bank_v2.crud.crud_external_wrong import EXTERNAL_WRONG_KEY, external_wrong_dao
from backend.app.question_bank_v2.crud.crud_practice import question_attempt_dao
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.model.review import QbQuestionReview, QbWrongQuestionState
from backend.app.question_bank_v2.schema.external_practice import ImportPracticeQuestionParam
from backend.app.question_bank_v2.schema.review import CreateExternalWrongQuestionParam
from backend.app.question_bank_v2.utils.external_practice import EXTERNAL_PRACTICE_ORIGIN, external_question_identity
from backend.common.exception import errors
from backend.utils.timezone import timezone

OccurrenceKey = tuple[str, str, str]


def _answer_key(value: Any) -> Any:
    if isinstance(value, dict) and 'selected' in value:
        value = value['selected']
    if isinstance(value, str):
        value = list(value) if re.fullmatch(r'[A-Z]+', value) else value
    return sorted(value) if isinstance(value, list) and all(isinstance(item, str) for item in value) else value


def _report_key(metadata: dict[str, Any]) -> str | None:
    if metadata.get('wrong_report_key'):
        return str(metadata['wrong_report_key'])
    key = str(metadata.get('external_key') or '')
    match = re.fullmatch(r'fenbi:(\d+_\d+_[a-zA-Z0-9]+):[^:]+', key)
    return match[1] if match else None


def _title(value: str | None) -> str:
    return re.sub(r'^粉笔', '', value or '').strip()


def _merge_snapshot(old: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """答案与用时来自同报告；冲突拒绝，绝不从别的报告补时间。"""
    if _answer_key(old['response_data']) != _answer_key(incoming['response_data']):
        raise errors.ConflictError(msg='同一练习报告的错误答案与已保存记录冲突')
    if (
        old['duration_ms'] is not None
        and incoming['duration_ms'] is not None
        and old['duration_ms'] != incoming['duration_ms']
    ):
        raise errors.ConflictError(msg='同一练习报告的作答用时与已保存记录冲突')
    merged = dict(old)
    for key in ('duration_ms', 'submitted_time', 'attempt_id', 'attempt_created_time'):
        if merged.get(key) is None and incoming.get(key) is not None:
            merged[key] = incoming[key]
    return merged


class ExternalWrongService:
    @staticmethod
    def initial_metadata(obj: CreateExternalWrongQuestionParam) -> dict[str, str]:
        return {'wrong_report_key': obj.wrong_occurrence.source_key} if obj.wrong_occurrence else {}

    @staticmethod
    async def related_ids(db: AsyncSession, *, state: QbWrongQuestionState, question: QbQuestion) -> list[int]:
        identity = external_question_identity(state.entry_metadata)
        if not identity:
            return [question.id]
        peers = await external_practice_dao.find_source_questions(
            db,
            user_id=state.user_id,
            platform=identity[0],
            source_question_key=identity[1],
            core={
                'stem': question.stem,
                'options': question.option_data,
                'content_format': question.content_format,
                'question_type': question.question_type,
            },
            include_deleted=True,
        )
        return list({question.id, *(peer.id for peer in peers)})

    @staticmethod
    async def sync(
        db: AsyncSession,
        *,
        state: QbWrongQuestionState,
        question: QbQuestion,
        obj: CreateExternalWrongQuestionParam | None = None,
    ) -> None:
        """调用方持有用户/状态锁；归档原始作答或独立采集均按真实报告幂等。"""
        if obj is not None and obj.entry_source != 'import':
            return
        ids = await ExternalWrongService.related_ids(db, state=state, question=question)
        identity = external_question_identity(state.entry_metadata)
        history = await question_attempt_dao.get_wrong_answer_history(
            db,
            user_id=state.user_id,
            question_id=question.id,
            related_question_ids=[qid for qid in ids if qid != question.id],
            include_external_source=True,
        )
        incoming = ExternalWrongService._build_incoming(history, identity=identity, obj=obj)
        if not incoming:
            return
        snapshots = await ExternalWrongService._sync_events(db, state=state, ids=ids, incoming=incoming)
        await ExternalWrongService._update_latest(db, state=state, incoming=snapshots)
        await db.flush()

    @staticmethod
    def _build_incoming(
        history: list[dict[str, Any]],
        *,
        identity: tuple[str, str] | None,
        obj: CreateExternalWrongQuestionParam | None,
    ) -> dict[OccurrenceKey, dict[str, Any]]:
        incoming: dict[OccurrenceKey, dict[str, Any]] = {}
        for row in history:
            if row.get('origin') != EXTERNAL_PRACTICE_ORIGIN or not row.get('source_key'):
                continue
            source_question_key = row.get('source_question_key') or (identity[1] if identity else None)
            if not row.get('source_platform') or not source_question_key:
                continue
            key = (row['source_platform'], row['source_key'], source_question_key)
            snapshot = {
                'platform': key[0],
                'source_key': key[1],
                'source': row.get('source'),
                'source_question_key': key[2],
                'response_data': row['response_data'],
                'duration_ms': row['duration_ms'],
                'submitted_time': row['submitted_time'].isoformat(),
                'attempt_id': row['attempt_id'],
                'attempt_created_time': row['attempt_created_time'].isoformat()
                if row.get('attempt_created_time')
                else None,
            }
            incoming[key] = _merge_snapshot(incoming[key], snapshot) if key in incoming else snapshot
        if obj is not None and obj.wrong_occurrence is not None:
            occurrence_identity = external_question_identity({
                **obj.entry_metadata,
                'source_system': obj.source_system,
                'external_key': obj.external_key,
            })
            if obj.wrong_response is None or not obj.source_system or occurrence_identity is None:
                raise errors.RequestError(msg='当次错误记录必须提供真实错误答案及稳定原站题号')
            occurrence = obj.wrong_occurrence
            source_question_key = occurrence_identity[1]
            key = (obj.source_system, occurrence.source_key, source_question_key)
            snapshot = {
                'platform': key[0],
                'source_key': key[1],
                'source': obj.entry_metadata.get('source'),
                'source_question_key': key[2],
                'response_data': obj.wrong_response,
                'duration_ms': occurrence.duration_seconds * 1000 if occurrence.duration_seconds is not None else None,
                'submitted_time': occurrence.submitted_time.isoformat() if occurrence.submitted_time else None,
                'attempt_id': None,
            }
            incoming[key] = _merge_snapshot(incoming[key], snapshot) if key in incoming else snapshot
        return incoming

    @staticmethod
    async def _same_question_attempt(
        db: AsyncSession, *, state: QbWrongQuestionState, attempt_id: int | None
    ) -> int | None:
        if attempt_id is None:
            return None
        attempt = await question_attempt_dao.get(db, attempt_id, user_id=state.user_id)
        return attempt.id if attempt is not None and attempt.question_id == state.question_id else None

    @staticmethod
    def _initial_credit_key(
        state: QbWrongQuestionState,
        incoming: dict[OccurrenceKey, dict[str, Any]],
        *,
        events: list[QbQuestionReview],
    ) -> OccurrenceKey | None:
        legacy = next(
            (
                event
                for event in events
                if event.wrong_state_id == state.id and event.review_data[EXTERNAL_WRONG_KEY].get('legacy_initial')
            ),
            None,
        )
        if legacy is not None:
            matches = [
                key
                for key, data in incoming.items()
                if ExternalWrongService._matches_initial_snapshot(
                    legacy.review_data[EXTERNAL_WRONG_KEY], data, collected_time=legacy.reviewed_time
                )
            ]
            return matches[0] if len(matches) == 1 else None
        metadata = state.entry_metadata
        if initial_key := _report_key(metadata):
            identity = external_question_identity(metadata)
            return (identity[0], initial_key, identity[1]) if identity else None
        # 只用于旧初始计数抵扣，不把标题作为报告身份。
        initial_candidates = [
            key
            for key, data in incoming.items()
            if data.get('attempt_created_time')
            and datetime.fromisoformat(data['attempt_created_time']) <= state.created_time
            and _title(data.get('source')) == _title(metadata.get('source'))
            and _answer_key(data['response_data']) == _answer_key(state.last_wrong_response)
        ]
        return initial_candidates[0] if len(initial_candidates) == 1 else None

    @staticmethod
    async def _sync_events(
        db: AsyncSession,
        *,
        state: QbWrongQuestionState,
        ids: list[int],
        incoming: dict[OccurrenceKey, dict[str, Any]],
    ) -> dict[OccurrenceKey, dict[str, Any]]:
        events = await external_wrong_dao.get_events(db, user_id=state.user_id, question_ids=ids)
        # 保留比这次重导更新的错误；错题状态撤销后重建也可找回独立错误事实。
        for event in events:
            saved = event.review_data[EXTERNAL_WRONG_KEY]
            if saved.get('legacy_initial'):
                continue
            key = (saved['platform'], saved['source_key'], saved['source_question_key'])
            incoming[key] = _merge_snapshot(saved, incoming[key]) if key in incoming else saved
        existing = {
            (
                event.review_data[EXTERNAL_WRONG_KEY]['platform'],
                event.review_data[EXTERNAL_WRONG_KEY]['source_key'],
                event.review_data[EXTERNAL_WRONG_KEY]['source_question_key'],
            ): event
            for event in events
            if event.wrong_state_id == state.id and not event.review_data[EXTERNAL_WRONG_KEY].get('legacy_initial')
        }
        metadata = dict(state.entry_metadata or {})
        credit_key = (
            ExternalWrongService._initial_credit_key(state, incoming, events=events)
            if state.entry_source == 'import'
            else None
        )
        added = 0
        for key, data in incoming.items():
            event = existing.get(key)
            if event is not None:
                merged = _merge_snapshot(event.review_data[EXTERNAL_WRONG_KEY], data)
                if merged != event.review_data[EXTERNAL_WRONG_KEY]:
                    event.review_data = {EXTERNAL_WRONG_KEY: merged}
                continue
            # FK 要求同一个稳定题 ID；历史旧题仅作只读关联，不改写其作答。
            source_attempt_id = await ExternalWrongService._same_question_attempt(
                db, state=state, attempt_id=data.get('attempt_id')
            )
            await external_wrong_dao.create_event(db, state=state, data=data, source_attempt_id=source_attempt_id)
            added += 1
        if credit_key in incoming and not metadata.get('external_initial_absorbed'):
            metadata['external_initial_absorbed'] = True
            added -= 1
        added += ExternalWrongService._sync_retained_initial_counts(
            state, events=events, metadata=metadata, incoming=incoming
        )
        await ExternalWrongService._preserve_initial_snapshot(db, state=state, events=events, metadata=metadata)
        state.wrong_count += added
        metadata['has_external_wrong'] = True
        state.entry_metadata = metadata
        return incoming

    @staticmethod
    def _sync_retained_initial_counts(
        state: QbWrongQuestionState,
        *,
        events: list[QbQuestionReview],
        metadata: dict[str, Any],
        incoming: dict[OccurrenceKey, dict[str, Any]],
    ) -> int:
        counted = set(metadata.get('external_legacy_initial_ids') or [])
        delta = 0
        for event in events:
            data = event.review_data[EXTERNAL_WRONG_KEY]
            if not data.get('legacy_initial') or event.wrong_state_id == state.id:
                continue
            matches = [
                snapshot
                for snapshot in incoming.values()
                if ExternalWrongService._matches_initial_snapshot(data, snapshot, collected_time=event.reviewed_time)
            ]
            matched = len(matches) == 1
            if matched and not data.get('superseded'):
                event.review_data = {EXTERNAL_WRONG_KEY: {**data, 'superseded': True}}
            if matched or data.get('superseded'):
                if event.id in counted:
                    counted.remove(event.id)
                    delta -= 1
            elif event.id not in counted:
                counted.add(event.id)
                delta += 1
        metadata['external_legacy_initial_ids'] = sorted(counted)
        return delta

    @staticmethod
    def _matches_initial_snapshot(
        initial: dict[str, Any], snapshot: dict[str, Any], *, collected_time: datetime
    ) -> bool:
        if (
            initial.get('platform') != snapshot.get('platform')
            or initial.get('source_question_key') != snapshot.get('source_question_key')
            or _answer_key(initial['response_data']) != _answer_key(snapshot['response_data'])
        ):
            return False
        if initial.get('original_source_key'):
            return initial['original_source_key'] == snapshot.get('source_key')
        created_time = snapshot.get('attempt_created_time')
        return bool(
            created_time
            and datetime.fromisoformat(created_time) <= collected_time
            and _title(initial.get('source'))
            and _title(initial.get('source')) == _title(snapshot.get('source'))
        )

    @staticmethod
    async def _preserve_initial_snapshot(
        db: AsyncSession, *, state: QbWrongQuestionState, events: list[QbQuestionReview], metadata: dict[str, Any]
    ) -> None:
        legacy = [
            event
            for event in events
            if event.wrong_state_id == state.id and event.review_data[EXTERNAL_WRONG_KEY].get('legacy_initial')
        ]
        if metadata.get('external_initial_absorbed'):
            for event in legacy:
                event.review_data = {EXTERNAL_WRONG_KEY: {**event.review_data[EXTERNAL_WRONG_KEY], 'superseded': True}}
            return
        if legacy or state.entry_source != 'import' or state.last_wrong_response is None:
            return
        identity = external_question_identity(state.entry_metadata)
        await external_wrong_dao.create_event(
            db,
            state=state,
            source_attempt_id=None,
            data={
                'platform': identity[0] if identity else metadata.get('source_system'),
                'source_key': None,
                'source_question_key': identity[1] if identity else None,
                'original_source_key': _report_key(metadata),
                'source': metadata.get('source'),
                'response_data': state.last_wrong_response,
                'duration_ms': None,
                'submitted_time': None,
                'attempt_id': None,
                'legacy_initial': True,
            },
        )

    @staticmethod
    async def _update_latest(
        db: AsyncSession, *, state: QbWrongQuestionState, incoming: dict[OccurrenceKey, dict[str, Any]]
    ) -> None:
        known = [data for data in incoming.values() if data.get('submitted_time')]
        latest = (
            max(known, key=lambda data: datetime.fromisoformat(data['submitted_time']))
            if known
            else next(reversed(incoming.values()))
        )
        actual_time = datetime.fromisoformat(latest['submitted_time']) if latest.get('submitted_time') else None
        if actual_time is not None and (
            state.last_wrong_time is None or actual_time > state.last_wrong_time or state.last_practice_time is None
        ):
            state.last_wrong_time = actual_time
            first_time = min(datetime.fromisoformat(data['submitted_time']) for data in known)
            state.first_wrong_time = min(state.first_wrong_time or first_time, first_time)
            state.last_wrong_response = latest['response_data']
            state.source_attempt_id = await ExternalWrongService._same_question_attempt(
                db, state=state, attempt_id=latest.get('attempt_id')
            )
            if state.status == 'resolved' and (state.resolved_time is None or actual_time > state.resolved_time):
                state.status = 'active'
                state.resolved_time = None
                state.correct_streak = 0

    @staticmethod
    async def merge_history(
        db: AsyncSession, *, user_id: int, question_ids: list[int], history: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        events = await external_wrong_dao.get_events(db, user_id=user_id, question_ids=question_ids)
        saved: dict[OccurrenceKey, dict[str, Any]] = {}
        legacy_events = []
        for event in events:
            data = event.review_data[EXTERNAL_WRONG_KEY]
            if data.get('legacy_initial'):
                legacy_events.append(event)
                continue
            key = (data['platform'], data['source_key'], data['source_question_key'])
            saved[key] = {
                'attempt_id': data.get('attempt_id'),
                'response_data': data['response_data'],
                'attempt_no': 1,
                'duration_ms': data['duration_ms'],
                'submitted_time': datetime.fromisoformat(data['submitted_time'])
                if data.get('submitted_time')
                else None,
                'source_key': key[1],
                'source_question_key': key[2],
                'source': data.get('source'),
                'annotations': [],
                '_sort_time': event.reviewed_time,
            }
        combined = []
        for row in history:
            key = (row.get('source_platform'), row.get('source_key'), row.get('source_question_key'))
            if row.get('origin') == EXTERNAL_PRACTICE_ORIGIN:
                snapshot = saved.pop(key, None)
                if (
                    snapshot
                    and row['duration_ms'] is None
                    and _answer_key(row['response_data']) == _answer_key(snapshot['response_data'])
                ):
                    row = {**row, 'duration_ms': snapshot['duration_ms']}
            # 只允许同报告同题同答案的缺失补全；其他报告或冲突快照绝不借用。
            combined.append(row)
        combined.extend(saved.values())
        combined.extend(ExternalWrongService._initial_history(legacy_events, history=history, events=events))
        return sorted(
            combined,
            key=lambda row: (
                not row.get('_legacy_initial', False),
                row.get('submitted_time') or row.get('_sort_time') or timezone.now(),
                row.get('attempt_id') or 0,
            ),
            reverse=True,
        )

    @staticmethod
    def _initial_history(
        legacy: list[QbQuestionReview], *, history: list[dict[str, Any]], events: list[QbQuestionReview]
    ) -> list[dict[str, Any]]:
        snapshots = [
            event.review_data[EXTERNAL_WRONG_KEY]
            for event in events
            if not event.review_data[EXTERNAL_WRONG_KEY].get('legacy_initial')
        ]
        snapshots.extend(
            {
                **row,
                'platform': row.get('source_platform'),
                'attempt_created_time': row['attempt_created_time'].isoformat()
                if row.get('attempt_created_time')
                else None,
            }
            for row in history
            if row.get('origin') == EXTERNAL_PRACTICE_ORIGIN
        )
        result = []
        for event in legacy:
            data = event.review_data[EXTERNAL_WRONG_KEY]
            matches = {
                (snapshot['platform'], snapshot['source_key'], snapshot['source_question_key'])
                for snapshot in snapshots
                if ExternalWrongService._matches_initial_snapshot(data, snapshot, collected_time=event.reviewed_time)
            }
            if data.get('superseded') or len(matches) == 1:
                continue
            result.append({
                'attempt_id': None,
                'response_data': data['response_data'],
                'attempt_no': 1,
                'duration_ms': None,
                'submitted_time': None,
                'annotations': [],
                'source_key': data.get('original_source_key'),
                'source_question_key': data.get('source_question_key'),
                'source': data.get('source'),
                '_sort_time': event.reviewed_time,
                '_legacy_initial': True,
            })
        return result

    @staticmethod
    async def sync_report_question(
        db: AsyncSession, *, user_id: int, platform: str, data: ImportPracticeQuestionParam
    ) -> None:
        """导入整卷只同步已在错题本的状态；不自动把所有错误题加入错题本。"""
        if data.status != 'wrong':
            return
        core = data.model_dump(mode='json', include={'stem', 'options', 'content_format', 'question_type'})
        questions = await external_practice_dao.find_source_questions(
            db, user_id=user_id, platform=platform, source_question_key=data.source_question_key, core=core
        )
        by_id = {question.id: question for question in questions}
        if not by_id:
            return
        states = await external_wrong_dao.get_states(db, user_id=user_id, question_ids=list(by_id))
        for state in states:
            await ExternalWrongService.sync(db, state=state, question=by_id[state.question_id])


external_wrong_service = ExternalWrongService()
