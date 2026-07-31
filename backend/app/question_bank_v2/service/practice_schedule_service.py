"""错题重练调度：由客观作答派生等级并推进阶梯间隔。

不使用 FSRS：FSRS 需要用户主观四级评分，而错题场景下「这次做对没有 + 比上次快还是慢」
已经是更可靠的客观信号，且完全可解释、纯整数运算。

复盘不走这里 —— 复盘由用户主动发起，没有到期概念，也不参与推送。
"""

from datetime import datetime, timedelta

# 阶梯间隔（分钟）。等级越高间隔越长，到顶后不再增长。
PRACTICE_LADDER_MINUTES: tuple[int, ...] = (
    10,  # L0 十分钟后，当天再来一次
    30,  # L1 半小时
    60 * 24,  # L2 次日
    60 * 24 * 2,  # L3
    60 * 24 * 4,  # L4
    60 * 24 * 7,  # L5
    60 * 24 * 15,  # L6
    60 * 24 * 30,  # L7
)
MAX_PRACTICE_LEVEL = len(PRACTICE_LADDER_MINUTES) - 1

# 用时对比容差，避免网络与操作抖动导致等级来回跳
DURATION_TOLERANCE = 0.2


def derive_rating(*, is_correct: bool | None, duration_ms: int | None, baseline_ms: int | None) -> int | None:
    """由客观作答派生重练等级

    :param is_correct: 本次判定结果；主观题待批时为空
    :param duration_ms: 本次作答用时
    :param baseline_ms: 上次作答用时基线
    :return: 1 又快又错 / 2 慢且错 / 3 对但吃力 / 4 又快又对；不参与调度时为空
    """
    if is_correct is None:
        return None
    if not duration_ms or not baseline_ms:
        return 3 if is_correct else 1
    if is_correct:
        return 4 if duration_ms <= baseline_ms * (1 - DURATION_TOLERANCE) else 3
    # 用时变长说明仍在调动记忆，比缩短后仍答错（蒙或放弃）更接近想起来
    return 2 if duration_ms >= baseline_ms * (1 + DURATION_TOLERANCE) else 1


def next_practice_level(*, level: int, rating: int) -> int:
    """按派生等级推进阶梯"""
    if rating == 1:
        return 0
    if rating == 2:
        return max(0, level - 1)
    if rating == 3:
        return min(MAX_PRACTICE_LEVEL, level + 1)
    return min(MAX_PRACTICE_LEVEL, level + 2)


def next_practice_time(*, level: int, now: datetime) -> datetime:
    """按阶梯等级计算下次重练时间"""
    return now + timedelta(minutes=PRACTICE_LADDER_MINUTES[min(max(level, 0), MAX_PRACTICE_LEVEL)])
