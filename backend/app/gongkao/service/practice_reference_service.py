"""外部难度参照，不输出IRT能力。阈值是质量门槛，不是科学性证明。"""

import hashlib
import math
import random

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from backend.app.gongkao.crud.crud_practice_reference import (
    MAX_REFERENCE_QUESTIONS,
    MAX_REFERENCE_RECORDS,
    practice_reference_dao,
)
from backend.app.gongkao.schema.practice_reference import GetReferenceTrends, ReferenceWindowComparison
from backend.common.exception import errors
from backend.utils.timezone import timezone

MIN_COVERAGE = 0.8
MIN_WINDOW_DAYS = 5
MIN_WINDOW_QUESTIONS = 40
MIN_COMMON_SUPPORT = 0.7
BOOTSTRAP_SAMPLES = 500


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def rounded(value: float | None) -> float | None:
    return round(value, 4) if value is not None else None


def reference_probability(row: dict[str, Any]) -> float | None:
    ref = row.get('platform_reference')
    if not isinstance(ref, dict) or ref.get('version') != 'fenbi-global-v1' or not ref.get('captured_at'):
        return None
    value = ref.get('correct_ratio_percent')
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value / 100 if 0 <= value <= 100 else None


def cell(row: dict[str, Any]) -> tuple[str, str, str]:
    p = row['p']
    band = 'below40' if p < 0.4 else '40to70' if p < 0.7 else '70plus'
    return row['module_path'][0], row['question_type'], band


def standardized(rows: list[dict[str, Any]], weights: dict[tuple, float]) -> float | None:
    cells: dict[tuple, list[float]] = defaultdict(list)
    for row in rows:
        cells[cell(row)].append(row['y'] - row['p'])
    if any(not cells[c] for c in weights):
        return None
    return 100 * sum(weight * mean(cells[c]) for c, weight in weights.items())


def compare_windows(rows: list[dict[str, Any]], end_date: date) -> ReferenceWindowComparison:
    current_start = end_date - timedelta(days=27)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=27)
    result = ReferenceWindowComparison(
        previous_start=previous_start,
        previous_end=previous_end,
        current_start=current_start,
        current_end=end_date,
    )
    previous = [r for r in rows if previous_start <= r['date'] <= previous_end]
    current = [r for r in rows if current_start <= r['date'] <= end_date]
    result.previous_questions, result.current_questions = len(previous), len(current)
    days_before, days_after = sorted({r['date'] for r in previous}), sorted({r['date'] for r in current})
    result.previous_days, result.current_days = len(days_before), len(days_after)
    if (
        min(len(previous), len(current)) < MIN_WINDOW_QUESTIONS
        or min(len(days_before), len(days_after)) < MIN_WINDOW_DAYS
    ):
        result.reason = '每个28天窗口至少需要40道有效参照题、5个有数据的自然日'
        return result
    cells_before: dict[tuple, int] = defaultdict(int)
    cells_after: dict[tuple, int] = defaultdict(int)
    for row in previous:
        cells_before[cell(row)] += 1
    for row in current:
        cells_after[cell(row)] += 1
    # 小格子不作稳定结论。相同的一组权重用于前后窗，避免模块构成变化制造趋势。
    shared = {c for c in cells_before.keys() & cells_after.keys() if min(cells_before[c], cells_after[c]) >= 5}
    support_before = sum(cells_before[c] for c in shared) / len(previous)
    support_after = sum(cells_after[c] for c in shared) / len(current)
    result.common_cells = len(shared)
    result.previous_support_percent, result.current_support_percent = (
        rounded(100 * support_before),
        rounded(100 * support_after),
    )
    if not shared or min(support_before, support_after) < MIN_COMMON_SUPPORT:
        result.reason = '前后共同模块、题型和难度分层覆盖不足70%，不作趋势方向判断'
        return result
    raw_weights = {c: (cells_before[c] / len(previous) + cells_after[c] / len(current)) / 2 for c in sorted(shared)}
    total_weight = sum(raw_weights.values())
    weights = {c: w / total_weight for c, w in raw_weights.items()}
    before, after = standardized(previous, weights), standardized(current, weights)
    result.previous_gap_pp, result.current_gap_pp = rounded(before), rounded(after)
    result.change_pp = rounded(after - before)
    clusters_before = {d: [r for r in previous if r['date'] == d] for d in days_before}
    clusters_after = {d: [r for r in current if r['date'] == d] for d in days_after}
    # 按自然日成簇，不能把同卷/同材料题都当成独立伯努利试验。使用固定权重和稳定seed。
    seed = hashlib.sha256(repr([(r['date'], r['identity'], r['y'], r['p']) for r in rows]).encode()).digest()
    rng = random.Random(seed)
    changes = []
    for _ in range(BOOTSTRAP_SAMPLES):
        a = [r for d in rng.choices(days_before, k=len(days_before)) for r in clusters_before[d]]
        b = [r for d in rng.choices(days_after, k=len(days_after)) for r in clusters_after[d]]
        x, y = standardized(a, weights), standardized(b, weights)
        if x is not None and y is not None:
            changes.append(y - x)
    result.bootstrap_samples = len(changes)
    if len(changes) < BOOTSTRAP_SAMPLES * 0.8:
        result.reason = '日期重采样后分层覆盖不稳定，仅展示描述性差值'
        return result
    changes.sort()
    result.interval_low_pp = rounded(changes[int((len(changes) - 1) * 0.025)])
    result.interval_high_pp = rounded(changes[math.ceil((len(changes) - 1) * 0.975)])
    result.status = (
        'reference_up'
        if result.interval_low_pp > 0
        else 'reference_down'
        if result.interval_high_pp < 0
        else 'uncertain'
    )
    result.reason = '相对平台参照的描述性变化；区间按自然日重采样，不是绝对能力或因果结论'
    return result


