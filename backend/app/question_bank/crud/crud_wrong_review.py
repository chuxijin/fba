#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model.wrong_review import (
    WrongQuestionCustom,
    WrongQuestionReview,
    WrongReasonTag,
)
from backend.app.question_bank.model.practice import WrongQuestionBook


class CRUDReasonTag(CRUDPlus[WrongReasonTag]):
    """错因标签数据库操作类"""

    async def get(self, db: AsyncSession, tag_id: int) -> WrongReasonTag | None:
        """
        获取标签详情

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :return:
        """
        return await self.select_model(db, tag_id)

    async def list_system_tags(self, db: AsyncSession) -> list[WrongReasonTag]:
        """
        获取系统预设标签列表

        :param db: 数据库会话
        :return:
        """
        return await self.select_order('display_order', 'asc', is_system=True)

    async def list_user_tags(self, db: AsyncSession, user_id: int) -> list[WrongReasonTag]:
        """
        获取用户可见标签列表（系统预设 + 用户自定义）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(WrongReasonTag)
            .where(or_(WrongReasonTag.is_system.is_(True), WrongReasonTag.user_id == user_id))
            .order_by(WrongReasonTag.is_system.desc(), WrongReasonTag.display_order.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user_and_name(self, db: AsyncSession, user_id: int, name: str) -> WrongReasonTag | None:
        """
        按用户和名称查找标签

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param name: 标签名称
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, name=name)

    async def create(self, db: AsyncSession, *, user_id: int, name: str, color: str | None) -> WrongReasonTag:
        """
        创建用户自定义标签

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param name: 标签名称
        :param color: 标签颜色
        :return:
        """
        tag = WrongReasonTag(user_id=user_id, name=name, color=color, is_system=False)
        db.add(tag)
        await db.flush()
        return tag

    async def delete(self, db: AsyncSession, tag_id: int) -> int:
        """
        删除标签

        :param db: 数据库会话
        :param tag_id: 标签 ID
        :return:
        """
        return await self.delete_model(db, tag_id)


