import asyncio

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa

from backend.app.question_bank_v2.service import analytics_service as analytics_module


class TrendAggregateDB:
    def __init__(self, attempts: list[tuple[bool, int | None]]) -> None:
        self.attempts = attempts

    async def execute(self, statement: Any) -> Any:
        # 运行服务实际选取的聚合表达式，验证 NULL 计时不会进入 COUNT(duration_ms)。
        engine = sa.create_engine('sqlite://')
        try:
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    'CREATE TABLE qbank_v2_question_attempt (id INTEGER, is_correct BOOLEAN, duration_ms INTEGER)'
                )
                connection.exec_driver_sql(
                    'INSERT INTO qbank_v2_question_attempt VALUES (?, ?, ?)',
                    [(index, correct, duration) for index, (correct, duration) in enumerate(self.attempts)],
                )
                aggregates = sa.select(*[
                    statement.selected_columns[name]
                    for name in (
                        'attempt_count',
                        'correct_count',
                        'avg_duration_ms',
                        'timed_attempt_count',
                        'total_duration_ms',
                    )
                ])
                row = dict(connection.execute(aggregates).mappings().one())
        finally:
            engine.dispose()
        row.update(practiced_at='2026-10-25', knowledge_point_id=1, module_name='言语理解', sort_order=1)
        return SimpleNamespace(mappings=lambda: SimpleNamespace(all=lambda: [row]))


@pytest.mark.parametrize(
    ('attempts', 'timed_count', 'total_duration', 'average'),
    [
        ([(True, 1000), (False, None), (True, 3000)], 2, 4000, 2.0),
        ([(True, None), (False, None)], 0, None, None),
        ([(True, 0), (False, None)], 1, 0, 0.0),
    ],
)
def test_trends_preserve_timed_denominator_and_raw_duration(
    monkeypatch: pytest.MonkeyPatch,
    attempts: list[tuple[bool, int | None]],
    timed_count: int,
    total_duration: int | None,
    average: float | None,
) -> None:
    monkeypatch.setattr(analytics_module.knowledge_service, 'resolve_domain_category_id', AsyncMock(return_value=1))
    monkeypatch.setattr(analytics_module.knowledge_service, 'resolve_system_ids', AsyncMock(return_value=[1]))
    result = asyncio.run(
        analytics_module.AnalyticsService.get_knowledge_point_trends(
            db=TrendAggregateDB(attempts),
            user_id=1,
        )
    )
    point = result.module_trends[0].points[0]
    assert point.attempt_count == len(attempts)
    assert point.correct_count == sum(correct for correct, _ in attempts)
    assert point.timed_attempt_count == timed_count
    assert point.total_duration_ms == total_duration
    assert point.avg_seconds == average
