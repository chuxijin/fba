#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_question_favorite import question_favorite_dao
from backend.app.question_bank.model import QuestionFavorite
from backend.app.question_bank.schema.favorite import (
    CreateQuestionFavoriteParam,
    FavoriteStatistics,
    FolderInfo,
    GetQuestionFavoriteDetail,
)
from backend.common.exception import errors


class FavoriteService:
    """收藏服务类"""

    @staticmethod
    async def create_favorite(
        *, db: AsyncSession, user_id: int, obj: CreateQuestionFavoriteParam
    ) -> QuestionFavorite:
        """
        收藏题目

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 收藏参数
        :return: 收藏记录
        """
        existing = await question_favorite_dao.get_by_user_and_question(
            db=db, user_id=user_id, question_id=obj.question_id
        )
        if existing:
            raise errors.ForbiddenError(msg='该题目已收藏')

        new_favorite = await question_favorite_dao.create(
            db=db,
            user_id=user_id,
            question_id=obj.question_id,
            folder_name=obj.folder_name,
            tags=obj.tags,
            remark=obj.remark,
        )

        return new_favorite

    @staticmethod
    async def delete_favorite_by_question(*, db: AsyncSession, user_id: int, question_id: int) -> int:
        """
        通过题目ID取消收藏

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return: 删除数量
        """
        favorite = await question_favorite_dao.get_by_user_and_question(
            db=db, user_id=user_id, question_id=question_id
        )

        if not favorite:
            return 0

        count = await question_favorite_dao.delete(db=db, favorite_id=favorite.id)
        return count

    @staticmethod
    async def get_favorite(*, db: AsyncSession, favorite_id: int, user_id: int) -> QuestionFavorite:
        """
        获取收藏详情

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :param user_id: 用户 ID
        :return: 收藏记录
        """
        favorite = await question_favorite_dao.get(db=db, favorite_id=favorite_id)
        if not favorite:
            raise errors.NotFoundError(msg='收藏不存在')
        if favorite.user_id != user_id:
            raise errors.AuthorizationError(msg='无权访问此收藏')

        return favorite

    @staticmethod
    async def update_favorite(
        *,
        db: AsyncSession,
        favorite_id: int,
        user_id: int,
        folder_name: str | None,
        tags: list[str] | None,
        remark: str | None,
    ) -> int:
        """
        更新收藏信息

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :param user_id: 用户 ID
        :param folder_name: 收藏夹名称
        :param tags: 标签列表
        :param remark: 备注
        :return: 更新数量
        """
        favorite = await question_favorite_dao.get(db=db, favorite_id=favorite_id)
        if not favorite:
            raise errors.NotFoundError(msg='收藏不存在')
        if favorite.user_id != user_id:
            raise errors.AuthorizationError(msg='无权操作此收藏')

        count = await question_favorite_dao.update(
            db=db, favorite_id=favorite_id, folder_name=folder_name, tags=tags, remark=remark
        )

        return count

    @staticmethod
    async def set_pin(*, db: AsyncSession, favorite_id: int, user_id: int, is_pinned: bool) -> int:
        """
        设置收藏置顶

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :param user_id: 用户 ID
        :param is_pinned: 是否置顶
        :return: 更新数量
        """
        favorite = await question_favorite_dao.get(db=db, favorite_id=favorite_id)
        if not favorite:
            raise errors.NotFoundError(msg='收藏不存在')
        if favorite.user_id != user_id:
            raise errors.AuthorizationError(msg='无权操作此收藏')

        count = await question_favorite_dao.set_pin(db=db, favorite_id=favorite_id, is_pinned=is_pinned)
        return count

    @staticmethod
    async def delete_favorites(*, db: AsyncSession, favorite_ids: list[int], user_id: int) -> int:
        """
        取消收藏（支持单个和批量）

        :param db: 数据库会话
        :param favorite_ids: 收藏 ID 列表
        :param user_id: 用户 ID
        :return: 删除数量
        """
        for favorite_id in favorite_ids:
            favorite = await question_favorite_dao.get(db=db, favorite_id=favorite_id)
            if favorite and favorite.user_id != user_id:
                raise errors.AuthorizationError(msg=f'无权操作收藏 {favorite_id}')

        count = await question_favorite_dao.batch_delete(db=db, favorite_ids=favorite_ids)
        return count

    @staticmethod
    async def check_favorited(*, db: AsyncSession, user_id: int, question_ids: list[int]) -> dict[int, bool]:
        """
        批量检查题目的收藏状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids: 题目 ID 列表
        :return: 字典 {question_id: is_favorited}
        """
        stmt = select(question_favorite_dao.model.question_id).where(
            question_favorite_dao.model.user_id == user_id,
            question_favorite_dao.model.question_id.in_(question_ids),
        )
        result = await db.execute(stmt)
        favorited_ids = {row[0] for row in result.fetchall()}

        status_map = {qid: qid in favorited_ids for qid in question_ids}

        return status_map

    @staticmethod
    async def batch_check_favorites_from_string(
        *, db: AsyncSession, user_id: int, question_ids_str: str
    ) -> dict[int, bool]:
        """
        批量检查题目的收藏状态（从逗号分隔的字符串）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids_str: 题目 ID 列表（逗号分隔）
        :return: 字典 {question_id: is_favorited}
        """
        try:
            ids = [int(qid.strip()) for qid in question_ids_str.split(',') if qid.strip()]
        except ValueError:
            raise errors.BadRequestError(msg='题目 ID 格式错误')

        if not ids:
            return {}

        return await FavoriteService.check_favorited(db=db, user_id=user_id, question_ids=ids)

    @staticmethod
    async def get_statistics(*, db: AsyncSession, user_id: int) -> FavoriteStatistics:
        """
        获取收藏统计数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return: 收藏统计
        """
        all_favorites = await question_favorite_dao.get_by_user(db=db, user_id=user_id)
        folder_names = await question_favorite_dao.get_user_folders(db=db, user_id=user_id)

        folder_stats = []
        for folder_name in folder_names:
            folder_favorites = [f for f in all_favorites if f.folder_name == folder_name]
            folder_stats.append(FolderInfo(folder_name=folder_name, count=len(folder_favorites)))

        no_folder_count = sum(1 for f in all_favorites if not f.folder_name)
        if no_folder_count > 0:
            folder_stats.insert(0, FolderInfo(folder_name='未分组', count=no_folder_count))

        stats = FavoriteStatistics(
            total_count=len(all_favorites), folder_count=len(folder_names), folders=folder_stats
        )

        return stats


favorite_service = FavoriteService()
