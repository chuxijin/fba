#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""today_service 内部纯函数测试（_calc_day_index / _calc_progress）"""

from datetime import date

from backend.app.study_plan.service.today_service import _calc_day_index, _calc_progress


class _StubPlan:
    """轻量 plan 替身，仅暴露 _calc_day_index 需要的字段"""

    def __init__(self, start: date, end: date) -> None:
        self.start_date = start
        self.end_date = end


class _StubItem:
    """轻量 item 替身，仅暴露 _calc_progress 需要的字段"""

    def __init__(self, status: str) -> None:
        self.status = status


class TestCalcDayIndex:
    """day_index / total_days 严格日历计算（D18）"""

    def test_first_day(self) -> None:
        plan = _StubPlan(date(2026, 6, 9), date(2026, 7, 8))
        day, total = _calc_day_index(plan, date(2026, 6, 9))
        assert day == 1
        assert total == 30

    def test_middle_day(self) -> None:
        plan = _StubPlan(date(2026, 6, 9), date(2026, 7, 8))
        day, total = _calc_day_index(plan, date(2026, 6, 18))
        assert day == 10
        assert total == 30

    def test_last_day(self) -> None:
        plan = _StubPlan(date(2026, 6, 9), date(2026, 7, 8))
        day, total = _calc_day_index(plan, date(2026, 7, 8))
        assert day == 30
        assert total == 30

    def test_single_day_plan(self) -> None:
        plan = _StubPlan(date(2026, 6, 9), date(2026, 6, 9))
        day, total = _calc_day_index(plan, date(2026, 6, 9))
        assert day == 1
        assert total == 1


class TestCalcProgress:
    """完成进度计算"""

    def test_empty_items(self) -> None:
        progress = _calc_progress([])
        assert progress.completed == 0
        assert progress.total == 0
        assert progress.percent == 0

    def test_all_completed(self) -> None:
        items = [_StubItem('completed') for _ in range(4)]
        progress = _calc_progress(items)
        assert progress.completed == 4
        assert progress.total == 4
        assert progress.percent == 100

    def test_partial_completed(self) -> None:
        items = [
            _StubItem('completed'),
            _StubItem('completed'),
            _StubItem('pending'),
            _StubItem('in_progress'),
        ]
        progress = _calc_progress(items)
        assert progress.completed == 2
        assert progress.total == 4
        assert progress.percent == 50

    def test_skipped_not_counted_as_completed(self) -> None:
        items = [_StubItem('skipped'), _StubItem('completed')]
        progress = _calc_progress(items)
        assert progress.completed == 1
        assert progress.total == 2
        assert progress.percent == 50

    def test_percent_floor_for_uneven_division(self) -> None:
        items = [_StubItem('completed')] + [_StubItem('pending')] * 2
        progress = _calc_progress(items)
        assert progress.completed == 1
        assert progress.total == 3
        assert progress.percent == 33
