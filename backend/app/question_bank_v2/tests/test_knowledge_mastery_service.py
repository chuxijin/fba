from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from backend.app.question_bank_v2.service.knowledge_mastery_service import KnowledgeMasteryService


def test_decay_reaches_half_after_default_half_life() -> None:
    assert KnowledgeMasteryService._decay(elapsed_days=Decimal(30)) == pytest.approx(Decimal('0.5'))


@pytest.mark.parametrize(
    ('effective_sample_size', 'score', 'expected'),
    [
        (Decimal('0.5'), Decimal('0.9'), 'unknown'),
        (Decimal(2), Decimal('0.9'), 'learning'),
        (Decimal(3), Decimal('0.6'), 'stable'),
        (Decimal(5), Decimal('0.8'), 'mastered'),
    ],
)
def test_refresh_state_requires_both_score_and_evidence(
    effective_sample_size: Decimal,
    score: Decimal,
    expected: str,
) -> None:
    assert (
        KnowledgeMasteryService._refresh_state(score=score, effective_sample_size=effective_sample_size)
        == expected
    )


def test_correctness_uses_objective_result_before_score_rate() -> None:
    attempt = SimpleNamespace(is_correct=False, score=Decimal(8))
    assert KnowledgeMasteryService._correctness(attempt=attempt, max_score=Decimal(10)) == Decimal(0)


def test_correctness_supports_partial_subjective_score() -> None:
    attempt = SimpleNamespace(
        is_correct=None,
        score=Decimal(6),
        submitted_time=datetime(2026, 8, 20, tzinfo=UTC),
    )
    assert KnowledgeMasteryService._correctness(attempt=attempt, max_score=Decimal(10)) == Decimal('0.6')


def test_correctness_skips_pending_grade() -> None:
    attempt = SimpleNamespace(is_correct=None, score=None)
    assert KnowledgeMasteryService._correctness(attempt=attempt, max_score=Decimal(10)) is None


def test_rebuild_projection_orders_and_decays_historical_evidence() -> None:
    mastery = SimpleNamespace(
        weighted_correct=Decimal(9),
        weighted_wrong=Decimal(9),
        effective_sample_size=Decimal(18),
        lifetime_correct_weight=Decimal(9),
        lifetime_wrong_weight=Decimal(9),
        attempt_count=18,
        correct_count=9,
        last_attempt_time=None,
        model_version='',
        calculated_time=None,
        mastery_score=Decimal('0.5'),
        confidence_score=Decimal(0),
        state='unknown',
    )
    snapshots = [
        SimpleNamespace(
            correctness=Decimal(1),
            weight=Decimal(1),
            graded_time=datetime(2026, 7, 21, tzinfo=UTC),
        ),
        SimpleNamespace(
            correctness=Decimal(0),
            weight=Decimal(1),
            graded_time=datetime(2026, 8, 20, tzinfo=UTC),
        ),
    ]

    KnowledgeMasteryService._rebuild_projection(mastery=mastery, snapshots=snapshots)

    assert mastery.weighted_correct == pytest.approx(Decimal('0.5'))
    assert mastery.weighted_wrong == Decimal(1)
    assert mastery.effective_sample_size == pytest.approx(Decimal('1.5'))
    assert mastery.lifetime_correct_weight == Decimal(1)
    assert mastery.lifetime_wrong_weight == Decimal(1)
    assert mastery.attempt_count == 2
    assert mastery.correct_count == 1
    assert mastery.mastery_score == pytest.approx(Decimal('1.5') / Decimal('3.5'))
    assert mastery.state == 'learning'
