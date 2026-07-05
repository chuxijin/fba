from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_review_log import review_log_dao
from backend.app.vocab.crud.crud_user_word import user_word_dao
from backend.app.vocab.schema.review import CreateReviewLogParam, ReviewForecast, ReviewResult, SubmitReviewParam
from backend.app.vocab.schema.user_word import CreateUserWordParam
from backend.app.vocab.service.checkin_service import checkin_service
from backend.common.exception import errors
from backend.common.fsrs import fsrs_engine
from backend.utils.timezone import timezone


class ReviewService:
    """单词 FSRS 复习引擎服务类"""

    async def submit_review(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        obj: SubmitReviewParam,
    ) -> ReviewResult:
        """提交复习结果"""
        uw = await user_word_dao.get_by_user_and_word(db, user_id, obj.word_id)
        is_new = uw is None
        now = timezone.now()

        if uw is None:
            defaults = fsrs_engine.new_card_defaults(now)
            uw = await user_word_dao.create_model(
                db,
                CreateUserWordParam(user_id=user_id, word_id=obj.word_id, **defaults),
                commit=False,
            )
            await db.flush()

        update_data, result = fsrs_engine.schedule(uw, obj.rating, now=now)

        old_state = uw.state
        await user_word_dao.update_model(db, uw.id, update_data, commit=False)

        await review_log_dao.create_model(
            db,
            CreateReviewLogParam(
                user_id=user_id,
                word_id=obj.word_id,
                rating=obj.rating,
                state=old_state,
                review_mode=obj.review_mode,
                duration_ms=obj.duration_ms,
                reviewed_at=now,
            ),
            commit=False,
        )

        await checkin_service.update_daily_progress(
            db=db,
            user_id=user_id,
            is_new_word=is_new,
            duration_ms=obj.duration_ms,
        )

        await db.commit()
        return result

    async def get_review_forecast(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        word_id: int,
    ) -> ReviewForecast:
        """预览各评分对应的下次复习时间"""
        uw = await user_word_dao.get_by_user_and_word(db, user_id, word_id)
        if not uw:
            raise errors.NotFoundError(msg='未找到该单词的学习记录')
        return fsrs_engine.forecast(uw)


review_service: ReviewService = ReviewService()
