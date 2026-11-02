"""题库 FSRS 适配；复用公共引擎，独立配置，不影响记忆卡/词汇。"""

from datetime import datetime, timedelta
from importlib.metadata import version
from types import SimpleNamespace
from typing import Any

from backend.common.fsrs import FSRSEngine

# 不以快慢冒充记忆反馈；关闭随机抖动，允许同一作答的反馈从原状态确定性重算。
engine = FSRSEngine(
    desired_retention=0.9,
    enable_fuzzing=False,
    learning_steps=(),
    relearning_steps=(),
)
ALGORITHM = f'fsrs-{version("fsrs")}:retention-0.9:daily:v1'


def first_practice_time(now: datetime) -> datetime:
    """无可靠回测历史时次日验证；这是启动规则，不虚构成功回忆。"""
    return now + timedelta(days=1)


def schedule(data: dict[str, Any], *, rating: int, now: datetime) -> tuple[dict[str, Any], datetime]:
    record = SimpleNamespace(
        state=data.get('state', engine.new_card_defaults(now)['state']),
        step=data.get('step', 0),
        stability=data.get('stability'),
        difficulty=data.get('difficulty'),
        due=datetime.fromisoformat(data['due']) if data.get('due') else now,
        last_review=datetime.fromisoformat(data['last_review']) if data.get('last_review') else None,
    )
    update, result = engine.schedule(record, rating, now=now)
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in update.items()
        if key != 'due'
    }, result.next_due
