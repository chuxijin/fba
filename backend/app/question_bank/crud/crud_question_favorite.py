#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import QuestionFavorite


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
        from backend.app.question_bank.model import Question, QuestionPlacement

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
        if placement_id is not None:
            placement = next((p for p in question.placements if p.id == placement_id), None)
        if placement is None and question.placements:
            placement = question.placements[0]

        # 创建收藏，填充冗余字段
        new_favorite = self.model(
            user_id=user_id,
            question_id=question_id,
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


question_favorite_dao: CRUDQuestionFavorite = CRUDQuestionFavorite(QuestionFavorite)
