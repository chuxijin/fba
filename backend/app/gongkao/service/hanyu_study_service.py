#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_hanyu_review_log import hanyu_review_log_dao
from backend.app.gongkao.crud.crud_hanyu_user_book import hanyu_user_book_dao
from backend.app.gongkao.crud.crud_hanyu_user_setting import hanyu_user_setting_dao
from backend.app.gongkao.crud.crud_hanyu_user_word import hanyu_user_word_dao
from backend.app.gongkao.crud.crud_hanyu_wordbook import hanyu_wordbook_dao
from backend.app.gongkao.crud.crud_hanyu_wordbook_entry import hanyu_wordbook_entry_dao
from backend.app.gongkao.model import GkHanyu, GkHanyuUserWord, GkHanyuWordbook, GkHanyuWordbookEntry
from backend.app.gongkao.schema.hanyu_review import (
    GetStudySession,
    GetStudyStats,
    HanyuBookProgress,
    StudySessionWord,
)
from backend.utils.timezone import timezone


class HanyuStudyService:
    """汉语学习核心服务类"""

    @staticmethod
    async def _build_session_word(
        db: AsyncSession,
        hanyu: GkHanyu,
        user_word: GkHanyuUserWord | None = None,
        entry: GkHanyuWordbookEntry | None = None,
    ) -> StudySessionWord:
        """
        构建学习会话词语

        :param db: 数据库会话
        :param hanyu: 汉语词汇
        :param user_word: 用户词语状态
        :param entry: 词语本条目（含自定义释义）
        :return:
        """
        return StudySessionWord(
            hanyu_id=hanyu.id,
            word=hanyu.name,
            pinyin=hanyu.pinyin,
            type=hanyu.type,
            meaning=entry.meaning if entry and entry.meaning else None,
            commentary=entry.commentary if entry and entry.commentary else None,
            example=entry.example if entry and entry.example else None,
            definition_info=hanyu.definition_info,
            detail_means=hanyu.detail_means,
            voice=hanyu.voice,
            state=user_word.state if user_word else None,
            stability=user_word.stability if user_word else None,
            difficulty=user_word.difficulty if user_word else None,
            is_new=user_word is None,
            is_starred=user_word.is_starred if user_word else False,
        )

    @staticmethod
    async def get_study_session(
        *,
        db: AsyncSession,
        user_id: int,
        mode: str = 'all',
    ) -> GetStudySession:
        """
        获取今日学习会话

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param mode: 模式: all-所有, learn-仅新词, review-仅复习
        :return:
        """
        setting = await hanyu_user_setting_dao.get_or_create(db, user_id)
        now = timezone.now()

        words: list[StudySessionWord] = []
        review_count = 0
        new_count = 0

        # 1. 待复习词
        if mode in ('all', 'review'):
            review_limit = setting.daily_review_limit if setting.daily_review_limit > 0 else 200
            due_user_words = await hanyu_user_word_dao.get_due_words(db, user_id, now, limit=review_limit)
            for uw in due_user_words:
                stmt = (
                    select(GkHanyu, GkHanyuWordbookEntry)
                    .join(GkHanyuWordbookEntry, GkHanyuWordbookEntry.hanyu_id == GkHanyu.id, isouter=True)
                    .where(GkHanyu.id == uw.hanyu_id)
                )
                result = await db.execute(stmt)
                row = result.first()
                if row:
                    hanyu, entry = row
                    words.append(await HanyuStudyService._build_session_word(db, hanyu, uw, entry))
            review_count = len(words)

        # 2. 新词
        if mode in ('all', 'learn'):
            active_ub = await hanyu_user_book_dao.get_active_book(db, user_id)
            if active_ub:
                needed = setting.daily_new_target
                learned_ids = await hanyu_user_word_dao.get_learned_hanyu_ids(db, user_id)
                entry_hanyu_ids = await hanyu_wordbook_entry_dao.get_hanyu_ids_by_book(db, active_ub.book_id)
                new_hanyu_ids = [hid for hid in entry_hanyu_ids if hid not in learned_ids][:needed]

                for hanyu_id in new_hanyu_ids:
                    stmt = (
                        select(GkHanyu, GkHanyuWordbookEntry)
                        .join(GkHanyuWordbookEntry, GkHanyuWordbookEntry.hanyu_id == GkHanyu.id)
                        .where(
                            GkHanyu.id == hanyu_id,
                            GkHanyuWordbookEntry.wordbook_id == active_ub.book_id,
                        )
                    )
                    result = await db.execute(stmt)
                    row = result.first()
                    if row:
                        hanyu, entry = row
                        words.append(await HanyuStudyService._build_session_word(db, hanyu, None, entry))
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
        state_counts = await hanyu_user_word_dao.count_by_state(db, user_id)
        total_learned = sum(state_counts.values())

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59)
        today_data = await hanyu_review_log_dao.count_today(db, user_id, today_start, today_end)
        today_new_count = await hanyu_user_word_dao.count_today_new(db, user_id, today_start, today_end)
        today_total_unique = today_data.get('total_words', 0)
        today_review_count = max(0, today_total_unique - today_new_count)

        due_words = await hanyu_user_word_dao.get_due_words(db, user_id, now, limit=1000)

        active_ub = await hanyu_user_book_dao.get_active_book(db, user_id)
        active_book_progress = None
        if active_ub:
            book = await hanyu_wordbook_dao.select_model(db, active_ub.book_id)
            if book:
                entry_hanyu_ids = await hanyu_wordbook_entry_dao.get_hanyu_ids_by_book(db, active_ub.book_id)
                learned_ids = await hanyu_user_word_dao.get_learned_hanyu_ids(db, user_id)
                learned_in_book = [hid for hid in entry_hanyu_ids if hid in learned_ids]
                active_book_progress = HanyuBookProgress(
                    book_id=book.id,
                    book_name=book.name,
                    book_cover=book.cover_image,
                    total_words=len(entry_hanyu_ids),
                    learned_words=len(learned_in_book),
                )

        return GetStudyStats(
            total_learned=total_learned,
            total_mastered=state_counts.get(2, 0),
            total_learning=state_counts.get(1, 0) + state_counts.get(3, 0),
            today_new=today_new_count,
            today_review=today_review_count,
            today_duration_seconds=today_data.get('total_duration_ms', 0) // 1000,
            due_count=len(due_words),
            active_book=active_book_progress,
        )


hanyu_study_service: HanyuStudyService = HanyuStudyService()
