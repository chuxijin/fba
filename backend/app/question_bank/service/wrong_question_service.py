#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.app.question_bank.model import WrongQuestionBook
from backend.app.question_bank.schema.wrong_question import WrongQuestionStatistics
from backend.common.exception import errors


class WrongQuestionService:
    """错题本服务类"""

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
        return await wrong_question_dao.batch_delete(db=db, wrong_ids=deletable_ids)

    @staticmethod
    async def clear_mastered(*, db: AsyncSession, user_id: int) -> int:
        """
        清空用户已掌握的错题

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        count = await wrong_question_dao.clear_mastered(db=db, user_id=user_id)
        return count

    @staticmethod
    async def get_statistics(*, db: AsyncSession, user_id: int) -> WrongQuestionStatistics:
        """
        获取用户的错题本统计数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stats = await wrong_question_dao.get_statistics(db=db, user_id=user_id)

        return WrongQuestionStatistics(
            total_count=stats['total'],
            mastered_count=stats['mastered'],
            unmastered_count=stats['unmastered'],
            pinned_count=stats['pinned'],
            avg_wrong_count=stats['avg_wrong_count'],
            avg_correct_streak=stats['avg_correct_streak'],
        )

    @staticmethod
    async def get_statistics_with_groups(
        *, db: AsyncSession, user_id: int, group_by: str = 'knowledge_point'
    ) -> dict:
        """
        获取错题统计与树形分组数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param group_by: 分组方式
        :return:
        """
        from backend.app.question_bank.service.group_tree import (
            build_bank_tree,
            build_kp_tree,
            load_banks_and_chapters,
            load_kp_categories,
        )

        stats = await wrong_question_dao.get_statistics(db=db, user_id=user_id)

        if group_by == 'knowledge_point':
            flat_counts = await wrong_question_dao.get_grouped_by_knowledge_point(db=db, user_id=user_id)
            count_map = {item['group_name']: item['count'] for item in flat_counts}
            categories = await load_kp_categories(db)
            groups = build_kp_tree(categories, count_map)
        else:
            flat_counts = await wrong_question_dao.get_bank_chapter_counts(db=db, user_id=user_id)
            count_map = {(row['bank_id'], row['chapter_id']): row['count'] for row in flat_counts}
            bank_ids = {row['bank_id'] for row in flat_counts if row['bank_id'] is not None}
            chapter_ids = {row['chapter_id'] for row in flat_counts if row['chapter_id'] is not None}
            banks, chapters = await load_banks_and_chapters(db, bank_ids, chapter_ids)
            groups = build_bank_tree(banks, chapters, count_map)

        return {
            'total_count': stats['total'],
            'mastered_count': stats['mastered'],
            'unmastered_count': stats['unmastered'],
            'pinned_count': stats['pinned'],
            'avg_wrong_count': stats['avg_wrong_count'],
            'avg_correct_streak': stats['avg_correct_streak'],
            'groups': groups,
        }

    @staticmethod
    async def get_grouped(*, db: AsyncSession, user_id: int, group_by: str) -> list[dict]:
        """
        按题库或知识点分组聚合错题数量

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param group_by: 分组方式
        :return:
        """
        if group_by == 'knowledge_point':
            return await wrong_question_dao.get_grouped_by_knowledge_point(db=db, user_id=user_id)
        return await wrong_question_dao.get_grouped_by_bank(db=db, user_id=user_id)


wrong_question_service = WrongQuestionService()
