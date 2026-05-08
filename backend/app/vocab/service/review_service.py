#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from fsrs import Card, Rating, Scheduler, State

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_review_log import review_log_dao
from backend.app.vocab.crud.crud_user_word import user_word_dao
from backend.app.vocab.model import VocabUserWord
from backend.app.vocab.schema.review import ReviewForecast, ReviewResult, SubmitReviewParam
from backend.app.vocab.service.checkin_service import checkin_service
from backend.common.exception import errors
from backend.utils.timezone import timezone


class ReviewService:
    """FSRS 复习引擎服务类"""

    def __init__(self) -> None:
        self.scheduler = Scheduler()

    def _db_to_card(self, uw: VocabUserWord) -> Card:
        """
        从数据库记录恢复 FSRS Card 对象

        :param uw: 用户单词记录
        :return:
        """
        card = Card()
        card.state = State(uw.state)
        card.step = uw.step
        card.stability = uw.stability
        card.difficulty = uw.difficulty
        card.due = uw.due
        card.last_review = uw.last_review
        return card

    def _card_to_db_dict(self, card: Card) -> dict:
        """
        将 FSRS Card 对象转为数据库更新字典

        :param card: FSRS Card
        :return:
        """
        return {
            'state': card.state.value,
            'step': card.step,
            'stability': card.stability,
            'difficulty': card.difficulty,
            'due': card.due,
            'last_review': card.last_review,
        }

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
        :param obj: 复习参数
        :return:
        """
        # 获取或创建用户单词状态
        uw = await user_word_dao.get_by_user_and_word(db, user_id, obj.word_id)
        is_new = uw is None

        if uw is None:
            now = timezone.now()
            uw = await user_word_dao.create_model(
                db,
                {
                    'user_id': user_id,
                    'word_id': obj.word_id,
                    'state': State.Learning.value,
                    'step': 0,
                    'due': now,
                },
                commit=False,
            )
            await db.flush()

        # 构建 Card 并执行 FSRS 调度
        card = self._db_to_card(uw)
        rating = Rating(obj.rating)
        now = timezone.now()
        new_card, _ = self.scheduler.review_card(card, rating, now)

        # 记录复习前的状态
        old_state = uw.state

        # 更新用户单词状态
        update_data = self._card_to_db_dict(new_card)
        await user_word_dao.update_model(db, uw.id, update_data, commit=False)

        # 写入复习日志
        await review_log_dao.create_model(
            db,
            {
                'user_id': user_id,
                'word_id': obj.word_id,
                'rating': obj.rating,
                'state': old_state,
                'review_mode': obj.review_mode,
                'duration_ms': obj.duration_ms,
                'reviewed_at': now,
            },
            commit=False,
        )

        await db.commit()

        # 触发打卡更新
        await checkin_service.update_daily_progress(
            db=db,
            user_id=user_id,
            is_new_word=is_new,
            duration_ms=obj.duration_ms,
        )

        return ReviewResult(
            next_due=new_card.due,
            new_state=new_card.state.value,
            stability=new_card.stability,
            difficulty=new_card.difficulty,
        )

    async def get_review_forecast(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        word_id: int,
    ) -> ReviewForecast:
        """
        预览各评分对应的下次复习时间

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param word_id: 单词 ID
        :return:
        """
        uw = await user_word_dao.get_by_user_and_word(db, user_id, word_id)
        if not uw:
            raise errors.NotFoundError(msg='未找到该单词的学习记录')

        card = self._db_to_card(uw)
        now = timezone.now()

        results: dict[str, datetime] = {}
        for rating in [Rating.Again, Rating.Hard, Rating.Good, Rating.Easy]:
            new_card, _ = self.scheduler.review_card(card, rating, now)
            results[rating.name.lower()] = new_card.due

        return ReviewForecast(**results)


review_service: ReviewService = ReviewService()