def identity_history(rows: list[dict[str, Any]]) -> tuple[dict[tuple, date], dict[tuple, set]]:
    first_dates: dict[tuple, date] = {}
    global_states: dict[tuple, set] = defaultdict(set)
    for row in rows:
        if not row.get('content_hash') or not row.get('source_question_key'):
            continue
        identity = row['source_question_key'], row['content_hash']
        first_dates[identity] = min(first_dates.get(identity, row['date']), row['date'])
        global_states[row['date'], identity].add((
            row['status'],
            tuple(row.get('module_path') or []),
            row['question_type'],
        ))
    return first_dates, global_states


def analyze_reference_rows(
    rows: list[dict[str, Any]], *, start_date: date, end_date: date, module_name: str | None = None
) -> tuple[list[dict[str, Any]], ReferenceWindowComparison, list[str]]:
    modules = sorted({r['module_path'][0] for r in rows if r.get('module_path')})
    scoped = [r for r in rows if r.get('module_path') and (not module_name or r['module_path'][0] == module_name)]
    first_dates, global_states = identity_history(rows)
    days: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in scoped:
        days[row['date']].append(row)
    points, comparable = [], []
    daily_valid: dict[date, list[dict[str, Any]]] = {}
    for index in range((end_date - start_date).days + 1):
        day = start_date + timedelta(days=index)
        source = days[day]
        grouped: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
        for row in source:
            # 没有身份指纹的旧/异常数据不进入参照，不能猜题目版本。
            if row.get('content_hash') and row.get('source_question_key'):
                grouped[row['source_question_key'], row['content_hash']].append(row)
        valid, conflicts, duplicates, repeats = [], 0, 0, 0
        for identity, attempts in grouped.items():
            duplicates += len(attempts) - 1
            # 当日答案冲突或归属/类型冲突无法确定首次真实作答，保守排除，不挑最好的一次。
            if len(global_states[day, identity]) != 1:
                conflicts += 1
                continue
            row = attempts[0]
            p = reference_probability(row)
            first_observed = first_dates[identity] == day
            if not first_observed:
                repeats += 1
            if p is not None and row['status'] in {'correct', 'wrong', 'unanswered'}:
                valid.append({
                    **row,
                    'identity': identity,
                    'p': p,
                    'y': int(row['status'] == 'correct'),
                    'first_observed': first_observed,
                })
        unidentified = sum(not r.get('content_hash') or not r.get('source_question_key') for r in source)
        denominator = len(grouped) + unidentified
        coverage = len(valid) / denominator if denominator else None
        gap = 100 * mean([r['y'] - r['p'] for r in valid]) if valid and coverage >= MIN_COVERAGE else None
        # 低覆盖日的有效子样本仍可展示，但不能混入滚动线或前后方向判断。
        daily_valid[day] = valid if gap is not None else []
        comparable.extend(daily_valid[day])
        trailing = [r for d, values in daily_valid.items() if day - timedelta(days=6) <= d <= day for r in values]
        trailing_days = {r['date'] for r in trailing}
        rolling = (
            100 * mean([r['y'] - r['p'] for r in trailing])
            if source and len(trailing) >= 20 and len(trailing_days) >= 2
            else None
        )
        points.append({
            'date': day,
            'total_questions': len(source),
            'raw_accuracy_percent': rounded(100 * sum(r['status'] == 'correct' for r in source) / len(source))
            if source
            else None,
            'comparable_questions': len(valid),
            'reference_coverage_percent': rounded(100 * coverage) if coverage is not None else None,
            'personal_reference_accuracy_percent': rounded(100 * mean([r['y'] for r in valid])) if valid else None,
            'platform_accuracy_percent': rounded(100 * mean([r['p'] for r in valid])) if valid else None,
            'reference_gap_pp': rounded(gap),
            'rolling_gap_pp': rounded(rolling),
            'duplicate_attempts': duplicates,
            'conflicting_questions': conflicts,
            'observed_repeat_questions': repeats,
            'active_records': len({r['record_id'] for r in source}),
        })
    # 跨日重复题也会引入记忆优势：方向比较只使用观察区间内首次出现的同版本题。
    unique = [row for row in comparable if row['first_observed']]
    return points, compare_windows(unique, end_date), modules


