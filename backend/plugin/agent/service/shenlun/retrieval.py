from __future__ import annotations

import json

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, case, select

from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ShenlunHistoryRetriever:
    """从题库 V2 读取可审计的用户历史作答证据。"""

    async def retrieve(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        question_type: str,
        current_attempt_id: int = 0,
        limit: int = 12,
    ) -> dict[str, Any]:
        stmt = (
            select(
                QbQuestionAttempt.id,
                QbQuestionAttempt.question_id,
                QbQuestionAttempt.response_data,
                QbQuestionAttempt.score,
                QbQuestionAttempt.grading_status,
                QbQuestionAttempt.submitted_time,
                QbQuestion.stem,
                QbQuestion.question_type,
                QbPracticeSessionItem.max_score,
            )
            .join(QbQuestion, and_(QbQuestion.id == QbQuestionAttempt.question_id, QbQuestion.deleted == 0))
            .outerjoin(
                QbPracticeSessionItem,
                and_(
                    QbPracticeSessionItem.id == QbQuestionAttempt.session_item_id,
                    QbPracticeSessionItem.deleted == 0,
                ),
            )
            .where(
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.deleted == 0,
                QbQuestionAttempt.id != current_attempt_id,
                QbQuestionAttempt.grading_status.in_({'graded', 'review_required'}),
                QbQuestion.question_type == question_type,
            )
            .order_by(
                case((QbQuestionAttempt.question_id == question_id, 0), else_=1),
                QbQuestionAttempt.submitted_time.desc(),
                QbQuestionAttempt.id.desc(),
            )
            .limit(max(1, min(limit, 50)))
        )
        rows = (await db.execute(stmt)).mappings().all()
        evidence: list[dict[str, Any]] = []
        for row in rows:
            score = _optional_number(row['score'])
            max_score = _optional_number(row['max_score']) or 100.0
            answer = _stringify(row['response_data'])
            submitted = row['submitted_time']
            evidence.append({
                'evidence_id': f'attempt:{row["id"]}',
                'attempt_id': int(row['id']),
                'question_id': int(row['question_id']),
                'question_type': row['question_type'],
                'role': 'personalization',
                'score': score,
                'max_score': max_score,
                'score_rate': round(score / max_score, 4) if score is not None and max_score else None,
                'answer_word_count': len(answer),
                'answer_preview': answer[:180],
                'submitted_time': submitted.isoformat() if isinstance(submitted, datetime) else str(submitted or ''),
                'grading_status': row['grading_status'],
            })
        return {
            'history_attempt_count': len(evidence),
            'history_stable': len(evidence) >= 2,
            'retrieval_degraded': False,
            'evidence': evidence,
            'signals': _signals(evidence),
        }


def _signals(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not evidence:
        return []
    low_score = [item for item in evidence if item.get('score_rate') is not None and float(item['score_rate']) < 0.6]
    short_answers = [item for item in evidence if 0 < int(item.get('answer_word_count') or 0) < 80]
    signals: list[dict[str, Any]] = []
    if len(low_score) >= 2:
        signals.append({
            'signal_key': 'repeated_low_score',
            'finding': '同类申论作答中多次处于较低得分区间。',
            'evidence_ids': [item['evidence_id'] for item in low_score[:6]],
        })
    if len(short_answers) >= 2:
        signals.append({
            'signal_key': 'repeated_short_answer',
            'finding': '同类作答多次篇幅明显偏短，可能导致要点覆盖不足。',
            'evidence_ids': [item['evidence_id'] for item in short_answers[:6]],
        })
    return signals


def _optional_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ''
    return json.dumps(value, ensure_ascii=False, default=str)


shenlun_history_retriever = ShenlunHistoryRetriever()
