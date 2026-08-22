from __future__ import annotations

from statistics import median
from typing import Any

CALIBRATION_POLICY_VERSION = 'exam-anchor-calibration-v1'


def empty_calibration_policy() -> dict[str, Any]:
    return {
        'policy_version': CALIBRATION_POLICY_VERSION,
        'enabled': False,
        'anchor_count': 0,
        'paper_count': 0,
        'offset': 0.0,
        'applicable_band': [65, 100],
        'max_adjustment': 3.0,
        'reason': 'activation_gate_not_met',
    }


def fit_offset_policy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """仅在有足够跨试卷人工锚点时生成可启用的校准策略。"""
    valid = [
        row
        for row in rows
        if row.get('paper_id') is not None
        and row.get('actual_score') is not None
        and row.get('predicted_score') is not None
    ]
    residuals = [float(row['actual_score']) - float(row['predicted_score']) for row in valid]
    paper_count = len({row['paper_id'] for row in valid})
    if len(valid) < 4 or paper_count < 3:
        policy = empty_calibration_policy()
        policy.update({'anchor_count': len(valid), 'paper_count': paper_count})
        return policy
    direction = sum(1 for value in residuals if value >= 0) / len(residuals)
    if direction < 0.75 and direction > 0.25:
        return empty_calibration_policy() | {'anchor_count': len(valid), 'paper_count': paper_count}
    offset = max(-3.0, min(3.0, median(residuals) * len(valid) / (len(valid) + 8)))
    baseline_mae = sum(abs(value) for value in residuals) / len(residuals)
    held_out_errors: list[float] = []
    for held_out_paper in {row['paper_id'] for row in valid}:
        training = [
            float(row['actual_score']) - float(row['predicted_score'])
            for row in valid
            if row['paper_id'] != held_out_paper
        ]
        if not training:
            continue
        fold_offset = max(-3.0, min(3.0, median(training) * len(training) / (len(training) + 8)))
        held_out_errors.extend(
            abs((float(row['actual_score']) - float(row['predicted_score'])) - fold_offset)
            for row in valid
            if row['paper_id'] == held_out_paper
        )
    calibrated_mae = sum(held_out_errors) / len(held_out_errors) if len(held_out_errors) == len(valid) else baseline_mae
    if calibrated_mae >= baseline_mae:
        policy = empty_calibration_policy()
        policy.update({
            'anchor_count': len(valid),
            'paper_count': paper_count,
            'baseline_mae': round(baseline_mae, 3),
            'calibrated_mae': round(calibrated_mae, 3),
        })
        return policy
    return {
        'policy_version': CALIBRATION_POLICY_VERSION,
        'enabled': True,
        'anchor_count': len(valid),
        'paper_count': paper_count,
        'offset': round(offset, 3),
        'applicable_band': [65, 100],
        'max_adjustment': 3.0,
        'baseline_mae': round(baseline_mae, 3),
        'calibrated_mae': round(calibrated_mae, 3),
        'validation_method': 'leave_one_paper_out',
        'reason': 'validated_high_score_offset',
    }


def apply_score_calibration(score_percent: float, policy: dict[str, Any] | None = None) -> tuple[float, dict[str, Any]]:
    policy = policy or empty_calibration_policy()
    if policy.get('policy_version') != CALIBRATION_POLICY_VERSION:
        policy = empty_calibration_policy() | {'reason': 'unsupported_policy_version'}
    raw_score = round(max(0.0, min(100.0, float(score_percent or 0))), 2)
    adjustment = 0.0
    if policy.get('enabled') and raw_score > 65:
        blend = min(1.0, max(0.0, (raw_score - 65) / 10))
        limit = abs(_number(policy.get('max_adjustment'), 3.0))
        adjustment = max(-limit, min(limit, _number(policy.get('offset'), 0.0))) * blend
    calibrated = round(max(0.0, min(100.0, raw_score + adjustment)), 2)
    return calibrated, {
        'policy_version': policy.get('policy_version') or CALIBRATION_POLICY_VERSION,
        'raw_score': raw_score,
        'adjustment': round(calibrated - raw_score, 2),
        'anchor_count': int(policy.get('anchor_count') or 0),
        'paper_count': int(policy.get('paper_count') or 0),
        'applicable_band': policy.get('applicable_band') or [65, 100],
        'enabled': bool(policy.get('enabled')),
        'reason': policy.get('reason') or 'activation_gate_not_met',
    }


def _number(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
