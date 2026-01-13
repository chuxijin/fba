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
        :return: 错题记录
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
        :return: 更新数量
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
        :return: 删除数量
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
        :return: 删除数量
        """
        # 验证所有错题是否属于当前用户
        for wrong_id in wrong_ids:
            wrong = await wrong_question_dao.get(db=db, wrong_id=wrong_id)
            if wrong and wrong.user_id != user_id:
                raise errors.ForbiddenError(msg=f'无权操作错题 {wrong_id}')

        # 批量删除
        count = 0
        for wrong_id in wrong_ids:
            count += await wrong_question_dao.delete(db=db, wrong_id=wrong_id)

        return count

    @staticmethod
    async def clear_mastered(*, db: AsyncSession, user_id: int) -> int:
        """
        清空用户已掌握的错题

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 删除数量
        """
        count = await wrong_question_dao.clear_mastered(db=db, user_id=user_id)
        return count

    @staticmethod
    async def get_statistics(*, db: AsyncSession, user_id: int) -> WrongQuestionStatistics:
        """
        获取用户的错题本统计数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 错题本统计
        """
        all_wrongs = await wrong_question_dao.get_by_user(db=db, user_id=user_id)

        total_count = len(all_wrongs)
        mastered_count = sum(1 for w in all_wrongs if w.is_mastered)
        unmastered_count = total_count - mastered_count
        avg_wrong_count = sum(w.wrong_count for w in all_wrongs) / total_count if total_count > 0 else 0

        stats = WrongQuestionStatistics(
            total_count=total_count,
            mastered_count=mastered_count,
            unmastered_count=unmastered_count,
            avg_wrong_count=round(avg_wrong_count, 2),
        )

        return stats


wrong_question_service = WrongQuestionService()
