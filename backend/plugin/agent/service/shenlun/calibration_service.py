from __future__ import annotations

import hashlib
import json

from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from backend.app.question_bank_v2.model.bank import QbBankItem, QbBankRevision
from backend.app.question_bank_v2.model.evaluation import QbEvaluationRun
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbQuestionAttempt,
)
from backend.plugin.agent.crud import agent_calibration_anchor_dao, agent_calibration_policy_dao
from backend.plugin.agent.model import AgentRun
from backend.plugin.agent.service.shenlun.calibration import (
    CALIBRATION_POLICY_VERSION,
    empty_calibration_policy,
    fit_offset_policy,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


AGENT_KEY = 'shenlun.grading'


class ShenlunCalibrationService:
    """申论整卷人工锚点和校准策略服务。"""

    async def get_policy(
        self,
        *,
        db: AsyncSession,
        bank_revision_id: int | None,
        question_type: str,
    ) -> dict[str, Any]:
        """按题库版本、题型、全局顺序读取当前有效策略。"""
        policy = await agent_calibration_policy_dao.get_active(
            db,
            agent_key=AGENT_KEY,
            bank_revision_id=bank_revision_id,
            question_type=question_type,
        )
        if policy is None:
            return empty_calibration_policy()
        payload = dict(policy.policy_payload or {})
        if payload.get('policy_version') != CALIBRATION_POLICY_VERSION:
            return empty_calibration_policy() | {'reason': 'unsupported_policy_version'}
        return payload

    async def refresh(
        self,
        *,
        db: AsyncSession,
        bank_revision_id: int | None = None,
        session_id: int | None = None,
        agent_key: str = AGENT_KEY,
    ) -> dict[str, Any]:
        """扫描已完成人工判分的整卷并拟合可验证的校准策略。"""
        sessions = await self._list_candidate_sessions(
            db=db,
            bank_revision_id=bank_revision_id,
            session_id=session_id,
        )
        results: list[dict[str, Any]] = []
        for session, revision in sessions:
            results.append(await self._refresh_session(db=db, session=session, revision=revision, agent_key=agent_key))

        ready = await agent_calibration_anchor_dao.list_ready(db, agent_key=agent_key)
        activated_scopes: list[str] = []
        global_rows = [self._anchor_row(anchor) for anchor in ready]
        if self._activate_policy_if_valid(
            await self._fit_and_store_policy(
                db=db,
                agent_key=agent_key,
                scope_type='global',
                scope_key='global',
                rows=global_rows,
            )
        ):
            activated_scopes.append('global:global')

        by_question_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for anchor in ready:
            for row in (anchor.metadata_payload or {}).get('question_rows') or []:
                question_type = str(row.get('question_type') or '')
                if question_type:
                    by_question_type[question_type].append(row)
        for question_type, rows in by_question_type.items():
            if self._activate_policy_if_valid(
                await self._fit_and_store_policy(
                    db=db,
                    agent_key=agent_key,
                    scope_type='question_type',
                    scope_key=question_type,
                    rows=rows,
                )
            ):
                activated_scopes.append(f'question_type:{question_type}')

        await db.commit()
        return {
            'agent_key': agent_key,
            'scanned_session_count': len(sessions),
            'ready_anchor_count': len(ready),
            'activated_scopes': activated_scopes,
            'results': results,
        }

    async def _list_candidate_sessions(
        self,
        *,
        db: AsyncSession,
        bank_revision_id: int | None,
        session_id: int | None,
    ) -> list[tuple[QbPracticeSession, QbBankRevision]]:
        stmt = (
            select(QbPracticeSession, QbBankRevision)
            .join(QbBankRevision, QbBankRevision.id == QbPracticeSession.bank_revision_id)
            .where(
                QbPracticeSession.bank_revision_id.is_not(None),
                QbPracticeSession.mode.in_({'exam', 'mock'}),
                QbPracticeSession.status.in_({'submitted', 'graded'}),
                QbPracticeSession.deleted == 0,
                QbBankRevision.bank_kind.in_({'paper', 'mock'}),
                QbBankRevision.status.in_({'published', 'retired'}),
                QbBankRevision.deleted == 0,
            )
            .order_by(QbPracticeSession.id)
        )
        if bank_revision_id is not None:
            stmt = stmt.where(QbPracticeSession.bank_revision_id == bank_revision_id)
        if session_id is not None:
            stmt = stmt.where(QbPracticeSession.id == session_id)
        return list((await db.execute(stmt)).all())

    async def _refresh_session(  # noqa: C901
        self,
        *,
        db: AsyncSession,
        session: QbPracticeSession,
        revision: QbBankRevision,
        agent_key: str,
    ) -> dict[str, Any]:
        required_items = await self._required_items(db=db, revision_id=revision.id)
        session_items = await self._session_items(db=db, session_id=session.id)
        required_question_ids = {item.question_id for item in required_items}
        required_session_items = [item for item in session_items if item.question_id in required_question_ids]
        attempts = await self._latest_attempts(db=db, session_id=session.id)
        required_session_item_ids = {item.id for item in required_session_items}
        attempts = {
            session_item_id: attempt
            for session_item_id, attempt in attempts.items()
            if session_item_id in required_session_item_ids
        }
        agent_runs = await self._agent_runs(db=db, attempt_ids=[attempt.id for attempt in attempts.values()])
        manual_session = await self._manual_session_run(db=db, session_id=session.id)
        manual_runs = await self._manual_attempt_runs(
            db=db,
            attempt_ids=[attempt.id for attempt in attempts.values()],
        )

        paper_total = _decimal(revision.total_score)
        expected_total = sum((_decimal(item.score) for item in required_items), Decimal(0))
        session_total = sum((_decimal(item.max_score) for item in required_session_items), Decimal(0))
        missing_questions = [
            item.question_id
            for item in required_items
            if item.question_id not in {session_item.question_id for session_item in session_items}
        ]
        incomplete_attempts = [item.question_id for item in required_session_items if item.id not in attempts]
        actual_attempt_scores: dict[int, Decimal] = {}
        manual_source_ids: list[str] = []
        for attempt in attempts.values():
            session_item = self._session_item_for_attempt(attempt, required_session_items)
            if session_item is None:
                continue
            manual_run = manual_runs.get(attempt.id)
            if (
                manual_run is not None
                and manual_run.score is not None
                and (manual_run.max_score is None or _decimal(manual_run.max_score) == _decimal(session_item.max_score))
            ):
                actual_attempt_scores[attempt.session_item_id] = _decimal(manual_run.score)
                manual_source_ids.append(f'evaluation:{manual_run.id}')
            elif (
                attempt.grading_method == 'manual' and attempt.grading_status == 'graded' and attempt.score is not None
            ):
                actual_attempt_scores[attempt.session_item_id] = _decimal(attempt.score)
                manual_source_ids.append(f'attempt:{attempt.id}')
        predicted_runs = {run.subject_id: run for run in agent_runs if self._is_valid_agent_run(run)}
        missing_agent_runs = [attempt.id for attempt in attempts.values() if attempt.id not in predicted_runs]

        question_rows: list[dict[str, Any]] = []
        for attempt in attempts.values():
            if attempt.session_item_id not in actual_attempt_scores or attempt.id not in predicted_runs:
                continue
            session_item = self._session_item_for_attempt(attempt, required_session_items)
            run = predicted_runs[attempt.id]
            if session_item is None:
                continue
            question_rows.append({
                'paper_id': revision.id,
                'session_id': session.id,
                'attempt_id': attempt.id,
                'question_type': str((run.result_payload or {}).get('question_type') or ''),
                'actual_score': float(
                    _percent(actual_attempt_scores[attempt.session_item_id], _decimal(session_item.max_score))
                ),
                'predicted_score': float(_decimal((run.result_payload or {}).get('raw_score'))),
            })

        actual_total = (
            _decimal(manual_session.score)
            if manual_session and manual_session.score is not None
            else sum(actual_attempt_scores.values(), Decimal(0))
        )
        predicted_total = sum(
            (
                _decimal((predicted_runs[attempt.id].result_payload or {}).get('raw_score'))
                * _decimal(self._session_item_for_attempt(attempt, session_items).max_score)
                / Decimal(100)
                for attempt in attempts.values()
                if attempt.id in predicted_runs and self._session_item_for_attempt(attempt, session_items) is not None
            ),
            Decimal(0),
        )
        source_payload = {
            'session_id': session.id,
            'revision_id': revision.id,
            'manual_session_id': manual_session.id if manual_session else None,
            'manual_sources': sorted(manual_source_ids),
            'agent_runs': sorted((run.subject_id, run.id) for run in predicted_runs.values()),
            'status': session.status,
        }
        source_hash = _hash(source_payload)
        valid = not missing_questions and not incomplete_attempts and not missing_agent_runs
        reason = None
        if expected_total != paper_total:
            valid, reason = False, 'revision_total_not_closed'
        elif session_total != paper_total:
            valid, reason = False, 'session_total_not_closed'
        elif manual_session is None and len(actual_attempt_scores) != len(required_session_items):
            valid, reason = False, 'manual_scores_incomplete'
        elif manual_session is not None and manual_session.score is None:
            valid, reason = False, 'manual_session_score_missing'
        elif (
            manual_session is not None
            and manual_session.max_score is not None
            and _decimal(manual_session.max_score) != paper_total
        ):
            valid, reason = False, 'manual_session_max_score_mismatch'
        elif (
            manual_session is not None
            and len(actual_attempt_scores) == len(required_session_items)
            and sum(actual_attempt_scores.values(), Decimal(0)) != actual_total
        ):
            valid, reason = False, 'manual_scores_not_closed'
        elif actual_total < 0 or actual_total > paper_total:
            valid, reason = False, 'manual_score_out_of_range'
        elif predicted_total < 0 or predicted_total > paper_total:
            valid, reason = False, 'agent_score_out_of_range'
        elif missing_questions:
            reason = 'required_questions_missing'
        elif incomplete_attempts:
            reason = 'attempts_incomplete'
        elif missing_agent_runs:
            reason = 'agent_predictions_incomplete'

        actual_percent = _percent(actual_total, paper_total)
        predicted_percent = _percent(predicted_total, paper_total)
        metadata = {
            'required_question_ids': [item.question_id for item in required_items],
            'missing_questions': missing_questions,
            'incomplete_attempts': incomplete_attempts,
            'missing_agent_runs': missing_agent_runs,
            'manual_session_run_id': manual_session.id if manual_session else None,
            'manual_source_ids': manual_source_ids,
            'agent_run_ids': [run.id for run in predicted_runs.values()],
            'question_types': sorted({
                str(run.result_payload.get('question_type'))
                for run in predicted_runs.values()
                if (run.result_payload or {}).get('question_type')
            }),
            'question_rows': question_rows,
        }
        data = {
            'agent_key': agent_key,
            'bank_revision_id': revision.id,
            'session_id': session.id,
            'user_id': session.user_id,
            'actual_score_percent': actual_percent,
            'predicted_score_percent': predicted_percent,
            'actual_total_score': actual_total,
            'predicted_total_score': predicted_total,
            'paper_total_score': paper_total,
            'source_type': 'manual_session' if manual_session else 'manual_attempt_sum',
            'source_hash': source_hash,
            'status': 'ready' if valid else 'excluded',
            'exclusion_reason': reason,
            'metadata_payload': metadata,
        }
        await agent_calibration_anchor_dao.upsert(db, data=data)
        return {
            'session_id': session.id,
            'anchor_status': data['status'],
            'exclusion_reason': reason,
            'activated_scopes': [],
        }

    async def _fit_and_store_policy(
        self,
        *,
        db: AsyncSession,
        agent_key: str,
        scope_type: str,
        scope_key: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        policy = fit_offset_policy(rows)
        source_hash = _hash({'scope_type': scope_type, 'scope_key': scope_key, 'rows': rows})
        if not policy.get('enabled'):
            await agent_calibration_policy_dao.retire_scope(
                db,
                agent_key=agent_key,
                scope_type=scope_type,
                scope_key=scope_key,
            )
            return {'enabled': False, 'policy': policy}
        existing = await agent_calibration_policy_dao.get_by_source(
            db,
            agent_key=agent_key,
            source_hash=source_hash,
        )
        if existing is not None and existing.status == 'active':
            return {'enabled': True, 'policy': policy, 'existing': True}
        await agent_calibration_policy_dao.activate(
            db,
            data={
                'agent_key': agent_key,
                'policy_version': str(policy.get('policy_version') or CALIBRATION_POLICY_VERSION),
                'scope_type': scope_type,
                'scope_key': scope_key,
                'anchor_count': int(policy.get('anchor_count') or 0),
                'paper_count': int(policy.get('paper_count') or 0),
                'source_hash': source_hash,
                'policy_payload': policy,
                'metrics_payload': {
                    'baseline_mae': policy.get('baseline_mae'),
                    'calibrated_mae': policy.get('calibrated_mae'),
                    'validation_method': policy.get('validation_method'),
                },
            },
        )
        return {'enabled': True, 'policy': policy, 'existing': False}

    @staticmethod
    def _activate_policy_if_valid(result: dict[str, Any]) -> bool:
        return bool(result.get('enabled') and not result.get('existing'))

    @staticmethod
    async def _required_items(*, db: AsyncSession, revision_id: int) -> list[QbBankItem]:
        stmt = (
            select(QbBankItem)
            .where(
                QbBankItem.bank_revision_id == revision_id,
                QbBankItem.is_required.is_(True),
                QbBankItem.is_active.is_(True),
                QbBankItem.deleted == 0,
            )
            .order_by(QbBankItem.sort_order, QbBankItem.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def _session_items(*, db: AsyncSession, session_id: int) -> list[QbPracticeSessionItem]:
        stmt = (
            select(QbPracticeSessionItem)
            .where(
                QbPracticeSessionItem.session_id == session_id,
                QbPracticeSessionItem.deleted == 0,
            )
            .order_by(QbPracticeSessionItem.position, QbPracticeSessionItem.id)
        )
        return list((await db.execute(stmt)).scalars().all())

    @staticmethod
    async def _latest_attempts(*, db: AsyncSession, session_id: int) -> dict[int, QbQuestionAttempt]:
        stmt = (
            select(QbQuestionAttempt)
            .where(
                QbQuestionAttempt.session_id == session_id,
                QbQuestionAttempt.deleted == 0,
            )
            .order_by(
                QbQuestionAttempt.session_item_id, QbQuestionAttempt.attempt_no.desc(), QbQuestionAttempt.id.desc()
            )
        )
        result: dict[int, QbQuestionAttempt] = {}
        for attempt in (await db.execute(stmt)).scalars().all():
            if attempt.session_item_id is not None and attempt.session_item_id not in result:
                result[attempt.session_item_id] = attempt
        return result

    @staticmethod
    async def _agent_runs(*, db: AsyncSession, attempt_ids: list[int]) -> list[AgentRun]:
        if not attempt_ids:
            return []
        stmt = (
            select(AgentRun)
            .where(
                AgentRun.agent_key == AGENT_KEY,
                AgentRun.subject_type == 'qbank_v2_attempt',
                AgentRun.subject_id.in_(attempt_ids),
                AgentRun.status == 'succeeded',
                AgentRun.deleted == 0,
            )
            .order_by(AgentRun.subject_id, AgentRun.id.desc())
        )
        result: dict[int, AgentRun] = {}
        for run in (await db.execute(stmt)).scalars().all():
            result.setdefault(run.subject_id, run)
        return list(result.values())

    @staticmethod
    async def _manual_session_run(*, db: AsyncSession, session_id: int) -> QbEvaluationRun | None:
        stmt = (
            select(QbEvaluationRun)
            .where(
                QbEvaluationRun.session_id == session_id,
                QbEvaluationRun.attempt_id.is_(None),
                QbEvaluationRun.purpose == 'session_summary',
                QbEvaluationRun.engine_type == 'manual',
                QbEvaluationRun.status == 'succeeded',
                QbEvaluationRun.is_latest.is_(True),
                QbEvaluationRun.deleted == 0,
            )
            .order_by(QbEvaluationRun.id.desc())
            .limit(1)
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    async def _manual_attempt_runs(
        *,
        db: AsyncSession,
        attempt_ids: list[int],
    ) -> dict[int, QbEvaluationRun]:
        if not attempt_ids:
            return {}
        stmt = (
            select(QbEvaluationRun)
            .where(
                QbEvaluationRun.attempt_id.in_(attempt_ids),
                QbEvaluationRun.session_id.is_(None),
                QbEvaluationRun.purpose == 'attempt_grading',
                QbEvaluationRun.engine_type == 'manual',
                QbEvaluationRun.status == 'succeeded',
                QbEvaluationRun.is_latest.is_(True),
                QbEvaluationRun.deleted == 0,
            )
            .order_by(QbEvaluationRun.attempt_id, QbEvaluationRun.id.desc())
        )
        result: dict[int, QbEvaluationRun] = {}
        for run in (await db.execute(stmt)).scalars().all():
            if run.attempt_id is not None:
                result.setdefault(run.attempt_id, run)
        return result

    @staticmethod
    def _is_valid_agent_run(run: AgentRun) -> bool:
        result = run.result_payload or {}
        return (
            run.status == 'succeeded'
            and result.get('score_status') == 'valid'
            and result.get('status') == 'valid'
            and result.get('raw_score') is not None
            and result.get('display_max_score') is not None
        )

    @staticmethod
    def _session_item_for_attempt(
        attempt: QbQuestionAttempt,
        session_items: list[QbPracticeSessionItem],
    ) -> QbPracticeSessionItem | None:
        return next((item for item in session_items if item.id == attempt.session_item_id), None)

    @staticmethod
    def _anchor_row(anchor: Any) -> dict[str, Any]:
        return {
            'paper_id': anchor.bank_revision_id,
            'actual_score': float(anchor.actual_score_percent),
            'predicted_score': float(anchor.predicted_score_percent),
        }


def _decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal('0.001'))
    except (ArithmeticError, TypeError, ValueError):
        return Decimal('0.000')


def _percent(score: Decimal, total: Decimal) -> Decimal:
    if total <= 0:
        return Decimal('0.000')
    return (score * Decimal(100) / total).quantize(Decimal('0.001'))


def _hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


shenlun_calibration_service = ShenlunCalibrationService()
