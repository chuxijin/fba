from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, select

from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion, QbQuestionAnswer, QbQuestionEmbedding
from backend.common.enums import DataBaseType
from backend.core.conf import settings
from backend.plugin.agent.model import AgentRun
from backend.plugin.agent.service.shenlun.common import infer_question_type
from backend.plugin.agent.service.shenlun.semantic import (
    FEATURE_HASH_MODEL,
    cosine_similarity,
    embed_text,
    lexical_similarity,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ShenlunSimilarQuestionRetriever:
    """检索同题型、同任务和语义相近的申论题作为评分先例。"""

    async def retrieve(
        self,
        *,
        db: AsyncSession,
        question_id: int,
        question_text: str,
        question_type: str,
        limit: int = 5,
    ) -> dict[str, Any]:
        try:
            query_vector, embedding_space = await self._query_vector(
                db=db,
                question_id=question_id,
                question_text=question_text,
            )
            rows = await self._load_candidates(
                db=db,
                question_id=question_id,
                query_vector=query_vector,
                embedding_space=embedding_space,
                limit=max(80, limit * 20),
            )
        except Exception as error:
            return self._degraded(question_type=question_type, error=error)
        candidates: list[dict[str, Any]] = []
        for row in rows:
            stem = str(row.get('stem') or '')
            inferred_type = infer_question_type(
                stem,
                {'grading_config': row.get('grading_config') or {}},
            )
            if inferred_type != question_type:
                continue
            lexical = lexical_similarity(question_text, stem)
            vector = float(row.get('_vector_score') or 0.0)
            task = 1.0
            score = round(0.55 * vector + 0.3 * lexical + 0.15 * task, 4)
            if score < 0.16:
                continue
            candidates.append({
                'evidence_id': f'similar-question:{row["id"]}',
                'question_id': int(row['id']),
                'question_type': inferred_type,
                'stem_preview': stem[:500],
                'similarity': score,
                'vector_score': round(vector, 4),
                'lexical_score': lexical,
                'retrieval_backend': row.get('_vector_backend') or FEATURE_HASH_MODEL,
                'role': 'grading_reference',
            })
        candidates.sort(key=lambda item: (-item['similarity'], item['question_id']))
        return {
            'query_question_id': question_id,
            'question_type': question_type,
            'retrieval_degraded': False,
            'candidate_count': len(candidates),
            'candidates': candidates[: max(1, min(limit, 12))],
        }

    async def attach_rubric_precedents(
        self,
        *,
        db: AsyncSession,
        retrieval: dict[str, Any],
    ) -> dict[str, Any]:
        """为相似题附加已经过校验的历史 Rubric 摘要。"""
        candidates = retrieval.get('candidates') if isinstance(retrieval.get('candidates'), list) else []
        if not candidates:
            return retrieval
        from backend.plugin.agent.crud import agent_rubric_dao

        try:
            rubrics = await agent_rubric_dao.list_latest_ready(
                db,
                agent_key='shenlun.grading',
                question_ids=[int(item['question_id']) for item in candidates],
            )
        except Exception as error:
            retrieval['rubric_precedent_count'] = 0
            retrieval['rubric_retrieval_degraded'] = True
            retrieval['rubric_retrieval_error'] = type(error).__name__
            return retrieval
        by_question = {item.question_id: item for item in rubrics}
        precedent_count = 0
        for candidate in candidates:
            rubric = by_question.get(int(candidate['question_id']))
            if rubric is None:
                continue
            payload = rubric.rubric_payload if isinstance(rubric.rubric_payload, dict) else {}
            candidate['rubric_precedent'] = {
                'rubric_id': rubric.id,
                'rubric_version': rubric.rubric_version,
                'question_type': payload.get('question_type') or '',
                'task_constraints': payload.get('task_constraints') or {},
                'points': [
                    {
                        'label': point.get('label') or '',
                        'canonical_expression': point.get('canonical_expression') or '',
                        'importance': point.get('importance') or '',
                        'coverage_role': point.get('coverage_role') or '',
                    }
                    for point in (payload.get('points') or [])[:12]
                    if isinstance(point, dict)
                ],
            }
            precedent_count += 1
        retrieval['rubric_precedent_count'] = precedent_count
        try:
            cases = await self._load_grading_cases(
                db=db,
                question_ids=[int(item['question_id']) for item in candidates],
            )
        except Exception as error:
            retrieval['case_retrieval_degraded'] = True
            retrieval['case_retrieval_error'] = type(error).__name__
            return retrieval
        case_count = 0
        for candidate in candidates:
            case = cases.get(int(candidate['question_id']))
            if case is None:
                continue
            candidate['grading_case'] = case
            case_count += 1
        retrieval['grading_case_count'] = case_count
        return retrieval

    @staticmethod
    async def _query_vector(
        *,
        db: AsyncSession,
        question_id: int,
        question_text: str,
    ) -> tuple[list[float], str | None]:
        if DataBaseType.postgresql != settings.DATABASE_TYPE:
            vector, _ = embed_text(question_text)
            return vector, None
        stmt = (
            select(QbQuestionEmbedding.embedding, QbQuestionEmbedding.embedding_space)
            .where(
                QbQuestionEmbedding.question_id == question_id,
                QbQuestionEmbedding.deleted == 0,
            )
            .order_by(QbQuestionEmbedding.id.desc())
            .limit(1)
        )
        row = (await db.execute(stmt)).first()
        if row is not None and row[0]:
            return [float(value) for value in row[0]], str(row[1])
        vector, _ = embed_text(question_text)
        return vector, None

    async def _load_candidates(
        self,
        *,
        db: AsyncSession,
        question_id: int,
        query_vector: list[float],
        embedding_space: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        base = (
            select(QbQuestion, QbQuestionAnswer.grading_config)
            .join(
                QbQuestionAnswer,
                and_(
                    QbQuestionAnswer.question_id == QbQuestion.id,
                    QbQuestionAnswer.grading_method.in_({'manual', 'rubric', 'custom'}),
                    QbQuestionAnswer.deleted == 0,
                ),
            )
            .where(
                QbQuestion.id != question_id,
                QbQuestion.question_type.in_({'short_answer', 'composite'}),
                QbQuestion.visibility.in_({'public', 'internal'}),
                QbQuestion.status == 'active',
                QbQuestion.deleted == 0,
            )
        )
        if embedding_space and DataBaseType.postgresql == settings.DATABASE_TYPE:
            stmt = (
                base
                .add_columns(QbQuestionEmbedding.embedding)
                .join(
                    QbQuestionEmbedding,
                    and_(
                        QbQuestionEmbedding.question_id == QbQuestion.id,
                        QbQuestionEmbedding.embedding_space == embedding_space,
                        QbQuestionEmbedding.deleted == 0,
                    ),
                )
                .order_by(QbQuestionEmbedding.embedding.cosine_distance(query_vector), QbQuestion.id)
                .limit(max(1, min(limit, 100)))
            )
        else:
            stmt = base.order_by(QbQuestion.updated_time.desc(), QbQuestion.id.desc()).limit(max(1, min(limit, 100)))
        result: list[dict[str, Any]] = []
        for row in (await db.execute(stmt)).all():
            question, grading_config = row[0], row[1]
            embedding = row[2] if len(row) > 2 else None
            if embedding_space and embedding and len(embedding) == len(query_vector):
                vector_score = cosine_similarity(query_vector, [float(value) for value in embedding])
                vector_backend = f'pgvector:{embedding_space}'
            else:
                fallback_vector, _ = embed_text(question.stem)
                vector_score = cosine_similarity(query_vector, fallback_vector)
                vector_backend = FEATURE_HASH_MODEL
            result.append({
                'id': question.id,
                'stem': question.stem,
                'question_type': question.question_type,
                'grading_config': grading_config or {},
                '_vector_score': max(0.0, vector_score),
                '_vector_backend': vector_backend,
            })
        return result

    @staticmethod
    async def _load_grading_cases(
        *,
        db: AsyncSession,
        question_ids: list[int],
    ) -> dict[int, dict[str, Any]]:
        if not question_ids:
            return {}
        stmt = (
            select(QbQuestionAttempt.question_id, AgentRun)
            .join(
                AgentRun,
                and_(
                    AgentRun.subject_type == 'qbank_v2_attempt',
                    AgentRun.subject_id == QbQuestionAttempt.id,
                    AgentRun.agent_key == 'shenlun.grading',
                    AgentRun.status == 'succeeded',
                    AgentRun.deleted == 0,
                ),
            )
            .where(
                QbQuestionAttempt.question_id.in_(set(question_ids)),
                QbQuestionAttempt.deleted == 0,
            )
            .order_by(QbQuestionAttempt.question_id, AgentRun.id.desc())
            .limit(100)
        )
        result: dict[int, dict[str, Any]] = {}
        for question_id, run in (await db.execute(stmt)).all():
            if question_id in result:
                continue
            payload = run.result_payload or {}
            if payload.get('score_status') != 'valid' or payload.get('status') != 'valid':
                continue
            result[int(question_id)] = {
                'evidence_id': f'grading-case:{run.id}',
                'run_id': run.id,
                'raw_score': payload.get('raw_score'),
                'display_score': payload.get('display_score'),
                'display_max_score': payload.get('display_max_score'),
                'point_outcomes': [
                    {
                        'point_key': item.get('point_key'),
                        'status': item.get('status'),
                    }
                    for item in (payload.get('point_matches') or [])[:12]
                ],
                'role': 'grading_precedent',
            }
        return result

    @staticmethod
    def _degraded(*, question_type: str, error: Exception) -> dict[str, Any]:
        return {
            'question_type': question_type,
            'retrieval_degraded': True,
            'retrieval_error': type(error).__name__,
            'candidate_count': 0,
            'candidates': [],
        }


shenlun_similar_question_retriever = ShenlunSimilarQuestionRetriever()
