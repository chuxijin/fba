#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_hanyu_review_log import hanyu_review_log_dao
from backend.app.gongkao.crud.crud_hanyu_user_word import hanyu_user_word_dao
from backend.app.gongkao.schema.hanyu_review import ReviewForecast, ReviewResult, SubmitReviewParam
from backend.common.exception import errors
from backend.common.fsrs import fsrs_engine
from backend.utils.timezone import timezone


class HanyuReviewService:
    """汉语 FSRS 复习引擎服务类"""

    async def submit_review(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        obj: SubmitReviewParam,
    ) -> ReviewResult:
        """
        提交复习结果

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 提交参数
        :return:
        """
        uw = await hanyu_user_word_dao.get_by_user_and_word(db, user_id, obj.hanyu_id)
        is_new = uw is None
        now = timezone.now()

        if uw is None:
            from backend.app.gongkao.model import GkHanyuUserWord

            defaults = fsrs_engine.new_card_defaults(now)
            uw = GkHanyuUserWord(
                user_id=user_id,
                hanyu_id=obj.hanyu_id,
                **defaults,
            )
            db.add(uw)
            await db.flush()

        update_data, result = fsrs_engine.schedule(uw, obj.rating, now=now)

        old_state = uw.state
        for k, v in update_data.items():
            setattr(uw, k, v)

        from backend.app.gongkao.model import GkHanyuReviewLog

        review_log = GkHanyuReviewLog(
            user_id=user_id,
            hanyu_id=obj.hanyu_id,
            rating=obj.rating,
            state=old_state,
            review_mode=obj.review_mode,
            duration_ms=obj.duration_ms,
            reviewed_at=now,
        )
        db.add(review_log)

        # 联动打卡
        from backend.app.gongkao.service.hanyu_checkin_service import hanyu_checkin_service

        await hanyu_checkin_service.update_daily_progress(
            db=db,
            user_id=user_id,
            is_new_word=is_new,
            duration_ms=obj.duration_ms or 0,
        )

        await db.commit()
        return result

    async def get_review_forecast(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        hanyu_id: int,
    ) -> ReviewForecast:
        """
        预览各评分对应的下次复习时间

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param hanyu_id: 汉语词汇 ID
        :return:
        """
        uw = await hanyu_user_word_dao.get_by_user_and_word(db, user_id, hanyu_id)
        if not uw:
            raise errors.NotFoundError(msg='未找到该词语的学习记录')
        return fsrs_engine.forecast(uw)


hanyu_review_service: HanyuReviewService = HanyuReviewService()