class CRUDWrongQuestionCustom(CRUDPlus[WrongQuestionCustom]):
    """自定义错题数据库操作类"""

    async def get(self, db: AsyncSession, custom_id: int) -> WrongQuestionCustom | None:
        """
        获取自定义错题详情

        :param db: 数据库会话
        :param custom_id: 错题 ID
        :return:
        """
        return await self.select_model(db, custom_id)

    async def get_select(
        self,
        user_id: int,
        category_id: int | None = None,
        source: str | None = None,
        keyword: str | None = None,
    ) -> Select:
        """
        获取自定义错题列表查询表达式

        :param user_id: 用户 ID
        :param category_id: 分类 ID
        :param source: 来源
        :param keyword: 关键词搜索
        :return:
        """
        stmt = (
            select(WrongQuestionCustom)
            .where(WrongQuestionCustom.user_id == user_id)
            .order_by(WrongQuestionCustom.created_time.desc())
        )
        if category_id is not None:
            stmt = stmt.where(WrongQuestionCustom.category_id == category_id)
        if source is not None:
            stmt = stmt.where(WrongQuestionCustom.source == source)
        if keyword:
            stmt = stmt.where(WrongQuestionCustom.stem.ilike(f'%{keyword}%'))
        return stmt

    async def create(self, db: AsyncSession, *, user_id: int, **kwargs) -> WrongQuestionCustom:
        """
        创建自定义错题

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        question = WrongQuestionCustom(user_id=user_id, **kwargs)
        db.add(question)
        await db.flush()
        return question

    async def update(self, db: AsyncSession, custom_id: int, data: dict) -> int:
        """
        更新自定义错题

        :param db: 数据库会话
        :param custom_id: 错题 ID
        :param data: 更新字段
        :return:
        """
        return await self.update_model(db, custom_id, data)

    async def batch_delete(self, db: AsyncSession, ids: list[int]) -> int:
        """
        批量删除自定义错题

        :param db: 数据库会话
        :param ids: 错题 ID 列表
        :return:
        """
        stmt = delete(WrongQuestionCustom).where(WrongQuestionCustom.id.in_(ids))
        result = await db.execute(stmt)
        return result.rowcount


class CRUDWrongQuestionReview(CRUDPlus[WrongQuestionReview]):
    """复盘记录数据库操作类"""

    async def get(self, db: AsyncSession, review_id: int) -> WrongQuestionReview | None:
        """
        获取复盘记录详情

        :param db: 数据库会话
        :param review_id: 复盘 ID
        :return:
        """
        return await self.select_model(db, review_id)

    async def get_select(
        self,
        user_id: int,
        review_type: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> Select:
        """
        获取复盘记录列表查询表达式

        :param user_id: 用户 ID
        :param review_type: 复盘类型
        :param start_date: 开始日期
        :param end_date: 结束日期
        :return:
        """
        stmt = (
            select(WrongQuestionReview)
            .where(WrongQuestionReview.user_id == user_id)
            .order_by(WrongQuestionReview.reviewed_time.desc())
        )
        if review_type is not None:
            stmt = stmt.where(WrongQuestionReview.review_type == review_type)
        if start_date is not None:
            stmt = stmt.where(WrongQuestionReview.reviewed_time >= start_date)
        if end_date is not None:
            stmt = stmt.where(WrongQuestionReview.reviewed_time <= end_date)
        return stmt

    async def create(self, db: AsyncSession, *, user_id: int, **kwargs) -> WrongQuestionReview:
        """
        创建复盘记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        review = WrongQuestionReview(user_id=user_id, **kwargs)
        db.add(review)
        await db.flush()
        return review

    async def delete(self, db: AsyncSession, review_id: int) -> int:
        """
        删除复盘记录

        :param db: 数据库会话
        :param review_id: 复盘 ID
        :return:
        """
        return await self.delete_model(db, review_id)

    async def count_by_user(
        self,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
    ) -> int:
        """
        统计用户的总复盘记录数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 领域分类 ID
        :return:
        """
        from sqlalchemy import func

        stmt = select(func.count()).select_from(WrongQuestionReview).where(WrongQuestionReview.user_id == user_id)
        if cat_id is not None:
            stmt = stmt.where(WrongQuestionReview.cat_id == cat_id)

        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_review_summary(
        self,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
        today_start: datetime | None = None,
    ) -> tuple[int, int, dict[int, int], dict[int, int]]:
        """
        一次查询同时获取复盘总数、今日待复盘数、错因标签计数与知识点计数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 领域分类 ID
        :param today_start: 今日零点时间，用于统计今日待复盘数
        :return: (review_total, today_pending, tag_counter, kp_counter)
        """
        stmt = (
            select(WrongQuestionReview.reasons, func.count().over().label('total'))
            .where(WrongQuestionReview.user_id == user_id)
        )
        if cat_id is not None:
            stmt = stmt.where(WrongQuestionReview.cat_id == cat_id)

        # 今日待复盘数：标量子查询，作为附加列一次往返取回
        if today_start is not None:
            reviewed_subq = (
                select(WrongQuestionReview.wrong_book_id)
                .where(WrongQuestionReview.user_id == user_id)
                .where(WrongQuestionReview.wrong_book_id.isnot(None))
                .scalar_subquery()
            )
            today_pending_subq = (
                select(func.count())
                .select_from(WrongQuestionBook)
                .where(WrongQuestionBook.user_id == user_id)
                .where(WrongQuestionBook.last_wrong_time >= today_start)
                .where(WrongQuestionBook.id.notin_(reviewed_subq))
                .scalar_subquery()
                .label('today_pending')
            )
            stmt = stmt.add_columns(today_pending_subq)

        result = await db.execute(stmt)
        rows = result.all()

        review_total = int(rows[0].total) if rows else 0
        today_pending = int(rows[0].today_pending) if rows and today_start is not None else 0
        tag_counter: dict[int, int] = {}
        kp_counter: dict[int, int] = {}

        for row in rows:
            reasons_data = row.reasons
            if reasons_data is None:
                continue
            if not isinstance(reasons_data, dict):
                # 旧格式：数组 [1, 2, 3]
                if isinstance(reasons_data, list):
                    for tag_id in reasons_data:
                        if isinstance(tag_id, int):
                            tag_counter[tag_id] = tag_counter.get(tag_id, 0) + 1
                continue

            # 新格式：字典 {tags: [...], knowledge_points: [...]}
            tag_ids = reasons_data.get('tags', [])
            if isinstance(tag_ids, list):
                for tag_id in tag_ids:
                    if isinstance(tag_id, int):
                        tag_counter[tag_id] = tag_counter.get(tag_id, 0) + 1

            kp_ids = reasons_data.get('knowledge_points', [])
            if isinstance(kp_ids, list):
                for kp in kp_ids:
                    if isinstance(kp, dict):
                        kp_id = kp.get('id')
                        if isinstance(kp_id, int):
                            kp_counter[kp_id] = kp_counter.get(kp_id, 0) + 1
                    elif isinstance(kp, int):
                        kp_counter[kp] = kp_counter.get(kp, 0) + 1

        return review_total, today_pending, tag_counter, kp_counter

    async def get_reason_counts(
        self,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
    ) -> list[tuple[int, int]]:
        """
        统计用户复盘记录中各错因标签的出现次数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 领域分类 ID
        :return:
        """
        stmt = (
            select(WrongQuestionReview.reasons)
            .where(WrongQuestionReview.user_id == user_id)
            .where(WrongQuestionReview.reasons.isnot(None))
        )
        if cat_id is not None:
            stmt = stmt.where(WrongQuestionReview.cat_id == cat_id)

        result = await db.execute(stmt)
        rows = result.scalars().all()
        counter: dict[int, int] = {}
        for reasons_data in rows:
            # 新格式：字典 {tags: [...], knowledge_points: [...]}
            if isinstance(reasons_data, dict):
                tag_ids = reasons_data.get('tags', [])
                if isinstance(tag_ids, list):
                    for tag_id in tag_ids:
                        if isinstance(tag_id, int):
                            counter[tag_id] = counter.get(tag_id, 0) + 1
            # 旧格式：数组 [1, 2, 3]
            elif isinstance(reasons_data, list):
                for tag_id in reasons_data:
                    if isinstance(tag_id, int):
                        counter[tag_id] = counter.get(tag_id, 0) + 1
        return sorted(counter.items(), key=lambda x: x[1], reverse=True)

    async def get_reason_and_kp_counts(
        self,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
    ) -> tuple[dict[int, int], dict[int, int]]:
        """
        一次查询同时统计错因标签和知识点出现次数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 领域分类 ID
        :return: (tag_counter, kp_counter)
        """
        stmt = (
            select(WrongQuestionReview.reasons)
            .where(WrongQuestionReview.user_id == user_id)
            .where(WrongQuestionReview.reasons.isnot(None))
        )
        if cat_id is not None:
            stmt = stmt.where(WrongQuestionReview.cat_id == cat_id)

        result = await db.execute(stmt)
        rows = result.scalars().all()

        tag_counter: dict[int, int] = {}
        kp_counter: dict[int, int] = {}

        for reasons_data in rows:
            if not isinstance(reasons_data, dict):
                # 旧格式：数组 [1, 2, 3]
                if isinstance(reasons_data, list):
                    for tag_id in reasons_data:
                        if isinstance(tag_id, int):
                            tag_counter[tag_id] = tag_counter.get(tag_id, 0) + 1
                continue

            # 新格式：字典 {tags: [...], knowledge_points: [...]}
            tag_ids = reasons_data.get('tags', [])
            if isinstance(tag_ids, list):
                for tag_id in tag_ids:
                    if isinstance(tag_id, int):
                        tag_counter[tag_id] = tag_counter.get(tag_id, 0) + 1

            kp_ids = reasons_data.get('knowledge_points', [])
            if isinstance(kp_ids, list):
                for kp in kp_ids:
                    if isinstance(kp, dict):
                        kp_id = kp.get('id')
                        if isinstance(kp_id, int):
                            kp_counter[kp_id] = kp_counter.get(kp_id, 0) + 1
                    elif isinstance(kp, int):
                        kp_counter[kp] = kp_counter.get(kp, 0) + 1

        return tag_counter, kp_counter

    async def get_knowledge_point_distribution_by_parent(
        self,
        db: AsyncSession,
        user_id: int,
        parent_category_id: int,
        cat_id: int | None = None,
    ) -> list[dict]:
        """
        按父节点获取知识点错题分布

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param parent_category_id: 父分类 ID
        :param cat_id: 领域分类 ID
        :return: [{kp_id, kp_name, wrong_count, percentage}]
        """
        from backend.app.admin.model.category import Category

        # 获取直接子节点
        children_result = await db.execute(
            select(Category.id, Category.name)
            .where(
                Category.parent_id == parent_category_id,
                Category.status.is_(True),
            )
            .order_by(Category.sort_order)
        )
        children = children_result.all()

        if not children:
            return []

        children_map = {c.id: c.name for c in children}
        children_ids = list(children_map.keys())

        # 获取知识点统计（通过合并查询）
        _, kp_counter = await self.get_reason_and_kp_counts(db, user_id, cat_id)

        if not kp_counter:
            return []

        # 查询叶子知识点的 path，按子节点聚合
        leaf_ids = list(kp_counter.keys())
        leaf_paths = await db.execute(
            select(Category.id, Category.path).where(Category.id.in_(leaf_ids))
        )

        counter: dict[int, int] = {cid: 0 for cid in children_map}
        for row in leaf_paths.all():
            leaf_path = row.path or ''
            if not leaf_path:
                continue
            for child_id in children_ids:
                if f'/{child_id}/' in f'/{leaf_path}/':
                    counter[child_id] = counter.get(child_id, 0) + kp_counter.get(row.id, 0)
                    break

        total = sum(counter.values())

        return [
            {
                'kp_id': cid,
                'kp_name': children_map[cid],
                'wrong_count': count,
                'percentage': round(count / total * 100, 1) if total else 0.0,
            }
            for cid, count in sorted(counter.items(), key=lambda x: x[1], reverse=True)
            if count > 0
        ]

    async def get_knowledge_point_counts(
        self,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
    ) -> list[tuple[int, int]]:
        """
        统计用户复盘记录中各知识点的出现次数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param cat_id: 领域分类 ID
        :return:
        """
        stmt = (
            select(WrongQuestionReview.reasons)
            .where(WrongQuestionReview.user_id == user_id)
            .where(WrongQuestionReview.reasons.isnot(None))
        )
        if cat_id is not None:
            stmt = stmt.where(WrongQuestionReview.cat_id == cat_id)

        result = await db.execute(stmt)
        rows = result.scalars().all()
        counter: dict[int, int] = {}
        for reasons_data in rows:
            # 只处理新格式
            if isinstance(reasons_data, dict):
                kp_ids = reasons_data.get('knowledge_points', [])
                if isinstance(kp_ids, list):
                    for kp_id in kp_ids:
                        if isinstance(kp_id, int):
                            counter[kp_id] = counter.get(kp_id, 0) + 1
        return sorted(counter.items(), key=lambda x: x[1], reverse=True)


reason_tag_dao: CRUDReasonTag = CRUDReasonTag(WrongReasonTag)
custom_question_dao: CRUDWrongQuestionCustom = CRUDWrongQuestionCustom(WrongQuestionCustom)
review_dao: CRUDWrongQuestionReview = CRUDWrongQuestionReview(WrongQuestionReview)
