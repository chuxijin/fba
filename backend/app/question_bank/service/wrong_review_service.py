#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_wrong_review import (
    custom_question_dao,
    reason_tag_dao,
    review_dao,
)
from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.common.exception import errors


class WrongReviewService:
    """错题复盘服务类"""

    # ───────────────── 错因标签 ─────────────────

    @staticmethod
    async def list_tags(*, db: AsyncSession, user_id: int) -> list:
        """
        获取用户可见的错因标签（系统预设 + 用户自定义）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await reason_tag_dao.list_user_tags(db, user_id)

    @staticmethod
    async def create_tag(*, db: AsyncSession, user_id: int, name: str, color: str | None = None):
        """
        创建用户自定义错因标签

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param name: 标签名称
        :param color: 标签颜色
        :return:
        """
        existing = await reason_tag_dao.get_by_user_and_name(db, user_id, name)
        if existing:
            raise errors.BadRequestError(msg=f'标签"{name}"已存在')
        return await reason_tag_dao.create(db, user_id=user_id, name=name, color=color)

    @staticmethod
    async def delete_tag(*, db: AsyncSession, tag_id: int, user_id: int) -> int:
        """
        删除错因标签（仅允许删除自定义标签）

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :param user_id: 用户 ID
        :return:
        """
        tag = await reason_tag_dao.get(db, tag_id)
        if not tag:
            raise errors.NotFoundError(msg='标签不存在')
        if tag.is_system:
            raise errors.ForbiddenError(msg='系统预设标签不可删除')
        if tag.user_id != user_id:
            raise errors.ForbiddenError(msg='无权删除该标签')
        return await reason_tag_dao.delete(db, tag_id)

    # ───────────────── 自定义错题 ─────────────────

    @staticmethod
    async def get_custom_question(*, db: AsyncSession, custom_id: int, user_id: int):
        """
        获取自定义错题详情

        :param db: 数据库会话
        :param custom_id: 错题 ID
        :param user_id: 用户 ID
        :return:
        """
        question = await custom_question_dao.get(db, custom_id)
        if not question:
            raise errors.NotFoundError(msg='自定义错题不存在')
        if question.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问该错题')
        return question

    @staticmethod
    async def list_custom_questions(*, db: AsyncSession, user_id: int, **query):
        """
        获取自定义错题列表查询表达式

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await custom_question_dao.get_select(user_id=user_id, **query)

    @staticmethod
    async def create_custom_question(*, db: AsyncSession, user_id: int, **kwargs):
        """
        创建自定义错题

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await custom_question_dao.create(db, user_id=user_id, **kwargs)

    @staticmethod
    async def update_custom_question(*, db: AsyncSession, custom_id: int, user_id: int, data: dict) -> int:
        """
        更新自定义错题

        :param db: 数据库会话
        :param custom_id: 错题 ID
        :param user_id: 用户 ID
        :param data: 更新字段
        :return:
        """
        question = await custom_question_dao.get(db, custom_id)
        if not question:
            raise errors.NotFoundError(msg='自定义错题不存在')
        if question.user_id != user_id:
            raise errors.ForbiddenError(msg='无权修改该错题')
        return await custom_question_dao.update(db, custom_id, data)

    @staticmethod
    async def delete_custom_questions(*, db: AsyncSession, ids: list[int], user_id: int) -> int:
        """
        批量删除自定义错题

        :param db: 数据库会话
        :param ids: 错题 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        for custom_id in ids:
            question = await custom_question_dao.get(db, custom_id)
            if not question:
                raise errors.NotFoundError(msg=f'自定义错题 {custom_id} 不存在')
            if question.user_id != user_id:
                raise errors.ForbiddenError(msg=f'无权删除错题 {custom_id}')
        return await custom_question_dao.batch_delete(db, ids)

    # ───────────────── 复盘记录 ─────────────────

    @staticmethod
    async def create_review(*, db: AsyncSession, user_id: int, **kwargs):
        """
        创建复盘记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        review_type = kwargs.get('review_type')
        wrong_book_id = kwargs.get('wrong_book_id')
        custom_question_id = kwargs.get('custom_question_id')
        is_mastered = kwargs.pop('is_mastered', None)

        if review_type == 'auto':
            if not wrong_book_id:
                raise errors.BadRequestError(msg='自动收录错题复盘必须提供 wrong_book_id')
            book = await wrong_question_dao.get(db, wrong_book_id)
            if not book:
                raise errors.NotFoundError(msg='错题记录不存在')
            if book.user_id != user_id:
                raise errors.ForbiddenError(msg='无权复盘该错题')
            
            if is_mastered is True:
                await wrong_question_dao.update(db, wrong_book_id, {'is_mastered': True})
                
        elif review_type == 'custom':
            if not custom_question_id:
                raise errors.BadRequestError(msg='自定义错题复盘必须提供 custom_question_id')
            question = await custom_question_dao.get(db, custom_question_id)
            if not question:
                raise errors.NotFoundError(msg='自定义错题不存在')
            if question.user_id != user_id:
                raise errors.ForbiddenError(msg='无权复盘该错题')
        else:
            raise errors.BadRequestError(msg='review_type 必须为 auto 或 custom')

        return await review_dao.create(db, user_id=user_id, **kwargs)


    @staticmethod
    async def list_reviews(*, db: AsyncSession, user_id: int, **query):
        """
        获取复盘记录列表查询表达式

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await review_dao.get_select(user_id=user_id, **query)

    @staticmethod
    async def delete_review(*, db: AsyncSession, review_id: int, user_id: int) -> int:
        """
        删除复盘记录

        :param db: 数据库会话
        :param review_id: 复盘 ID
        :param user_id: 用户 ID
        :return:
        """
        review = await review_dao.get(db, review_id)
        if not review:
            raise errors.NotFoundError(msg='复盘记录不存在')
        if review.user_id != user_id:
            raise errors.ForbiddenError(msg='无权删除该复盘记录')
        return await review_dao.delete(db, review_id)

    # ───────────────── 看板统计 ─────────────────

    @staticmethod
    async def get_dashboard(
        *,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
        kp_cat_id: int | None = None,
    ) -> dict:
        """
        获取复盘看板统计数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 分类 ID
        :param kp_cat_id: 知识点分类 ID
        :return:
        """
        from backend.app.question_bank.service.wrong_question_service import wrong_question_service

        # 错题统计
        stats = await wrong_question_service.get_statistics(
            db=db, user_id=user_id, cat_id=cat_id, kp_cat_id=kp_cat_id
        )
        total_wrong = stats.total_count
        unmastered = stats.unmastered_count

        # 复盘记录总数
        total_review = await review_dao.count_by_user(db, user_id)

        # 今日待复盘数
        today_pending = await _count_today_pending(db, user_id)

        # 错因分布
        reason_counts = await review_dao.get_reason_counts(db, user_id)
        tags = await reason_tag_dao.list_user_tags(db, user_id)
        tag_map = {t.id: t for t in tags}
        total_reason_refs = sum(c for _, c in reason_counts)
        reason_distribution = []
        for tag_id, count in reason_counts:
            tag = tag_map.get(tag_id)
            if not tag:
                continue
            reason_distribution.append({
                'tag_id': tag_id,
                'tag_name': tag.name,
                'color': tag.color,
                'count': count,
                'percentage': round(count / total_reason_refs * 100, 1) if total_reason_refs else 0.0,
            })

        # 错题按题库分布
        wrong_distribution = await _get_wrong_distribution(db, user_id, cat_id, kp_cat_id)

        return {
            'total_wrong_count': total_wrong,
            'unmastered_count': unmastered,
            'total_review_count': total_review,
            'today_pending_count': today_pending,
            'reason_distribution': reason_distribution,
            'wrong_distribution': wrong_distribution,
        }

    @staticmethod
    async def get_today_pending_list(
        *,
        db: AsyncSession,
        user_id: int,
    ) -> list[dict]:
        """
        获取今日待复盘的错题列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await _get_today_pending_list(db, user_id)


async def _count_today_pending(db: AsyncSession, user_id: int) -> int:
    """
    统计今日新增且未复盘的错题数

    :param db: 数据库会话
    :param user_id: 用户 ID
    :return:
    """
    from datetime import datetime, time

    from sqlalchemy import func, select

    from backend.app.question_bank.model.practice import WrongQuestionBook
    from backend.app.question_bank.model.wrong_review import WrongQuestionReview
    from backend.utils.timezone import timezone

    today_start = datetime.combine(timezone.now().date(), time.min)
    today_start = today_start.replace(tzinfo=timezone.tz_info)

    # 今日新增或更新的未掌握错题中，排除已有复盘记录的
    reviewed_subq = (
        select(WrongQuestionReview.wrong_book_id)
        .where(WrongQuestionReview.user_id == user_id)
        .where(WrongQuestionReview.wrong_book_id.isnot(None))
        .correlate()
        .scalar_subquery()
    )
    stmt = (
        select(func.count())
        .select_from(WrongQuestionBook)
        .where(WrongQuestionBook.user_id == user_id)
        .where(WrongQuestionBook.is_mastered.is_(False))
        .where(WrongQuestionBook.last_wrong_time >= today_start)
        .where(WrongQuestionBook.id.notin_(reviewed_subq))
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def _get_today_pending_list(db: AsyncSession, user_id: int) -> list[dict]:
    """
    获取今日待复盘的错题列表

    :param db: 数据库会话
    :param user_id: 用户 ID
    :return:
    """
    from datetime import datetime, time

    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    from backend.app.question_bank.model.practice import WrongQuestionBook
    from backend.app.question_bank.model.question import Question
    from backend.app.question_bank.model.wrong_review import WrongQuestionReview
    from backend.utils.timezone import timezone

    today_start = datetime.combine(timezone.now().date(), time.min)
    today_start = today_start.replace(tzinfo=timezone.tz_info)

    reviewed_subq = (
        select(WrongQuestionReview.wrong_book_id)
        .where(WrongQuestionReview.user_id == user_id)
        .where(WrongQuestionReview.wrong_book_id.isnot(None))
        .correlate()
        .scalar_subquery()
    )
    stmt = (
        select(WrongQuestionBook)
        .options(joinedload(WrongQuestionBook.question).load_only(Question.stem))
        .where(WrongQuestionBook.user_id == user_id)
        .where(WrongQuestionBook.is_mastered.is_(False))
        .where(WrongQuestionBook.last_wrong_time >= today_start)
        .where(WrongQuestionBook.id.notin_(reviewed_subq))
        .order_by(WrongQuestionBook.last_wrong_time.desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    rows = result.scalars().unique().all()
    items = []
    for row in rows:
        stem_text = None
        if row.question and row.question.stem:
            stem_text = row.question.stem[:100]
        items.append({
            'wrong_book_id': row.id,
            'question_id': row.question_id,
            'stem': stem_text,
            'bank_name': row.bank_name,
            'wrong_count': row.wrong_count,
            'last_wrong_time': row.last_wrong_time,
        })
    return items


async def _get_wrong_distribution(
    db: AsyncSession,
    user_id: int,
    cat_id: int | None = None,
    kp_cat_id: int | None = None,
) -> list[dict]:
    """
    获取用户错题按题库的分布统计

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param cat_id: 分类 ID
    :param kp_cat_id: 知识点分类 ID
    :return:
    """
    from sqlalchemy import func, select

    from backend.app.question_bank.model.bank import QuestionBank
    from backend.app.question_bank.model.practice import WrongQuestionBook
    from backend.app.question_bank.model.question import QuestionPlacement

    stmt = (
        select(
            QuestionBank.id.label('bank_id'),
            QuestionBank.name.label('bank_name'),
            func.count(WrongQuestionBook.id).label('wrong_count'),
        )
        .select_from(WrongQuestionBook)
        .join(QuestionPlacement, WrongQuestionBook.placement_id == QuestionPlacement.id)
        .join(QuestionBank, QuestionPlacement.bank_id == QuestionBank.id)
        .where(WrongQuestionBook.user_id == user_id)
        .where(WrongQuestionBook.is_mastered.is_(False))
        .group_by(QuestionBank.id, QuestionBank.name)
        .order_by(func.count(WrongQuestionBook.id).desc())
    )
    if cat_id is not None:
        stmt = stmt.where(QuestionBank.cat_id == cat_id)
    result = await db.execute(stmt)
    rows = result.all()
    total = sum(r.wrong_count for r in rows)
    return [
        {
            'bank_id': r.bank_id,
            'bank_name': r.bank_name,
            'wrong_count': r.wrong_count,
            'percentage': round(r.wrong_count / total * 100, 1) if total else 0.0,
        }
        for r in rows
    ]


wrong_review_service = WrongReviewService()


