#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import cast, delete, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import JSONB as PGJSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import QuestionFavorite
from backend.app.question_bank.model.question import Question, QuestionPlacement
from backend.common.exception import errors


class CRUDQuestionFavorite(CRUDPlus[QuestionFavorite]):
    """题目收藏数据库操作类"""

    async def get(self, db: AsyncSession, favorite_id: int) -> QuestionFavorite | None:
        """
        获取收藏记录详情

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :return:
        """
        return await self.select_model(db, favorite_id)

    async def get_by_user_and_question(
        self, db: AsyncSession, user_id: int, question_id: int
    ) -> QuestionFavorite | None:
        """
        获取用户对特定题目的收藏记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, question_id=question_id)

    async def get_by_user(
        self, db: AsyncSession, user_id: int, folder_name: str | None = None, is_pinned: bool | None = None
    ) -> list[QuestionFavorite]:
        """
        获取用户的收藏列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param folder_name: 收藏夹名称
        :param is_pinned: 是否置顶
        :return:
        """
        filters: dict = {'user_id': user_id}
        if folder_name:
            filters['folder_name'] = folder_name
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned

        stmt = await self.select_order('created_time', 'desc', **filters)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_user_folders(self, db: AsyncSession, user_id: int) -> list[str]:
        """
        获取用户的所有收藏夹名称

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(QuestionFavorite.folder_name)
            .where(QuestionFavorite.user_id == user_id, QuestionFavorite.folder_name.isnot(None))
            .group_by(QuestionFavorite.folder_name)
        )
        result = await db.execute(stmt)
        return [row[0] for row in result.all()]

    async def get_folder_counts(self, db: AsyncSession, user_id: int) -> list[dict[str, str | int | None]]:
        """
        获取用户收藏夹计数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(
                QuestionFavorite.folder_name,
                func.count().label('count'),
            )
            .where(QuestionFavorite.user_id == user_id)
            .group_by(QuestionFavorite.folder_name)
            .order_by(func.count().desc(), QuestionFavorite.folder_name.asc().nullsfirst())
        )
        rows = (await db.execute(stmt)).all()
        return [{'folder_name': row.folder_name, 'count': row.count} for row in rows]

    async def create(
        self,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        placement_id: int | None = None,
        folder_name: str | None = None,
        tags: list[str] | None = None,
        remark: str | None = None,
    ) -> QuestionFavorite:
        """
        创建收藏记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :param placement_id: 挂载 ID（精确指定上下文）
        :param folder_name: 收藏夹名称
        :param tags: 标签列表
        :param remark: 备注
        :return:
        """
        # 查询题目及其挂载信息（用于填充冗余字段）
        stmt = (
            select(Question)
            .options(
                selectinload(Question.placements).joinedload(QuestionPlacement.bank),
                selectinload(Question.placements).joinedload(QuestionPlacement.chapter),
            )
            .where(Question.id == question_id)
        )
        result = await db.execute(stmt)
        question = result.unique().scalars().first()

        if not question:
            raise ValueError(f'题目 ID {question_id} 不存在')

        # 精确匹配 placement_id，未传则降级取第一条
        placement = None
        active_placements = [item for item in question.placements if item.is_active]
        sorted_placements = sorted(active_placements, key=lambda item: (item.sort_order, item.id))
        if placement_id is not None:
            placement = next((p for p in sorted_placements if p.id == placement_id), None)
            if placement is None:
                raise errors.NotFoundError(msg='挂载不存在或不属于当前题目')
        if placement is None and sorted_placements:
            placement = sorted_placements[0]

        # 创建收藏，填充冗余字段
        new_favorite = self.model(
            user_id=user_id,
            question_id=question_id,
            placement_id=placement.id if placement else None,
            folder_name=folder_name,
            tags=tags,
            remark=remark,
            created_by=user_id,
            # 冗余字段（收藏时快照，来自挂载记录）
            bank_id=placement.bank_id if placement else None,
            bank_name=placement.bank.name if placement and placement.bank else None,
            chapter_id=placement.chapter_id if placement else None,
            chapter_name=placement.chapter.name if placement and placement.chapter else None,
        )
        db.add(new_favorite)
        await db.flush()
        await db.refresh(new_favorite)
        return new_favorite

    async def update(
        self,
        db: AsyncSession,
        favorite_id: int,
        folder_name: str | None = None,
        tags: list[str] | None = None,
        remark: str | None = None,
    ) -> int:
        """
        更新收藏记录

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :param folder_name: 收藏夹名称
        :param tags: 标签列表
        :param remark: 备注
        :return:
        """
        update_data: dict = {}
        if folder_name is not None:
            update_data['folder_name'] = folder_name
        if tags is not None:
            update_data['tags'] = tags
        if remark is not None:
            update_data['remark'] = remark

        if not update_data:
            return 0

        return await self.update_model(db, favorite_id, update_data)

    async def delete(self, db: AsyncSession, favorite_id: int) -> int:
        """
        删除收藏记录

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :return:
        """
        return await self.delete_model(db, favorite_id)

    async def set_pin(self, db: AsyncSession, favorite_id: int, is_pinned: bool) -> int:
        """
        设置置顶状态

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :param is_pinned: 是否置顶
        :return:
        """
        update_data: dict = {'is_pinned': is_pinned}
        if is_pinned:
            update_data['pinned_time'] = datetime.now()
        else:
            update_data['pinned_time'] = None

        return await self.update_model(db, favorite_id, update_data)

    async def batch_delete(self, db: AsyncSession, favorite_ids: list[int]) -> int:
        """
        批量删除收藏

        :param db: 数据库会话
        :param favorite_ids: 收藏 ID 列表
        :return:
        """
        if not favorite_ids:
            return 0

        stmt = delete(QuestionFavorite).where(QuestionFavorite.id.in_(favorite_ids))
        result = await db.execute(stmt)
        return result.rowcount

    async def list_by_ids(self, db: AsyncSession, favorite_ids: list[int]) -> list[QuestionFavorite]:
        """
        按 ID 批量查询收藏

        :param db: 数据库会话
        :param favorite_ids: 收藏 ID 列表
        :return:
        """
        if not favorite_ids:
            return []

        stmt = select(QuestionFavorite).where(QuestionFavorite.id.in_(favorite_ids))
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def clear_folder(self, db: AsyncSession, user_id: int, folder_name: str) -> int:
        """
        清空收藏夹

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param folder_name: 收藏夹名称
        :return:
        """
        stmt = delete(QuestionFavorite).where(
            QuestionFavorite.user_id == user_id,
            QuestionFavorite.folder_name == folder_name,
        )
        result = await db.execute(stmt)
        return result.rowcount

    async def check_favorited(self, db: AsyncSession, user_id: int, question_id: int) -> bool:
        """
        检查是否已收藏

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        favorite = await self.get_by_user_and_question(db, user_id, question_id)
        return favorite is not None

    async def get_select(
        self,
        user_id: int | None = None,
        folder_name: str | None = None,
        is_pinned: bool | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
    ) -> Select:
        """
        获取收藏列表查询表达式

        :param user_id: 用户 ID
        :param folder_name: 收藏夹名称
        :param is_pinned: 是否置顶
        :param bank_id: 题库 ID（冗余字段筛选）
        :param chapter_id: 章节 ID（冗余字段筛选）
        :return:
        """
        stmt = select(QuestionFavorite)

        if user_id is not None:
            stmt = stmt.where(QuestionFavorite.user_id == user_id)
        if folder_name:
            stmt = stmt.where(QuestionFavorite.folder_name == folder_name)
        if is_pinned is not None:
            stmt = stmt.where(QuestionFavorite.is_pinned == is_pinned)
        if bank_id is not None:
            stmt = stmt.where(QuestionFavorite.bank_id == bank_id)
        if chapter_id is not None:
            stmt = stmt.where(QuestionFavorite.chapter_id == chapter_id)

        stmt = stmt.order_by(
            QuestionFavorite.is_pinned.desc(),
            QuestionFavorite.created_time.desc(),
        )
        return stmt

    # ============ 分组聚合 ============

    async def get_grouped_by_bank(self, db: AsyncSession, user_id: int) -> list[dict]:
        """
        按题库分组聚合收藏数量（利用冗余字段，无需 JOIN）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(
                QuestionFavorite.bank_id.label('group_id'),
                QuestionFavorite.bank_name.label('group_name'),
                func.count().label('count'),
            )
            .where(
                QuestionFavorite.user_id == user_id,
                QuestionFavorite.bank_id.isnot(None),
            )
            .group_by(QuestionFavorite.bank_id, QuestionFavorite.bank_name)
            .order_by(func.count().desc())
        )
        rows = (await db.execute(stmt)).all()
        return [{'group_id': r.group_id, 'group_name': r.group_name or '未分类', 'count': r.count} for r in rows]

    async def get_grouped_by_knowledge_point(self, db: AsyncSession, user_id: int) -> list[dict]:
        """
        按知识点分组聚合收藏数量

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        kp_element = func.jsonb_array_elements(Question.knowledge_point).table_valued('value')
        kp_name = func.coalesce(
            kp_element.c.value.op('->>')(literal_column("'name'")),
            kp_element.c.value.op('->>')(literal_column("'label'")),
            kp_element.c.value.op('->>')(literal_column("'title'")),
            kp_element.c.value.op('#>>')(literal_column("'{}'")),
        ).label('kp_name')

        stmt = (
            select(
                kp_name,
                func.count(func.distinct(QuestionFavorite.id)).label('count'),
            )
            .select_from(QuestionFavorite)
            .join(Question, Question.id == QuestionFavorite.question_id)
            .join(kp_element, literal_column('true'))
            .where(
                QuestionFavorite.user_id == user_id,
                Question.knowledge_point.isnot(None),
            )
            .group_by(kp_name)
            .having(kp_name.isnot(None))
            .order_by(func.count(func.distinct(QuestionFavorite.id)).desc())
        )
        rows = (await db.execute(stmt)).all()
        return [{'group_id': None, 'group_name': r.kp_name, 'count': r.count} for r in rows]

    async def get_question_ids(
        self, db: AsyncSession, user_id: int,
        bank_id: int | None = None, chapter_id: int | None = None, knowledge_point: str | None = None,
    ) -> list[int]:
        """
        按分组条件获取收藏的题目 ID 列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param knowledge_point: 知识点名称
        :return:
        """
        stmt = (
            select(QuestionFavorite.question_id)
            .where(QuestionFavorite.user_id == user_id)
            .order_by(QuestionFavorite.created_time.desc())
        )

        if bank_id is not None:
            stmt = stmt.where(QuestionFavorite.bank_id == bank_id)

        if chapter_id is not None:
            stmt = stmt.where(QuestionFavorite.chapter_id == chapter_id)

        if knowledge_point is not None:
            stmt = stmt.join(Question, Question.id == QuestionFavorite.question_id)
            kp_col = cast(Question.knowledge_point, PGJSONB)
            stmt = stmt.where(
                or_(
                    kp_col.contains([knowledge_point]),
                    kp_col.contains([{'name': knowledge_point}]),
                    kp_col.contains([{'label': knowledge_point}]),
                    kp_col.contains([{'title': knowledge_point}]),
                )
            )

        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)

    async def get_bank_chapter_counts(self, db: AsyncSession, user_id: int) -> list[dict]:
        """
        按 bank_id + chapter_id 分组统计收藏数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(
                QuestionFavorite.bank_id,
                QuestionFavorite.chapter_id,
                func.count().label('count'),
            )
            .where(QuestionFavorite.user_id == user_id)
            .group_by(QuestionFavorite.bank_id, QuestionFavorite.chapter_id)
        )
        rows = (await db.execute(stmt)).all()
        return [{'bank_id': r.bank_id, 'chapter_id': r.chapter_id, 'count': r.count} for r in rows]


question_favorite_dao: CRUDQuestionFavorite = CRUDQuestionFavorite(QuestionFavorite)