class PracticeReferenceService:
    @staticmethod
    async def get_trends(
        *,
        db: Any,
        user_id: int,
        subject_name: str = '行测',
        material_type: str = 'exam',
        start_date: date | None = None,
        end_date: date | None = None,
        module_name: str | None = None,
    ) -> GetReferenceTrends:
        end = end_date or timezone.now().date()
        start = start_date or end - timedelta(days=89)
        if start > end or (end - start).days >= 366:
            raise errors.RequestError(msg='请选取不超过366天且起止顺序正确的日期区间')
        records = await practice_reference_dao.get_records(
            db, user_id=user_id, subject_name=subject_name, material_type=material_type, start_date=start, end_date=end
        )
        if len(records) > MAX_REFERENCE_RECORDS:
            raise errors.RequestError(msg='区间超过1000份报告，请缩短日期；不使用截断数据推断趋势')
        eligible, legacy, incomplete = [], 0, 0
        for record in records:
            snapshot = record.get('source_snapshot') or {}
            if snapshot.get('reference_policy') != 1:
                legacy += 1
            elif record['total_items'] != snapshot.get('summary', {}).get('total_questions'):
                incomplete += 1
            else:
                eligible.append(record)
        questions = await practice_reference_dao.get_questions(
            db, user_id=user_id, session_ids=[r['session_id'] for r in eligible]
        )
        if len(questions) > MAX_REFERENCE_QUESTIONS:
            raise errors.RequestError(msg='区间超过50000题，请缩短日期；不使用截断数据推断趋势')
        actual_counts: dict[int, int] = defaultdict(int)
        malformed = set()
        for q in questions:
            actual_counts[q['session_id']] += 1
            if not q.get('module_path') or q.get('status') not in {'correct', 'wrong', 'unanswered'}:
                malformed.add(q['session_id'])
        complete = [
            r
            for r in eligible
            if actual_counts[r['session_id']] == r['total_items'] and r['session_id'] not in malformed
        ]
        incomplete += len(eligible) - len(complete)
        eligible = complete
        by_session = {r['session_id']: r for r in eligible}
        rows = [
            {
                **q,
                'date': by_session[q['session_id']]['practiced_at'],
                'record_id': by_session[q['session_id']]['record_id'],
            }
            for q in questions
            if q['session_id'] in by_session
        ]
        points, comparison, modules = analyze_reference_rows(
            rows, start_date=start, end_date=end, module_name=module_name
        )
        scoped_ids = {
            r['record_id']
            for r in rows
            if r.get('module_path') and (not module_name or r['module_path'][0] == module_name)
        }
        latest = next(
            (
                r
                for r in reversed(eligible)
                if r['record_id'] in scoped_ids and r['source_snapshot']['summary'].get('platform_reference')
            ),
            None,
        )
        latest_reference = (
            {
                **latest['source_snapshot']['summary']['platform_reference'],
                'record_id': latest['record_id'],
                'record_title': latest['record_title'],
                'practiced_at': latest['practiced_at'],
            }
            if latest
            else None
        )
        return GetReferenceTrends(
            subject_name=subject_name,
            material_type=material_type,
            module_name=module_name,
            start_date=start,
            end_date=end,
            record_count=len(records),
            eligible_records=len(eligible),
            excluded_legacy_records=legacy,
            excluded_incomplete_records=incomplete,
            modules=modules,
            points=points,
            comparison=comparison,
            latest_report_reference=latest_reference,
            warnings=[
                '平台统计人群、时间窗和独立样本量未知；本结果是外部参照，不是IRT能力。',
                '正确率原线含全部归档作答；参照线同日同版本题去重，冲突题排除，覆盖不足80%的日不作判断。',
                '方向比较只用选定区间内首次出现的同版本题；区间前练习历史不完整，不能视为生涯首次见题。',
                '前后各28天按共同模块×题型×正确率分层固定权重；95%描述性区间按自然日成簇重采样。',
                '整卷难度原量表、wrongCount与totalUser不用于能力或有效样本量计算；旧报告不回填。',
            ],
        )


practice_reference_service = PracticeReferenceService()
