from datetime import datetime
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

    def forecast(self, record: FSRSRecord) -> ReviewForecast:
        """
        预览各评分对应的下次复习时间

        :param record: 含 FSRS 字段的数据库记录
        :return:
        """
        card = self.db_to_card(record)
        now_utc = timezone.to_utc(timezone.now())
        results: dict[str, datetime] = {}
        for rating in [Rating.Again, Rating.Hard, Rating.Good, Rating.Easy]:
            new_card, _ = self.scheduler.review_card(card, rating, now_utc)
            results[rating.name.lower()] = timezone.from_datetime(new_card.due)
        return ReviewForecast(**results)

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
