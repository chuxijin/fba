from datetime import datetime, timedelta
from typing import Any, Protocol, runtime_checkable

from fsrs import Card, Rating, Scheduler, State
from pydantic import Field

from backend.common.schema import SchemaBase
from backend.utils.timezone import timezone

NEW_CARD_STATE = Card().state.value


@runtime_checkable
class FSRSRecord(Protocol):
    """含 FSRS 字段的数据库记录协议"""

    state: int
    step: int | None
    stability: float | None
    difficulty: float | None
    due: datetime | None
    last_review: datetime | None


class ReviewResult(SchemaBase):
    """复习结果"""

    next_due: datetime = Field(..., description='下次复习时间')
    new_state: int = Field(..., description='新卡片状态')
    stability: float | None = Field(None, description='稳定性')
    difficulty: float | None = Field(None, description='难度')


class ReviewForecast(SchemaBase):
    """复习预览"""

    again: datetime = Field(..., description='Again 下次复习时间')
    hard: datetime = Field(..., description='Hard 下次复习时间')
    good: datetime = Field(..., description='Good 下次复习时间')
    easy: datetime = Field(..., description='Easy 下次复习时间')


class FSRSEngine:
    """FSRS 间隔重复调度引擎"""

    def __init__(self) -> None:
        self.scheduler = Scheduler()

    @staticmethod
    def db_to_card(record: FSRSRecord) -> Card:
        """
        从数据库记录恢复 FSRS Card 对象

        :param record: 含 FSRS 字段的数据库记录
        :return:
        """
        card = Card()
        card.state = State(record.state)
        card.step = record.step
        card.stability = record.stability
        card.difficulty = record.difficulty
        if record.due:
            card.due = timezone.to_utc(record.due)
        if record.last_review:
            card.last_review = timezone.to_utc(record.last_review)
        return card

    @staticmethod
    def card_to_db_dict(card: Card) -> dict[str, Any]:
        """
        将 FSRS Card 转为数据库更新字典

        :param card: FSRS Card 对象
        :return:
        """
        return {
            'state': card.state.value,
            'step': card.step,
            'stability': card.stability,
            'difficulty': card.difficulty,
            'due': timezone.from_datetime(card.due) if card.due else None,
            'last_review': timezone.from_datetime(card.last_review) if card.last_review else None,
        }

    def schedule(
        self,
        record: FSRSRecord,
        rating: int,
        *,
        now: datetime | None = None,
    ) -> tuple[dict[str, Any], ReviewResult]:
        """
        对一条记录执行 FSRS 调度

        :param record: 含 FSRS 字段的数据库记录
        :param rating: 评分 (1-4)
        :param now: 当前时间，不传则自动获取
        :return:
        """
        card = self.db_to_card(record)
        now_utc = timezone.to_utc(now or timezone.now())
        new_card, _ = self.scheduler.review_card(card, Rating(rating), now_utc)
        update_data = self.card_to_db_dict(new_card)
        result = ReviewResult(
            next_due=update_data['due'],
            new_state=new_card.state.value,
            stability=new_card.stability,
            difficulty=new_card.difficulty,
        )
        return update_data, result

    def forecast(self, record: FSRSRecord, now: datetime | None = None) -> ReviewForecast:
        """
        预览各评分对应的下次复习时间

        :param record: 含 FSRS 字段的数据库记录
        :param now: 当前时间，不传则自动获取
        :return:
        """
        card = self.db_to_card(record)
        now_utc = timezone.to_utc(now or timezone.now())
        results: dict[str, datetime] = {}
        for rating in [Rating.Again, Rating.Hard, Rating.Good, Rating.Easy]:
            new_card, _ = self.scheduler.review_card(card, rating, now_utc)
            results[rating.name.lower()] = timezone.from_datetime(new_card.due)
        return ReviewForecast(**results)

    def retrievability(self, record: FSRSRecord, at: datetime | None = None) -> float:
        """
        计算卡片在指定时刻的预测回忆概率（FSRS retrievability）

        :param record: 含 FSRS 字段的数据库记录
        :param at: 目标时刻，不传则为当前时间
        :return: 0-1 的回忆概率
        """
        card = self.db_to_card(record)
        if card.last_review is None or card.stability is None:
            return 0.0
        at_utc = timezone.to_utc(at or timezone.now())
        return float(self.scheduler.get_card_retrievability(card, current_datetime=at_utc))

    def retrievability_curve(
        self,
        record: FSRSRecord,
        *,
        days: int = 30,
        step_days: int = 1,
        now: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """
        采样未来 N 天内的回忆概率曲线

        :param record: 含 FSRS 字段的数据库记录
        :param days: 采样总天数
        :param step_days: 采样步长（天）
        :param now: 起点时间
        :return: [{'day': int, 'retrievability': float, 'date': str}, ...]
        """
        card = self.db_to_card(record)
        if card.last_review is None or card.stability is None:
            return [{'day': d, 'retrievability': 0.0, 'date': ''} for d in range(0, days + 1, step_days)]
        start = timezone.to_utc(now or timezone.now())
        points: list[dict[str, Any]] = []
        for d in range(0, days + 1, step_days):
            sample_at = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=d)
            points.append(
                {
                    'day': d,
                    'date': timezone.from_datetime(sample_at).strftime('%Y-%m-%d'),
                    'retrievability': round(float(self.scheduler.get_card_retrievability(card, sample_at)), 4),
                }
            )
        return points

    @staticmethod
    def new_card_defaults(now: datetime) -> dict[str, Any]:
        """
        新卡片的默认值字典

        :param now: 当前时间
        :return:
        """
        return {
            'state': NEW_CARD_STATE,
            'step': 0,
            'due': now,
        }


fsrs_engine: FSRSEngine = FSRSEngine()
