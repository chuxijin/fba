#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_book import book_dao, book_word_dao
from backend.app.vocab.crud.crud_review_log import review_log_dao
from backend.app.vocab.crud.crud_user_book import user_book_dao
from backend.app.vocab.crud.crud_user_setting import user_setting_dao
from backend.app.vocab.crud.crud_user_word import user_word_dao
from backend.app.vocab.crud.crud_word import definition_dao, example_dao, word_dao
from backend.app.vocab.model import VocabWord
from backend.app.vocab.schema.review import GetStudySession, GetStudyStats, StudySessionWord
from backend.app.vocab.schema.word import GetDefinitionDetail, GetExampleDetail, GetWordDetail
from backend.common.exception import errors
from backend.utils.timezone import timezone


class StudyService:
    """学习核心服务类"""

    @staticmethod
    async def _build_word_detail(db: AsyncSession, word: VocabWord) -> GetWordDetail:
        """
        构建单词详情（含释义和例句）

        :param db: 数据库会话
        :param word: 单词实体
        :return:
        """
        definitions = await definition_dao.get_by_word_id(db, word.id)
        examples = await example_dao.get_by_word_id(db, word.id)
        detail = GetWordDetail.model_validate(word)
        detail.definitions = [GetDefinitionDetail.model_validate(d) for d in definitions]
        detail.examples = [GetExampleDetail.model_validate(e) for e in examples]
        return detail

    @staticmethod
    async def get_study_session(*, db: AsyncSession, user_id: int) -> GetStudySession:
        """
        获取今日学习会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        setting = await user_setting_dao.get_or_create(db, user_id)
        now = timezone.now()

        review_limit = setting.daily_review_limit if setting.daily_review_limit > 0 else 200
        due_user_words = await user_word_dao.get_due_words(db, user_id, now, limit=review_limit)

        words: list[StudySessionWord] = []
        for uw in due_user_words:
            word = await word_dao.select_model(db, uw.word_id)
            if word:
                detail = await StudyService._build_word_detail(db, word)
                words.append(StudySessionWord(word=detail, is_new=False, user_word_id=uw.id))

        review_count = len(words)
        new_count = 0

        active_ub = await user_book_dao.get_active_book(db, user_id)
        if active_ub:
            needed = setting.daily_new_target
            learned_ids = await user_word_dao.get_learned_word_ids(db, user_id)
            book_word_ids = await book_word_dao.get_word_ids_by_book(db, active_ub.book_id)
            new_word_ids = [wid for wid in book_word_ids if wid not in learned_ids][:needed]

            for word_id in new_word_ids:
                word = await word_dao.select_model(db, word_id)
                if word:
                    detail = await StudyService._build_word_detail(db, word)
                    words.append(StudySessionWord(word=detail, is_new=True, user_word_id=None))
                    new_count += 1

        return GetStudySession(words=words, new_count=new_count, review_count=review_count, total=len(words))

    @staticmethod
    async def get_study_stats(*, db: AsyncSession, user_id: int) -> GetStudyStats:
        """
        获取学习统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = timezone.now()
        state_counts = await user_word_dao.count_by_state(db, user_id)
        total_learned = sum(state_counts.values())

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)
        today_data = await review_log_dao.count_today(db, user_id, today_start, today_end)
        today_new_count = await user_word_dao.count_today_new(db, user_id, today_start, today_end)
        today_total_unique = today_data.get('total_words', 0)
        today_review_count = max(0, today_total_unique - today_new_count)

        due_words = await user_word_dao.get_due_words(db, user_id, now, limit=1000)
        
        active_ub = await user_book_dao.get_active_book(db, user_id)
        active_book_model = None
        if active_ub:
            book = await book_dao.select_model(db, active_ub.book_id)
            if book:
                from backend.app.vocab.schema.user_book import GetUserBookWithProgress
                book_words = await book_word_dao.get_word_ids_by_book(db, active_ub.book_id)
                learned_ids = await user_word_dao.get_learned_word_ids(db, user_id)
                learned_in_book = [wid for wid in book_words if wid in learned_ids]
                active_book_model = GetUserBookWithProgress(
                    id=active_ub.id,
                    user_id=active_ub.user_id,
                    book_id=active_ub.book_id,
                    is_active=active_ub.is_active,
                    started_at=active_ub.started_at,
                    finished_at=active_ub.finished_at,
                    created_time=active_ub.created_time,
                    book_name=book.name,
                    book_cover=book.cover_image,
                    total_words=len(book_words),
                    learned_words=len(learned_in_book),
                    mastered_words=0  # 如果需要精细可以之后再算，或者这里传 0
                )

        return GetStudyStats(
            total_learned=total_learned,
            total_mastered=state_counts.get(2, 0),
            total_learning=state_counts.get(1, 0) + state_counts.get(3, 0),
            today_new=today_new_count,
            today_review=today_review_count,
            today_duration_seconds=today_data.get('total_duration_ms', 0) // 1000,
            due_count=len(due_words),
            active_book=active_book_model,
        )


study_service: StudyService = StudyService()
