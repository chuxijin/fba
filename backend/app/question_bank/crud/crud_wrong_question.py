#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from sqlalchemy import bindparam, case, cast, delete, false, func, literal_column, or_, select
from sqlalchemy import update as sa_update
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, noload, selectinload
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import WrongQuestionBook
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.model.question import Question, QuestionPlacement
from backend.common.enums import DataBaseType
from backend.core.conf import settings
from backend.utils.timezone import timezone


class CRUDWrongQuestion(CRUDPlus[WrongQuestionBook]):
    """错题本数据库操作类"""

    async def get(self, db: AsyncSession, wrong_id: int) -> WrongQuestionBook | None:
        """
        获取错题记录详情（预加载 placement → bank / chapter）

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :return:
        """
        stmt = (
            select(WrongQuestionBook)
            .where(WrongQuestionBook.id == wrong_id)
            .options(
                # question 只需 stem / type，阻止自动 selectin 子关系
                joinedload(WrongQuestionBook.question).options(
                    noload(Question.analyses),
                    noload(Question.materials),
                    noload(Question.placements),
                ),
                # placement → bank（阻止 parent selectin）→ chapter
                selectinload(WrongQuestionBook.placement)
                .selectinload(QuestionPlacement.bank)
                .options(
                    noload(QuestionBank.parent),
                ),
                selectinload(WrongQuestionBook.placement).selectinload(QuestionPlacement.chapter),
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_user_and_question(
        self, db: AsyncSession, user_id: int, question_id: int, placement_id: int | None = None
    ) -> WrongQuestionBook | None:
        """
        获取用户特定题目的错题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :param placement_id: 挂载 ID
        :return:
        """
        filters: dict = {'user_id': user_id, 'question_id': question_id}
        if placement_id is not None:
            filters['placement_id'] = placement_id

        return await self.select_model_by_column(db, **filters)

    async def list_by_user_and_question(
        self, db: AsyncSession, user_id: int, question_id: int
    ) -> list[WrongQuestionBook]:
        """
        获取用户同一题目的全部错题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        stmt = (
            select(WrongQuestionBook)
            .where(
                WrongQuestionBook.user_id == user_id,
                WrongQuestionBook.question_id == question_id,
            )
            .order_by(
                WrongQuestionBook.last_wrong_time.desc(),
                WrongQuestionBook.id.desc(),
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_ids(self, db: AsyncSession, wrong_ids: list[int]) -> list[WrongQuestionBook]:
        """
        按 ID 批量查询错题

        :param db: 数据库会话
        :param wrong_ids: 错题 ID 列表
        :return:
        """
        if not wrong_ids:
            return []

        stmt = select(WrongQuestionBook).where(WrongQuestionBook.id.in_(wrong_ids))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def list_by_user_and_questions(
        self, db: AsyncSession, user_id: int, question_ids: list[int]
    ) -> list[WrongQuestionBook]:
        """
        批量查询用户题目对应的错题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids: 题目 ID 列表
        :return:
        """
        if not question_ids:
            return []

        stmt = select(WrongQuestionBook).where(
            WrongQuestionBook.user_id == user_id,
            WrongQuestionBook.question_id.in_(question_ids),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(
        self, db: AsyncSession, user_id: int, is_pinned: bool | None = None
    ) -> list[WrongQuestionBook]:
        """
        获取用户的错题本列表（复用 get_select 保持排序一致）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param is_pinned: 是否置顶
        :return:
        """
        stmt = await self.get_select(user_id=user_id, is_pinned=is_pinned)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        wrong_time: datetime,
        placement_id: int | None = None,
    ) -> WrongQuestionBook:
        """
        创建错题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :param wrong_time: 错误时间
        :param placement_id: 挂载 ID
        :return:
        """
        new_wrong = self.model(
            user_id=user_id,
            question_id=question_id,
            placement_id=placement_id,
            wrong_count=1,
            correct_streak=0,
            first_wrong_time=wrong_time,
            last_wrong_time=wrong_time,
            created_by=user_id,
        )
        db.add(new_wrong)
        await db.flush()
        await db.refresh(new_wrong)
        return new_wrong

    async def increment_wrong(self, db: AsyncSession, wrong_id: int, wrong_time: datetime) -> int:
        """
        增加错误次数（答错时调用，连续做对链归零）

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :param wrong_time: 错误时间
        :return:
        """
        wrong = await self.select_model(db, wrong_id)
        if not wrong:
            return 0

        return await self.update_model(
            db,
            wrong_id,
            {
                'wrong_count': wrong.wrong_count + 1,
                'correct_streak': 0,
                'last_wrong_time': wrong_time,
            },
        )

    async def increment_correct(
        self, db: AsyncSession, wrong_id: int, practice_time: datetime, mastery_threshold: int = 3
    ) -> int:
        """
        增加连续做对次数（答对时调用）

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :param practice_time: 练习时间
        :param mastery_threshold: 连续答对多少次标记为已掌握（已废弃，由 mastery_service 处理）
        :return:
        """
        wrong = await self.select_model(db, wrong_id)
        if not wrong:
            return 0

        new_streak = wrong.correct_streak + 1
        update_data: dict = {'correct_streak': new_streak, 'last_practice_time': practice_time}

        return await self.update_model(db, wrong_id, update_data)

    async def set_pin(self, db: AsyncSession, wrong_id: int, is_pinned: bool) -> int:
        """
        设置置顶状态

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :param is_pinned: 是否置顶
        :return:
        """
        update_data: dict = {'is_pinned': is_pinned}
        if is_pinned:
            update_data['pinned_time'] = timezone.now()
        else:
            update_data['pinned_time'] = None

        return await self.update_model(db, wrong_id, update_data)

    async def delete(self, db: AsyncSession, wrong_id: int) -> int:
        """
        删除错题记录

        :param db: 数据库会话
        :param wrong_id: 错题记录 ID
        :return:
        """
        return await self.delete_model(db, wrong_id)

    async def batch_delete(self, db: AsyncSession, wrong_ids: list[int]) -> int:
        """
        批量删除错题记录

        :param db: 数据库会话
        :param wrong_ids: 错题 ID 列表
        :return:
        """
        if not wrong_ids:
            return 0

        stmt = delete(WrongQuestionBook).where(WrongQuestionBook.id.in_(wrong_ids))
        result = await db.execute(stmt)
        return result.rowcount

    async def batch_create(self, db: AsyncSession, rows: list[dict]) -> None:
        """
        批量创建错题记录

        :param db: 数据库会话
        :param rows: 错题记录列表
        :return:
        """
        if not rows:
            return

        if DataBaseType.postgresql != settings.DATABASE_TYPE:
            for row in rows:
                await self.create(
                    db=db,
                    user_id=row['user_id'],
                    question_id=row['question_id'],
                    wrong_time=row['first_wrong_time'],
                    placement_id=row.get('placement_id'),
                )
            return

        current_time = timezone.now()
        normalized_rows: list[dict] = []
        for row in rows:
            normalized_row = dict(row)
            normalized_row.setdefault('created_time', current_time)
            normalized_rows.append(normalized_row)

        rows_with_placement = [row for row in normalized_rows if row.get('placement_id') is not None]
        rows_without_placement = [row for row in normalized_rows if row.get('placement_id') is None]

        if rows_with_placement:
            stmt = postgresql.insert(WrongQuestionBook).values(rows_with_placement)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=[
                    WrongQuestionBook.user_id,
                    WrongQuestionBook.question_id,
                    WrongQuestionBook.placement_id,
                ],
                index_where=WrongQuestionBook.placement_id.isnot(None),
            )
            await db.execute(stmt)

        if rows_without_placement:
            stmt = postgresql.insert(WrongQuestionBook).values(rows_without_placement)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=[
                    WrongQuestionBook.user_id,
                    WrongQuestionBook.question_id,
                ],
                index_where=WrongQuestionBook.placement_id.is_(None),
            )
            await db.execute(stmt)

        await db.flush()

    async def batch_update(self, db: AsyncSession, rows: list[dict]) -> None:
        """
        批量更新错题记录

        :param db: 数据库会话
        :param rows: 更新数据列表
        :return:
        """
        if not rows:
            return

        stmt = (
            sa_update(WrongQuestionBook.__table__)
            .where(WrongQuestionBook.id == bindparam('filter_wrong_id'))
            .values(
                wrong_count=bindparam('set_wrong_count'),
                correct_streak=bindparam('set_correct_streak'),
                last_wrong_time=bindparam('set_last_wrong_time'),
                last_practice_time=bindparam('set_last_practice_time'),
            )
            .execution_options(synchronize_session=False)
        )
        await db.execute(stmt, rows)
        await db.flush()

    # ============ 聚合统计 ============

    async def get_statistics(self, db: AsyncSession, user_id: int) -> dict[str, int | float]:
        """
        获取用户错题统计概览

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        from backend.app.question_bank.crud.crud_mastery import mastery_dao

        # 获取错题本统计
        stmt = select(
            func.count().label('total'),
            func.sum(case((WrongQuestionBook.is_pinned == True, 1), else_=0)).label('pinned'),  # noqa: E712
            func.avg(WrongQuestionBook.wrong_count).label('avg_wrong_count'),
            func.avg(WrongQuestionBook.correct_streak).label('avg_correct_streak'),
        ).where(WrongQuestionBook.user_id == user_id)

        result = await db.execute(stmt)
        row = result.first()

        # 获取掌握状态统计
        mastery_stats = await mastery_dao.get_stats(db=db, user_id=user_id)

        return {
            'total': row.total or 0,
            'mastered': mastery_stats['mastered'],
            'unmastered': row.total - mastery_stats['mastered'] if row.total else 0,
            'pinned': int(row.pinned or 0),
            'avg_wrong_count': round(float(row.avg_wrong_count or 0), 2),
            'avg_correct_streak': round(float(row.avg_correct_streak or 0), 2),
        }

    async def get_statistics_by_bank_ids(
        self,
        db: AsyncSession,
        user_id: int,
        bank_ids: set[int],
    ) -> dict[str, int | float]:
        """
        按题库范围获取错题统计概览

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_ids: 题库 ID 集合
        :return:
        """
        if not bank_ids:
            return {
                'total': 0,
                'mastered': 0,
                'unmastered': 0,
                'pinned': 0,
                'avg_wrong_count': 0.0,
                'avg_correct_streak': 0.0,
            }

        from backend.app.question_bank.crud.crud_mastery import mastery_dao

        stmt = (
            select(
                func.count().label('total'),
                func.sum(case((WrongQuestionBook.is_pinned == True, 1), else_=0)).label('pinned'),  # noqa: E712
                func.avg(WrongQuestionBook.wrong_count).label('avg_wrong_count'),
                func.avg(WrongQuestionBook.correct_streak).label('avg_correct_streak'),
            )
            .select_from(WrongQuestionBook)
            .join(QuestionPlacement, QuestionPlacement.id == WrongQuestionBook.placement_id)
            .where(
                WrongQuestionBook.user_id == user_id,
                QuestionPlacement.bank_id.in_(bank_ids),
            )
        )
        result = await db.execute(stmt)
        row = result.first()

        # 获取掌握状态统计
        mastery_stats = await mastery_dao.get_stats(db=db, user_id=user_id)

        return {
            'total': row.total or 0,
            'mastered': mastery_stats['mastered'],
            'unmastered': (row.total or 0) - mastery_stats['mastered'],
            'pinned': int(row.pinned or 0),
            'avg_wrong_count': round(float(row.avg_wrong_count or 0), 2),
            'avg_correct_streak': round(float(row.avg_correct_streak or 0), 2),
        }

    async def get_progress_statistics(self, db: AsyncSession, user_id: int) -> dict[str, int]:
        """
        获取用户错题进度统计（今日/近 7 天新增）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_ago = today_start - timedelta(days=7)

        stmt = select(
            func.count().label('total'),
            func.sum(case((WrongQuestionBook.last_wrong_time >= today_start, 1), else_=0)).label('today_new'),
            func.sum(case((WrongQuestionBook.last_wrong_time >= week_ago, 1), else_=0)).label('week_new'),
        ).where(WrongQuestionBook.user_id == user_id)

        result = await db.execute(stmt)
        row = result.first()

        return {
            'total': row.total or 0,
            'today_new': int(row.today_new or 0),
            'week_new': int(row.week_new or 0),
        }

    # ============ 列表查询 ============

    async def get_select(
        self,
        user_id: int,
        is_pinned: bool | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        cat_bank_ids: set[int] | None = None,
        keyword: str | None = None,
        exclude_reviewed: bool | None = None,
        is_mastered: bool | None = None,
    ) -> Select:
        """
        获取错题本列表查询表达式

        :param user_id: 用户 ID
        :param is_pinned: 是否置顶
        :param bank_id: 题库 ID(通过挂载筛选)
        :param chapter_id: 章节 ID(通过挂载筛选)
        :param cat_bank_ids: 分类子树展开后的题库 ID 集合(空集合表示该分类下无题库,直接返回空)
        :param keyword: 关键字搜索(搜索题干)
        :param exclude_reviewed: 排除已复盘的错题
        :param is_mastered: 是否已掌握(基于 study_mastery_status,True=只看已掌握,False=只看未掌握含无记录)
        :return:
        """
        stmt = (
            select(WrongQuestionBook)
            .where(WrongQuestionBook.user_id == user_id)
            .options(
                # question 只需 stem / type，阻止自动 selectin 子关系
                selectinload(WrongQuestionBook.question).options(
                    noload(Question.analyses),
                    noload(Question.materials),
                    noload(Question.placements),
                ),
                # placement → bank（阻止 parent selectin）→ chapter
                selectinload(WrongQuestionBook.placement)
                .selectinload(QuestionPlacement.bank)
                .options(
                    noload(QuestionBank.parent),
                ),
                selectinload(WrongQuestionBook.placement).selectinload(QuestionPlacement.chapter),
            )
        )

        # 子树 bank_ids 显式为空集合 → 当前分类下无题库,直接返回空结果
        if cat_bank_ids is not None and not cat_bank_ids:
            return stmt.where(false())

        if bank_id is not None or chapter_id is not None or cat_bank_ids:
            stmt = stmt.join(
                QuestionPlacement,
                QuestionPlacement.id == WrongQuestionBook.placement_id,
            )
            if bank_id is not None:
                stmt = stmt.where(QuestionPlacement.bank_id == bank_id)
            if chapter_id is not None:
                stmt = stmt.where(QuestionPlacement.chapter_id == chapter_id)
            if cat_bank_ids:
                stmt = stmt.where(QuestionPlacement.bank_id.in_(cat_bank_ids))

        if keyword is not None:
            stmt = stmt.join(
                Question,
                Question.id == WrongQuestionBook.question_id,
            )
            stmt = stmt.where(Question.stem.like(f'%{keyword}%'))

        if is_pinned is not None:
            stmt = stmt.where(WrongQuestionBook.is_pinned == is_pinned)

        # 排除已复盘的错题
        if exclude_reviewed is True:
            from backend.app.question_bank.model.wrong_review import WrongQuestionReview

            reviewed_subq = (
                select(WrongQuestionReview.wrong_book_id)
                .where(WrongQuestionReview.user_id == user_id)
                .where(WrongQuestionReview.wrong_book_id.isnot(None))
                .distinct()
                .scalar_subquery()
            )
            stmt = stmt.where(WrongQuestionBook.id.notin_(reviewed_subq))

        # 是否已掌握(基于 study_mastery_status,按 user_id + question_id 关联)
        if is_mastered is not None:
            from backend.app.question_bank.model.mastery import WrongMasteryStatus

            mastered_subq = (
                select(WrongMasteryStatus.question_id)
                .where(WrongMasteryStatus.user_id == user_id)
                .where(WrongMasteryStatus.question_id.isnot(None))
                .where(WrongMasteryStatus.status == 'mastered')
                .where(WrongMasteryStatus.deleted == 0)
                .distinct()
                .scalar_subquery()
            )
            if is_mastered:
                stmt = stmt.where(WrongQuestionBook.question_id.in_(mastered_subq))
            else:
                stmt = stmt.where(WrongQuestionBook.question_id.notin_(mastered_subq))

        stmt = stmt.order_by(
            WrongQuestionBook.is_pinned.desc(),
            WrongQuestionBook.last_wrong_time.desc(),
        )
        return stmt

    # ============ 分组聚合 ============

    async def get_grouped_by_bank(self, db: AsyncSession, user_id: int) -> list[dict]:
        """
        按题库分组聚合错题数量

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(
                QuestionPlacement.bank_id.label('group_id'),
                QuestionBank.name.label('group_name'),
                func.count().label('count'),
            )
            .select_from(WrongQuestionBook)
            .join(QuestionPlacement, QuestionPlacement.id == WrongQuestionBook.placement_id)
            .join(QuestionBank, QuestionBank.id == QuestionPlacement.bank_id)
            .where(
                WrongQuestionBook.user_id == user_id,
            )
            .group_by(QuestionPlacement.bank_id, QuestionBank.name)
            .order_by(func.count().desc())
        )
        rows = (await db.execute(stmt)).all()
        return [{'group_id': r.group_id, 'group_name': r.group_name, 'count': r.count} for r in rows]

    async def get_grouped_by_knowledge_point(self, db: AsyncSession, user_id: int) -> list[dict]:
        """
        按知识点分组聚合错题数量

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        kp_json = cast(Question.knowledge_point, PGJSONB)
        kp_array = case(
            (func.jsonb_typeof(kp_json) == 'array', kp_json),
            else_=func.jsonb_build_array(kp_json),
        )
        kp_element = func.jsonb_array_elements(kp_array).table_valued('value')
        # 提取知识点名称：纯字符串 elem 或 dict 的 name / label / title 字段
        kp_name = func.coalesce(
            kp_element.c.value.op('->>')(literal_column("'name'")),
            kp_element.c.value.op('->>')(literal_column("'label'")),
            kp_element.c.value.op('->>')(literal_column("'title'")),
            kp_element.c.value.op('#>>')(literal_column("'{}'")),
        ).label('kp_name')

        stmt = (
            select(
                kp_name,
                func.count(func.distinct(WrongQuestionBook.id)).label('count'),
            )
            .select_from(WrongQuestionBook)
            .join(Question, Question.id == WrongQuestionBook.question_id)
            .join(kp_element, literal_column('true'))
            .where(
                WrongQuestionBook.user_id == user_id,
                Question.knowledge_point.isnot(None),
            )
            .group_by(kp_name)
            .having(kp_name.isnot(None))
            .order_by(func.count(func.distinct(WrongQuestionBook.id)).desc())
        )
        rows = (await db.execute(stmt)).all()
        return [{'group_id': None, 'group_name': r.kp_name, 'count': r.count} for r in rows]

    async def get_question_ids(
        self,
        db: AsyncSession,
        user_id: int,
        bank_id: int | None = None,
        bank_ids: list[int] | None = None,
        chapter_id: int | None = None,
        chapter_ids: list[int] | None = None,
        knowledge_point: str | None = None,
        recent_days: int | None = None,
    ) -> list[int]:
        """
        按分组条件获取错题的题目 ID 列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :param bank_ids: 题库 ID 列表
        :param chapter_id: 章节 ID
        :param chapter_ids: 章节 ID 列表
        :param knowledge_point: 知识点名称
        :return:
        """
        stmt = (
            select(WrongQuestionBook.question_id)
            .where(
                WrongQuestionBook.user_id == user_id,
            )
            .order_by(WrongQuestionBook.last_wrong_time.desc())
        )

        has_bank_filter = bank_id is not None or bool(bank_ids)
        if has_bank_filter or chapter_id is not None or chapter_ids:
            stmt = stmt.join(
                QuestionPlacement,
                QuestionPlacement.id == WrongQuestionBook.placement_id,
            )
            if bank_ids:
                stmt = stmt.where(QuestionPlacement.bank_id.in_(bank_ids))
            elif bank_id is not None:
                stmt = stmt.where(QuestionPlacement.bank_id == bank_id)
            if chapter_ids:
                stmt = stmt.where(QuestionPlacement.chapter_id.in_(chapter_ids))
            elif chapter_id is not None:
                stmt = stmt.where(QuestionPlacement.chapter_id == chapter_id)

        if knowledge_point is not None:
            stmt = stmt.join(
                Question,
                Question.id == WrongQuestionBook.question_id,
            )
            kp_col = cast(Question.knowledge_point, PGJSONB)
            stmt = stmt.where(
                or_(
                    kp_col.contains([knowledge_point]),
                    kp_col.contains([{'name': knowledge_point}]),
                    kp_col.contains([{'label': knowledge_point}]),
                    kp_col.contains([{'title': knowledge_point}]),
                )
            )

        if recent_days is not None and recent_days > 0:
            stmt = stmt.where(WrongQuestionBook.last_wrong_time >= timezone.now() - timedelta(days=recent_days))

        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)

    async def get_bank_chapter_counts(
        self,
        db: AsyncSession,
        user_id: int,
        bank_id: int | None = None,
    ) -> list[dict]:
        """
        按 bank_id + chapter_id 分组统计错题数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :return:
        """
        stmt = (
            select(
                QuestionPlacement.bank_id,
                QuestionPlacement.chapter_id,
                func.count().label('count'),
            )
            .select_from(WrongQuestionBook)
            .join(QuestionPlacement, QuestionPlacement.id == WrongQuestionBook.placement_id)
            .where(
                WrongQuestionBook.user_id == user_id,
            )
        )
        if bank_id is not None:
            stmt = stmt.where(QuestionPlacement.bank_id == bank_id)

        stmt = stmt.group_by(QuestionPlacement.bank_id, QuestionPlacement.chapter_id)
        rows = (await db.execute(stmt)).all()
        return [{'bank_id': r.bank_id, 'chapter_id': r.chapter_id, 'count': r.count} for r in rows]


wrong_question_dao: CRUDWrongQuestion = CRUDWrongQuestion(WrongQuestionBook)
