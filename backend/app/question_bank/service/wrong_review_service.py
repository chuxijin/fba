#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.cache.kp_cache import reason_tag_cache
from backend.app.question_bank.crud.crud_wrong_review import (
    custom_question_dao,
    reason_tag_dao,
    review_dao,
)
from backend.app.question_bank.crud.crud_wrong_question import wrong_question_dao
from backend.common.exception import errors


def parse_reasons(reasons: dict | list | None) -> dict:
    """
    解析 reasons 字段，兼容新旧格式

    :param reasons: 原始 reasons 数据
    :return: 统一格式 {'tags': [...], 'knowledge_points': [...]}
    """
    if reasons is None:
        return {'tags': [], 'knowledge_points': []}

    # 新格式：字典
    if isinstance(reasons, dict):
        return {
            'tags': reasons.get('tags', []),
            'knowledge_points': reasons.get('knowledge_points', []),
        }

    # 旧格式：数组（视为 tags）
    if isinstance(reasons, list):
        return {'tags': reasons, 'knowledge_points': []}

    return {'tags': [], 'knowledge_points': []}


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

        async def factory() -> list:
            tags = await reason_tag_dao.list_user_tags(db, user_id)
            # 转为字典列表以便序列化缓存
            return [
                {
                    'id': t.id,
                    'name': t.name,
                    'user_id': t.user_id,
                    'color': t.color,
                    'is_system': t.is_system,
                    'display_order': t.display_order,
                }
                for t in tags
            ]

        result = await reason_tag_cache.get_or_set(user_id, factory=factory)
        return result or []

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
        tag = await reason_tag_dao.create(db, user_id=user_id, name=name, color=color)
        # 失效该用户的标签缓存
        await reason_tag_cache.invalidate(user_id)
        return tag

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
        count = await reason_tag_dao.delete(db, tag_id)
        # 失效该用户的标签缓存
        await reason_tag_cache.invalidate(user_id)
        return count

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
        # 提取 knowledge_points，合并到 reasons 中
        knowledge_points = kwargs.pop('knowledge_points', None)
        if knowledge_points:
            reasons = kwargs.get('reasons')
            if isinstance(reasons, list):
                # 旧格式数组转为新格式字典
                kwargs['reasons'] = {'tags': reasons, 'knowledge_points': knowledge_points}
            elif isinstance(reasons, dict):
                reasons['knowledge_points'] = knowledge_points
            else:
                kwargs['reasons'] = {'tags': [], 'knowledge_points': knowledge_points}

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
        knowledge_points = kwargs.pop('knowledge_points', None) or []
        is_mastered = kwargs.pop('is_mastered', False)

        # 将 reasons 统一转换为新格式字典
        reasons = kwargs.get('reasons')
        if isinstance(reasons, list):
            # 旧格式数组转为新格式字典
            kwargs['reasons'] = {'tags': reasons, 'knowledge_points': knowledge_points}
        elif isinstance(reasons, dict):
            reasons['knowledge_points'] = knowledge_points
        else:
            kwargs['reasons'] = {'tags': [], 'knowledge_points': knowledge_points}

        if review_type == 'auto':
            if not wrong_book_id:
                raise errors.BadRequestError(msg='自动收录错题复盘必须提供 wrong_book_id')
            book = await wrong_question_dao.get(db, wrong_book_id)
            if not book:
                raise errors.NotFoundError(msg='错题记录不存在')
            if book.user_id != user_id:
                raise errors.ForbiddenError(msg='无权复盘该错题')

            # 获取 cat_id：通过 placement -> bank -> cat_id
            if book.placement and book.placement.bank:
                kwargs['cat_id'] = book.placement.bank.cat_id

        elif review_type == 'custom':
            if not custom_question_id:
                raise errors.BadRequestError(msg='自定义错题复盘必须提供 custom_question_id')
            question = await custom_question_dao.get(db, custom_question_id)
            if not question:
                raise errors.NotFoundError(msg='自定义错题不存在')
            if question.user_id != user_id:
                raise errors.ForbiddenError(msg='无权复盘该错题')

            # 直接使用 custom_question 的 category_id
            kwargs['cat_id'] = question.category_id

            # 同步更新 custom 表的 reasons 和 summary
            await custom_question_dao.update(
                db,
                custom_question_id,
                {
                    'reasons': kwargs.get('reasons'),
                    'summary': kwargs.get('summary'),
                },
            )
        else:
            raise errors.BadRequestError(msg='review_type 必须为 auto 或 custom')

        # 创建复盘记录
        review = await review_dao.create(db, user_id=user_id, **kwargs)

        # 更新掌握状态
        from backend.app.question_bank.service.mastery_service import mastery_service

        if is_mastered:
            # 手动标记为已掌握
            if review_type == 'auto' and wrong_book_id:
                await mastery_service.mark_as_mastered(
                    db=db,
                    user_id=user_id,
                    question_id=book.question_id,
                )
            elif review_type == 'custom' and custom_question_id:
                await mastery_service.mark_as_mastered(
                    db=db,
                    user_id=user_id,
                    custom_question_id=custom_question_id,
                )
        else:
            # 普通复盘，只更新复盘次数
            if review_type == 'auto' and wrong_book_id:
                await mastery_service.on_review(
                    db=db,
                    user_id=user_id,
                    question_id=book.question_id,
                )
            elif review_type == 'custom' and custom_question_id:
                await mastery_service.on_review(
                    db=db,
                    user_id=user_id,
                    custom_question_id=custom_question_id,
                )

        return review

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

    @staticmethod
    async def get_review(*, db: AsyncSession, review_id: int, user_id: int):
        """
        获取复盘记录详情

        :param db: 数据库会话
        :param review_id: 复盘 ID
        :param user_id: 用户 ID
        :return:
        """
        review = await review_dao.get(db, review_id)
        if not review:
            raise errors.NotFoundError(msg='复盘记录不存在')
        if review.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问该复盘记录')
        return review

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
        from datetime import datetime, time

        from backend.app.admin.model.category import Category
        from backend.app.question_bank.service.wrong_question_service import wrong_question_service
        from backend.database.db import async_db_session
        from backend.utils.timezone import timezone

        root_id = 109 if kp_cat_id == 1401 else (kp_cat_id or cat_id)
        today_start = datetime.combine(timezone.now().date(), time.min)
        today_start = today_start.replace(tzinfo=timezone.tz_info)

        # 错题统计（走缓存，命中时仅一次 Redis 往返）
        async def _stats() -> tuple[int, int]:
            stats = await wrong_question_service.get_statistics(
                db=db,
                user_id=user_id,
                cat_id=cat_id,
                kp_cat_id=kp_cat_id,
            )
            return stats.total_count, stats.unmastered_count

        # 复盘总数 + 今日待复盘 + 错因/知识点计数（原 count_by_user、_count_today_pending、
        # get_reason_and_kp_counts 三次查询合并为一次）
        async def _review_summary() -> tuple[int, int, dict[int, int], dict[int, int]]:
            async with async_db_session() as sdb:
                return await review_dao.get_review_summary(
                    sdb, user_id, cat_id=cat_id, today_start=today_start
                )

        # 错因标签（与上述互不依赖，独立子会话并行）
        async def _tags() -> list:
            async with async_db_session() as sdb:
                return await reason_tag_dao.list_user_tags(sdb, user_id)

        (total_wrong, unmastered), (total_review, today_pending, tag_counter, kp_counter), tags = (
            await asyncio.gather(_stats(), _review_summary(), _tags())
        )

        # 构建错因分布
        tag_map = {t.id: t for t in tags}
        total_reason_refs = sum(tag_counter.values())
        reason_distribution = []
        for tag_id, count in sorted(tag_counter.items(), key=lambda x: x[1], reverse=True):
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

        # 构建知识点分布：一次查询同时取直接子节点与被标注叶子的 path
        knowledge_point_distribution = []
        if root_id and kp_counter:
            cat_rows = (
                await db.execute(
                    select(Category.id, Category.name, Category.path, Category.parent_id)
                    .where(
                        Category.status.is_(True),
                        or_(Category.parent_id == root_id, Category.id.in_(list(kp_counter.keys()))),
                    )
                )
            ).all()
            children_map: dict[int, str] = {}
            leaf_paths: dict[int, str] = {}
            for row in cat_rows:
                # 直接子节点作为分布维度
                if row.parent_id == root_id and row.name is not None:
                    children_map[row.id] = row.name
                # 被标注的叶子取 path 用于归集
                if row.id in kp_counter and row.path:
                    leaf_paths[row.id] = row.path
            if children_map and leaf_paths:
                children_ids = list(children_map.keys())
                counter: dict[int, int] = {cid: 0 for cid in children_map}
                for leaf_id, leaf_path in leaf_paths.items():
                    if not leaf_path:
                        continue
                    for child_id in children_ids:
                        if f'/{child_id}/' in f'/{leaf_path}/':
                            counter[child_id] = counter.get(child_id, 0) + kp_counter.get(leaf_id, 0)
                            break
                total = sum(counter.values())
                knowledge_point_distribution = [
                    {
                        'kp_id': cid,
                        'kp_name': children_map[cid],
                        'wrong_count': count,
                        'percentage': round(count / total * 100, 1) if total else 0.0,
                    }
                    for cid, count in sorted(counter.items(), key=lambda x: x[1], reverse=True)
                    if count > 0
                ]

        return {
            'total_wrong_count': total_wrong,
            'unmastered_count': unmastered,
            'total_review_count': total_review,
            'today_pending_count': today_pending,
            'reason_distribution': reason_distribution,
            'knowledge_point_distribution': knowledge_point_distribution,
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

    @staticmethod
    async def get_reviewed_questions(
        *,
        db: AsyncSession,
        user_id: int,
        tag_id: int | None = None,
        kp_id: int | None = None,
    ) -> list[dict]:
        """
        获取已复盘的错题列表（按错因标签或知识点筛选）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param tag_id: 错因标签 ID
        :param kp_id: 知识点 ID
        :return:
        """
        return await _get_reviewed_questions(db, user_id, tag_id=tag_id, kp_id=kp_id)

    @staticmethod
    async def get_knowledge_point_distribution(
        *,
        db: AsyncSession,
        user_id: int,
        parent_id: int,
        cat_id: int | None = None,
    ) -> list[dict]:
        """
        获取知识点错题分布（按层级）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param parent_id: 父分类 ID
        :param cat_id: 领域分类 ID
        :return:
        """
        return await _get_knowledge_point_distribution(
            db, user_id, cat_id=cat_id, parent_category_id=parent_id
        )


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


async def _get_knowledge_point_distribution(
    db: AsyncSession,
    user_id: int,
    cat_id: int | None = None,
    kp_cat_id: int | None = None,
    parent_category_id: int | None = None,
) -> list[dict]:
    """
    获取用户复盘记录中标注的知识点分布

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param cat_id: 领域分类 ID（用于过滤复盘记录）
    :param kp_cat_id: 知识点根分类 ID（用于查询知识点树）
    :param parent_category_id: 父分类 ID（None 表示顶层）
    :return:
    """
    if parent_category_id is not None:
        # 按父节点查询子节点分布
        return await review_dao.get_knowledge_point_distribution_by_parent(
            db, user_id, parent_category_id, cat_id
        )

    # 默认显示顶层知识点分布
    # TODO: 临时固定为行测(109)，后续改为动态获取
    root_id = 109 if kp_cat_id == 1401 else (kp_cat_id or cat_id)
    if not root_id:
        return []

    return await review_dao.get_knowledge_point_distribution_by_parent(
        db, user_id, root_id, cat_id
    )


async def _get_bank_distribution(
    db: AsyncSession,
    user_id: int,
    cat_id: int | None = None,
) -> list[dict]:
    """
    获取用户错题按题库的分布统计

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param cat_id: 分类 ID
    :return:
    """
    from collections import Counter

    from sqlalchemy import select

    from backend.app.question_bank.model.bank import QuestionBank
    from backend.app.question_bank.model.practice import WrongQuestionBook
    from backend.app.question_bank.model.question import QuestionPlacement

    # 获取所有错题及其题库信息
    stmt = (
        select(QuestionPlacement.bank_id, QuestionBank.name)
        .select_from(WrongQuestionBook)
        .join(QuestionPlacement, WrongQuestionBook.placement_id == QuestionPlacement.id)
        .join(QuestionBank, QuestionPlacement.bank_id == QuestionBank.id)
        .where(WrongQuestionBook.user_id == user_id)
        .where(WrongQuestionBook.placement_id.isnot(None))
    )

    if cat_id:
        stmt = stmt.where(QuestionBank.cat_id == cat_id)

    result = await db.execute(stmt)
    rows = result.all()

    # 统计题库分布
    bank_counter: Counter[int] = Counter()
    bank_names: dict[int, str] = {}

    for bank_id, bank_name in rows:
        bank_counter[bank_id] += 1
        bank_names[bank_id] = bank_name

    # 取前 10 个
    top_banks = bank_counter.most_common(10)
    total = sum(count for _, count in top_banks)

    return [
        {
            'bank_id': bank_id,
            'bank_name': bank_names.get(bank_id, '未知题库'),
            'wrong_count': count,
            'percentage': round(count / total * 100, 1) if total else 0.0,
        }
        for bank_id, count in top_banks
    ]


async def _get_reviewed_questions(
    db: AsyncSession,
    user_id: int,
    tag_id: int | None = None,
    kp_id: int | None = None,
) -> list[dict]:
    """
    获取已复盘的错题列表（按错因标签或知识点筛选）

    :param db: 数据库会话
    :param user_id: 用户 ID
    :param tag_id: 错因标签 ID
    :param kp_id: 知识点 ID
    :return:
    """
    from sqlalchemy import select

    from backend.app.question_bank.model.question import Question
    from backend.app.question_bank.model.wrong_review import WrongQuestionReview

    # 查询复盘记录
    stmt = (
        select(WrongQuestionReview)
        .where(WrongQuestionReview.user_id == user_id)
        .where(WrongQuestionReview.reasons.isnot(None))
        .order_by(WrongQuestionReview.reviewed_time.desc())
    )

    result = await db.execute(stmt)
    reviews = result.scalars().all()

    # 筛选符合条件的复盘记录
    matched_reviews = []
    for review in reviews:
        if not isinstance(review.reasons, dict):
            continue

        reasons_data = review.reasons
        tags = reasons_data.get('tags', [])
        knowledge_points = reasons_data.get('knowledge_points', [])

        # 按错因标签筛选
        if tag_id is not None:
            if tag_id not in tags:
                continue

        # 按知识点筛选
        if kp_id is not None:
            kp_ids = []
            for kp in knowledge_points:
                if isinstance(kp, dict):
                    kp_ids.append(kp.get('id'))
                elif isinstance(kp, int):
                    kp_ids.append(kp)
            if kp_id not in kp_ids:
                continue

        matched_reviews.append(review)

    # 获取关联的错题信息
    items = []
    for review in matched_reviews[:20]:  # 限制返回前20条
        wrong_book_id = review.wrong_book_id
        question_id = None
        stem = None

        if wrong_book_id:
            # 自动收录的错题
            book = await wrong_question_dao.get(db, wrong_book_id)
            if book:
                question_id = book.question_id
                # 获取题干
                if question_id:
                    question = await db.get(Question, question_id)
                    if question and question.stem:
                        stem = question.stem[:100]
        elif review.custom_question_id:
            # 自定义错题
            custom = await custom_question_dao.get(db, review.custom_question_id)
            if custom:
                question_id = custom.question_id
                stem = custom.stem[:100] if custom.stem else None

        # 对于自定义错题，允许 question_id 为 None
        if review.custom_question_id and not question_id:
            # 使用 custom_question_id 作为标识
            items.append({
                'wrong_book_id': wrong_book_id or 0,
                'question_id': 0,  # 使用 0 表示自定义错题无关联题目
                'custom_question_id': review.custom_question_id,
                'stem': stem or '图片题（无题干）',
                'review_id': review.id,
                'review_time': review.reviewed_time,
                'reasons': review.reasons,
                'summary': review.summary,
            })
        elif question_id:
            items.append({
                'wrong_book_id': wrong_book_id or 0,
                'question_id': question_id,
                'custom_question_id': review.custom_question_id,
                'stem': stem,
                'review_id': review.id,
                'review_time': review.reviewed_time,
                'reasons': review.reasons,
                'summary': review.summary,
            })

    return items


wrong_review_service = WrongReviewService()
