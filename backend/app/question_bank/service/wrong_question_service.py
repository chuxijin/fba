#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.model import WrongQuestionBook
from backend.app.question_bank.schema.wrong_question import WrongQuestionChapterCountItem, WrongQuestionStatistics
from backend.app.question_bank.service.study_domain_service import StudyDomainQuestionFilter, study_domain_service
from backend.common.exception import errors
from backend.common.log import log
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

WRONG_QUESTION_STATISTICS_CACHE_TTL = 30


class WrongQuestionService:
    """错题本服务类"""

    @staticmethod
    def _statistics_cache_key(*, user_id: int, study_domain: str | None, group_by: str | None = None) -> str:
        """
        构建错题统计缓存 key

        :param user_id: 用户 ID
        :param study_domain: 学习领域
        :param group_by: 分组方式
        :return:
        """
        domain = study_domain or 'all'
        group = group_by or 'summary'
        return f'qbank:wrong:statistics:{user_id}:{domain}:{group}'

    @staticmethod
    async def _get_cached_statistics(key: str) -> dict | None:
        """
        获取错题统计缓存

        :param key: 缓存 key
        :return:
        """
        try:
            cached = await redis_client.get(key)
        except Exception as e:
            log.warning('读取错题统计缓存失败: {}', e)
            return None

        if not cached:
            return None
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            return None

    @staticmethod
    async def _set_cached_statistics(key: str, data: dict) -> None:
        """
        写入错题统计缓存

        :param key: 缓存 key
        :param data: 缓存数据
        :return:
        """
        try:
            await redis_client.setex(key, WRONG_QUESTION_STATISTICS_CACHE_TTL, json.dumps(data, ensure_ascii=False))
        except Exception as e:
            log.warning('写入错题统计缓存失败: {}', e)

    @staticmethod
    async def _clear_statistics_cache(user_id: int) -> None:
        """
        清理用户错题统计缓存

        :param user_id: 用户 ID
        :return:
        """
        try:
            await redis_client.delete_prefix(f'qbank:wrong:statistics:{user_id}:')
        except Exception as e:
            log.warning('清理错题统计缓存失败: {}', e)

    @staticmethod
    async def _get_study_domain_filter(
        *,
        db: AsyncSession,
        study_domain: str | None,
    ) -> StudyDomainQuestionFilter | None:
        """
        获取领域过滤上下文

        :param db: 数据库会话
        :param study_domain: 领域编码
        :return:
        """
        if study_domain is None:
            return None
        return await study_domain_service.get_question_filter(db=db, code=study_domain)

    @staticmethod
    async def get_wrong_question(*, db: AsyncSession, wrong_id: int, user_id: int) -> WrongQuestionBook:
        """
        获取错题详情

        :param db: 数据库会话
        :param wrong_id: 错题 ID
        :param user_id: 用户 ID
        :return:
        """
        wrong = await wrong_question_dao.get(db=db, wrong_id=wrong_id)
        if not wrong:
            raise errors.NotFoundError(msg='错题不存在')
        if wrong.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此错题')

        return wrong

    @staticmethod
    async def set_pin(*, db: AsyncSession, wrong_id: int, user_id: int, is_pinned: bool) -> int:
        """
        设置错题置顶

        :param db: 数据库会话
        :param wrong_id: 错题 ID
        :param user_id: 用户 ID
        :param is_pinned: 是否置顶
        :return:
        """
        wrong = await wrong_question_dao.get(db=db, wrong_id=wrong_id)
        if not wrong:
            raise errors.NotFoundError(msg='错题不存在')
        if wrong.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此错题')

        count = await wrong_question_dao.set_pin(db=db, wrong_id=wrong_id, is_pinned=is_pinned)
        if count > 0:
            await WrongQuestionService._clear_statistics_cache(user_id)
        return count

    @staticmethod
    async def delete_wrong_question(*, db: AsyncSession, wrong_id: int, user_id: int) -> int:
        """
        从错题本移除题目

        :param db: 数据库会话
        :param wrong_id: 错题 ID
        :param user_id: 用户 ID
        :return:
        """
        wrong = await wrong_question_dao.get(db=db, wrong_id=wrong_id)
        if not wrong:
            raise errors.NotFoundError(msg='错题不存在')
        if wrong.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作此错题')

        count = await wrong_question_dao.delete(db=db, wrong_id=wrong_id)
        if count > 0:
            await WrongQuestionService._clear_statistics_cache(user_id)
        return count

    @staticmethod
    async def delete_wrong_questions(*, db: AsyncSession, wrong_ids: list[int], user_id: int) -> int:
        """
        批量从错题本移除题目

        :param db: 数据库会话
        :param wrong_ids: 错题 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        wrongs = await wrong_question_dao.list_by_ids(db=db, wrong_ids=wrong_ids)
        wrong_map = {wrong.id: wrong for wrong in wrongs}

        for wrong_id in wrong_ids:
            wrong = wrong_map.get(wrong_id)
            if wrong and wrong.user_id != user_id:
                raise errors.ForbiddenError(msg=f'无权操作错题 {wrong_id}')

        deletable_ids = [wrong_id for wrong_id in wrong_ids if wrong_id in wrong_map]
        count = await wrong_question_dao.batch_delete(db=db, wrong_ids=deletable_ids)
        if count > 0:
            await WrongQuestionService._clear_statistics_cache(user_id)
        return count

    @staticmethod
    async def clear_mastered(*, db: AsyncSession, user_id: int) -> int:
        """
        清空用户已掌握的错题

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        count = await wrong_question_dao.clear_mastered(db=db, user_id=user_id)
        if count > 0:
            await WrongQuestionService._clear_statistics_cache(user_id)
        return count

    @staticmethod
    async def get_statistics(
        *,
        db: AsyncSession,
        user_id: int,
        study_domain: str | None = None,
    ) -> WrongQuestionStatistics:
        """
        获取用户的错题本统计数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        cache_key = WrongQuestionService._statistics_cache_key(user_id=user_id, study_domain=study_domain)
        cached = await WrongQuestionService._get_cached_statistics(cache_key)
        if cached:
            return WrongQuestionStatistics(**cached)

        domain_filter = await WrongQuestionService._get_study_domain_filter(db=db, study_domain=study_domain)
        if domain_filter:
            stats = await wrong_question_dao.get_statistics_by_bank_ids(
                db=db,
                user_id=user_id,
                bank_ids=domain_filter.bank_ids,
            )
        else:
            stats = await wrong_question_dao.get_statistics(db=db, user_id=user_id)

        data = WrongQuestionStatistics(
            total_count=stats['total'],
            mastered_count=stats['mastered'],
            unmastered_count=stats['unmastered'],
            pinned_count=stats['pinned'],
            avg_wrong_count=stats['avg_wrong_count'],
            avg_correct_streak=stats['avg_correct_streak'],
        )
        await WrongQuestionService._set_cached_statistics(cache_key, data.model_dump())
        return data

    @staticmethod
    async def get_statistics_with_groups(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str = 'knowledge_point',
        study_domain: str | None = None,
    ) -> dict:
        """
        获取错题统计与树形分组数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param group_by: 分组方式
        :return:
        """
        cache_key = WrongQuestionService._statistics_cache_key(
            user_id=user_id,
            study_domain=study_domain,
            group_by=group_by,
        )
        cached = await WrongQuestionService._get_cached_statistics(cache_key)
        if cached:
            return cached

        from backend.app.question_bank.service.group_tree import (
            build_bank_tree,
            build_kp_tree,
            load_banks_and_chapters,
            load_kp_categories,
        )

        domain_filter = await WrongQuestionService._get_study_domain_filter(db=db, study_domain=study_domain)
        if domain_filter:
            stats = await wrong_question_dao.get_statistics_by_bank_ids(
                db=db,
                user_id=user_id,
                bank_ids=domain_filter.bank_ids,
            )
        else:
            stats = await wrong_question_dao.get_statistics(db=db, user_id=user_id)

        if group_by == 'knowledge_point':
            flat_counts = await wrong_question_dao.get_grouped_by_knowledge_point(db=db, user_id=user_id)
            if domain_filter:
                flat_counts = [
                    item for item in flat_counts
                    if str(item['group_name'] or '').strip() in domain_filter.knowledge_names
                ]
            count_map = {item['group_name']: item['count'] for item in flat_counts}
            categories = await load_kp_categories(db)
            groups = build_kp_tree(categories, count_map)
        else:
            flat_counts = await wrong_question_dao.get_bank_chapter_counts(db=db, user_id=user_id)
            if domain_filter:
                flat_counts = [
                    row for row in flat_counts
                    if row['bank_id'] is not None and int(row['bank_id']) in domain_filter.bank_ids
                ]
            count_map = {(row['bank_id'], row['chapter_id']): row['count'] for row in flat_counts}
            bank_ids = {row['bank_id'] for row in flat_counts if row['bank_id'] is not None}
            chapter_ids = {row['chapter_id'] for row in flat_counts if row['chapter_id'] is not None}
            banks, chapters = await load_banks_and_chapters(db, bank_ids, chapter_ids)
            groups = build_bank_tree(banks, chapters, count_map)

        data = {
            'total_count': stats['total'],
            'mastered_count': stats['mastered'],
            'unmastered_count': stats['unmastered'],
            'pinned_count': stats['pinned'],
            'avg_wrong_count': stats['avg_wrong_count'],
            'avg_correct_streak': stats['avg_correct_streak'],
            'groups': groups,
        }
        await WrongQuestionService._set_cached_statistics(cache_key, data)
        return data

    @staticmethod
    async def get_bank_chapter_counts(
        *,
        db: AsyncSession,
        user_id: int,
        bank_id: int,
    ) -> list[WrongQuestionChapterCountItem]:
        """
        获取当前题库章节错题计数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :return:
        """
        rows = await wrong_question_dao.get_bank_chapter_counts(db=db, user_id=user_id, bank_id=bank_id)
        return [
            WrongQuestionChapterCountItem(
                bank_id=int(row['bank_id']),
                chapter_id=row['chapter_id'],
                count=int(row['count'] or 0),
            )
            for row in rows
            if row['bank_id'] is not None
        ]

    @staticmethod
    async def get_grouped(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str,
        study_domain: str | None = None,
    ) -> list[dict]:
        """
        按题库或知识点分组聚合错题数量

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param group_by: 分组方式
        :return:
        """
        domain_filter = await WrongQuestionService._get_study_domain_filter(db=db, study_domain=study_domain)
        if group_by == 'knowledge_point':
            rows = await wrong_question_dao.get_grouped_by_knowledge_point(db=db, user_id=user_id)
            if not domain_filter:
                return rows
            return [
                item for item in rows
                if str(item['group_name'] or '').strip() in domain_filter.knowledge_names
            ]

        rows = await wrong_question_dao.get_grouped_by_bank(db=db, user_id=user_id)
        if not domain_filter:
            return rows
        return [
            item for item in rows
            if item['group_id'] is not None and int(item['group_id']) in domain_filter.bank_ids
        ]

    @staticmethod
    async def answer_correct(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        placement_id: int | None = None,
        mastery_threshold: int = 3,
    ) -> dict:
        """
        错题答对上报

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :param placement_id: 挂载 ID（可选，精确匹配）
        :param mastery_threshold: 连续答对达到此阈值标记为已掌握
        :return:
        """

        if placement_id is not None:
            wrong = await wrong_question_dao.get_by_user_and_question(
                db=db, user_id=user_id, question_id=question_id, placement_id=placement_id,
            )
            wrong_records = [wrong] if wrong else []
        else:
            wrong_records = await wrong_question_dao.list_by_user_and_question(
                db=db, user_id=user_id, question_id=question_id,
            )

        wrong_records = [item for item in wrong_records if item]
        if not wrong_records:
            return {'is_mastered': False, 'correct_streak': 0, 'message': '未找到对应错题记录'}

        practice_time = timezone.now()
        for wrong in wrong_records:
            await wrong_question_dao.increment_correct(
                db=db,
                wrong_id=wrong.id,
                practice_time=practice_time,
                mastery_threshold=mastery_threshold,
            )
            await db.refresh(wrong)

        await WrongQuestionService._clear_statistics_cache(user_id)
        return {
            'is_mastered': all(item.is_mastered for item in wrong_records),
            'correct_streak': max(item.correct_streak for item in wrong_records),
            'affected_count': len(wrong_records),
        }


wrong_question_service = WrongQuestionService()
