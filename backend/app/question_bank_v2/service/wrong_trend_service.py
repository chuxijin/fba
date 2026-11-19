from datetime import date, datetime, time, timedelta
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_wrong_trend import wrong_trend_dao
from backend.app.question_bank_v2.schema.wrong_trend import GetWrongTrend, WrongTrendPoint
from backend.app.question_bank_v2.service.wrong_review_service import wrong_review_service
from backend.common.exception import errors
from backend.core.conf import settings
from backend.utils.timezone import timezone


class WrongTrendService:
    @staticmethod
    async def get_trend(
        *,
        db: AsyncSession,
        user_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
        domain_category_id: int | None = None,
        days: Literal[7, 30] = 7,
    ) -> GetWrongTrend:
        today = timezone.now().date()
        end_date = end_date or today
        start_date = start_date or end_date - timedelta(days=days - 1)
        if start_date > end_date or (end_date - start_date).days > 365 or end_date > today:
            raise errors.RequestError(msg='请选择不晚于今天、开始不晚于结束且最多366天的日期范围')
        domain_ids = await wrong_review_service.resolve_domain_scope(
            db=db,
            user_id=user_id,
            domain_category_id=domain_category_id,
        )

        def midnight(day: date) -> datetime:
            return datetime.combine(day, time.min, tzinfo=timezone.tz_info)

        counts = await wrong_trend_dao.daily_counts(
            db,
            user_id=user_id,
            start=midnight(start_date),
            end=midnight(end_date + timedelta(days=1)),
            today_start=midnight(today),
            today_end=midnight(today + timedelta(days=1)),
            domain_category_ids=domain_ids,
        )
        started = await wrong_trend_dao.coverage_start(db)
        known_from = (timezone.from_datetime(started).date() + timedelta(days=1)) if started else None

        def point(day: date) -> WrongTrendPoint:
            key = day.isoformat()
            return WrongTrendPoint(
                date=day,
                wrong=counts['wrong'].get(key, 0),
                reviewed=counts['reviewed'].get(key, 0),
                mastered=counts['mastered'].get(key, 0) if known_from and day >= known_from else None,
            )

        return GetWrongTrend(
            start_date=start_date,
            end_date=end_date,
            timezone=settings.DATETIME_TIMEZONE,
            mastery_known_from=known_from,
            today=point(today),
            points=[point(start_date + timedelta(days=i)) for i in range((end_date - start_date).days + 1)],
        )


wrong_trend_service = WrongTrendService()
