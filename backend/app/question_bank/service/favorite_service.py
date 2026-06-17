#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.crud.crud_question import question_statistics_dao
from backend.app.question_bank.crud.crud_question_favorite import question_favorite_dao
from backend.app.question_bank.model import QuestionFavorite, SessionQuestion
from backend.app.question_bank.schema.favorite import (
    CreateQuestionFavoriteParam,
    FavoriteStatistics,
    FolderInfo,
)
from backend.app.question_bank.schema.question import UpdateQuestionStatisticsParam
from backend.app.question_bank.service.category_filter_service import (
    CategoryQuestionFilter,
    category_filter_service,
)
from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import JsonSerializer
from backend.common.exception import errors

FAVORITE_STATISTICS_CACHE_TTL = 30


favorite_statistics_cache: RedisCache[dict] = RedisCache(
    prefix='qbank:favorite:statistics',
    ttl=FAVORITE_STATISTICS_CACHE_TTL,
    serializer=JsonSerializer(),
)


class FavoriteService:
    """收藏服务类"""

    @staticmethod
    def _statistics_key_parts(
        *,
        user_id: int,
        cat_id: int | None,
        kp_cat_id: int | None,
        group_by: str | None = None,
    ) -> tuple[int, str, str]:
        """
        构建收藏统计缓存键的元组

        :param user_id: 用户 ID
        :param cat_id: 题库目录分类 ID
        :param kp_cat_id: 知识点分类 ID
        :param group_by: 分组方式
        :return:
        """
        domain = category_filter_service.build_scope_key(cat_id=cat_id, kp_cat_id=kp_cat_id)
        group = group_by or 'summary'
        return user_id, domain, group

    @staticmethod
    async def _clear_statistics_cache(user_id: int) -> None:
        """
        清理用户收藏统计缓存

        :param user_id: 用户 ID
        :return:
        """
        await favorite_statistics_cache.invalidate_prefix(user_id)

    @staticmethod
    async def _get_category_filter(
        *,
        db: AsyncSession,
        cat_id: int | None,
        kp_cat_id: int | None,
    ) -> CategoryQuestionFilter | None:
        """
        获取分类过滤上下文

        :param db: 数据库会话
        :param cat_id: 题库目录分类 ID
        :param kp_cat_id: 知识点分类 ID
        :return:
        """
        return await category_filter_service.get_question_filter(db=db, cat_id=cat_id, kp_cat_id=kp_cat_id)

    @staticmethod
    async def create_favorite(*, db: AsyncSession, user_id: int, obj: CreateQuestionFavoriteParam) -> QuestionFavorite:
        """
        收藏题目

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 收藏参数
        :return:
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
            placement_id=obj.placement_id,
            folder_name=obj.folder_name,
            tags=obj.tags,
            remark=obj.remark,
        )

        await question_statistics_dao.update_stats(db, obj.question_id, UpdateQuestionStatisticsParam(collect_delta=1))
        await FavoriteService._clear_statistics_cache(user_id)
        return new_favorite

    @staticmethod
    async def delete_favorite_by_question(*, db: AsyncSession, user_id: int, question_id: int) -> int:
        """
        通过题目 ID 取消收藏

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        favorite = await question_favorite_dao.get_by_user_and_question(db=db, user_id=user_id, question_id=question_id)
        if not favorite:
            return 0

        count = await question_favorite_dao.delete(db=db, favorite_id=favorite.id)
        if count > 0:
            await question_statistics_dao.update_stats(db, question_id, UpdateQuestionStatisticsParam(collect_delta=-1))
            await FavoriteService._clear_statistics_cache(user_id)
        return count

    @staticmethod
    async def get_favorite(*, db: AsyncSession, favorite_id: int, user_id: int) -> QuestionFavorite:
        """
        获取收藏详情

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :param user_id: 用户 ID
        :return:
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
        :return:
        """
        favorite = await question_favorite_dao.get(db=db, favorite_id=favorite_id)
        if not favorite:
            raise errors.NotFoundError(msg='收藏不存在')
        if favorite.user_id != user_id:
            raise errors.AuthorizationError(msg='无权操作此收藏')

        count = await question_favorite_dao.update(
            db=db,
            favorite_id=favorite_id,
            folder_name=folder_name,
            tags=tags,
            remark=remark,
        )
        if count > 0:
            await FavoriteService._clear_statistics_cache(user_id)
        return count

    @staticmethod
    async def set_pin(*, db: AsyncSession, favorite_id: int, user_id: int, is_pinned: bool) -> int:
        """
        设置收藏置顶

        :param db: 数据库会话
        :param favorite_id: 收藏 ID
        :param user_id: 用户 ID
        :param is_pinned: 是否置顶
        :return:
        """
        favorite = await question_favorite_dao.get(db=db, favorite_id=favorite_id)
        if not favorite:
            raise errors.NotFoundError(msg='收藏不存在')
        if favorite.user_id != user_id:
            raise errors.AuthorizationError(msg='无权操作此收藏')

        count = await question_favorite_dao.set_pin(
            db=db,
            favorite_id=favorite_id,
            is_pinned=is_pinned,
        )
        if count > 0:
            await FavoriteService._clear_statistics_cache(user_id)
        return count

    @staticmethod
    async def delete_favorites(*, db: AsyncSession, favorite_ids: list[int], user_id: int) -> int:
        """
        批量取消收藏

        :param db: 数据库会话
        :param favorite_ids: 收藏 ID 列表
        :param user_id: 用户 ID
        :return:
        """
        favorites = await question_favorite_dao.list_by_ids(db=db, favorite_ids=favorite_ids)
        favorite_map = {favorite.id: favorite for favorite in favorites}
        question_ids_to_decrement: list[int] = []

        for favorite_id in favorite_ids:
            favorite = favorite_map.get(favorite_id)
            if favorite and favorite.user_id != user_id:
                raise errors.AuthorizationError(msg=f'无权操作收藏 {favorite_id}')
            if favorite:
                question_ids_to_decrement.append(favorite.question_id)

        deletable_ids = [favorite_id for favorite_id in favorite_ids if favorite_id in favorite_map]
        count = await question_favorite_dao.batch_delete(db=db, favorite_ids=deletable_ids)

        if question_ids_to_decrement:
            await question_statistics_dao.batch_update_stats(
                db=db,
                items=[{'question_id': question_id, 'collect_delta': -1} for question_id in question_ids_to_decrement],
            )

        if count > 0:
            await FavoriteService._clear_statistics_cache(user_id)
        return count

    @staticmethod
    async def check_favorited(*, db: AsyncSession, user_id: int, question_ids: list[int]) -> dict[int, bool]:
        """
        批量检查题目收藏状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids: 题目 ID 列表
        :return:
        """
        stmt = select(question_favorite_dao.model.question_id).where(
            question_favorite_dao.model.user_id == user_id,
            question_favorite_dao.model.question_id.in_(question_ids),
        )
        result = await db.execute(stmt)
        favorited_ids = {row[0] for row in result.fetchall()}
        return {question_id: question_id in favorited_ids for question_id in question_ids}

    @staticmethod
    async def _get_owned_session_question_ids(*, db: AsyncSession, user_id: int, session_id: int) -> list[int]:
        """
        获取当前用户会话内题目 ID 列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.AuthorizationError(msg='无权访问此会话')

        stmt = select(SessionQuestion.question_id).where(SessionQuestion.session_id == session_id)
        rows = (await db.execute(stmt)).scalars().all()
        return list(rows)

    @staticmethod
    async def batch_check_favorites_by_session(*, db: AsyncSession, user_id: int, session_id: int) -> dict[int, bool]:
        """
        通过会话批量检查收藏状态（单条 JOIN SQL，仅返回已收藏 ID）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :return:
        """
        stmt = (
            select(SessionQuestion.question_id)
            .join(
                QuestionFavorite,
                and_(
                    QuestionFavorite.question_id == SessionQuestion.question_id,
                    QuestionFavorite.user_id == user_id,
                ),
            )
            .where(SessionQuestion.session_id == session_id)
        )
        result = await db.execute(stmt)
        favorited_ids = {row[0] for row in result.fetchall()}
        return {qid: True for qid in favorited_ids}

    @staticmethod
    async def batch_check_favorites_from_string(
        *, db: AsyncSession, user_id: int, question_ids_str: str
    ) -> dict[int, bool]:
        """
        从字符串批量检查收藏状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_ids_str: 题目 ID 字符串
        :return:
        """
        try:
            ids = [int(qid.strip()) for qid in question_ids_str.split(',') if qid.strip()]
        except ValueError:
            raise errors.BadRequestError(msg='题目 ID 格式错误')

        if not ids:
            return {}

        return await FavoriteService.check_favorited(db=db, user_id=user_id, question_ids=ids)

    @staticmethod
    async def get_statistics(
        *,
        db: AsyncSession,
        user_id: int,
        cat_id: int | None = None,
        kp_cat_id: int | None = None,
    ) -> FavoriteStatistics:
        """
        获取收藏统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        key_parts = FavoriteService._statistics_key_parts(user_id=user_id, cat_id=cat_id, kp_cat_id=kp_cat_id)

        async def factory() -> dict:
            category_filter = await FavoriteService._get_category_filter(db=db, cat_id=cat_id, kp_cat_id=kp_cat_id)
            if category_filter and cat_id is not None:
                folder_rows = await question_favorite_dao.get_folder_counts_by_bank_ids(
                    db=db,
                    user_id=user_id,
                    bank_ids=category_filter.bank_ids,
                )
            else:
                folder_rows = await question_favorite_dao.get_folder_counts(db=db, user_id=user_id)

            total_count = 0
            folder_count = 0
            folder_stats: list[FolderInfo] = []
            for row in folder_rows:
                count = int(row['count'] or 0)
                total_count += count

                folder_name = row['folder_name']
                if folder_name:
                    folder_count += 1
                    folder_stats.append(FolderInfo(folder_name=str(folder_name), count=count))
                    continue

                folder_stats.insert(0, FolderInfo(folder_name='未分组', count=count))

            stats = FavoriteStatistics(
                total_count=total_count,
                folder_count=folder_count,
                folders=folder_stats,
            )
            return stats.model_dump()

        cached = await favorite_statistics_cache.get_or_set(*key_parts, factory=factory)
        return FavoriteStatistics(**cached) if cached else FavoriteStatistics(total_count=0, folder_count=0, folders=[])

    @staticmethod
    async def get_statistics_with_groups(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str = 'knowledge_point',
        cat_id: int | None = None,
        kp_cat_id: int | None = None,
    ) -> dict:
        """
        获取收藏统计与树形分组数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param group_by: 分组方式
        :return:
        """
        cache_key = FavoriteService._statistics_key_parts(
            user_id=user_id,
            cat_id=cat_id,
            kp_cat_id=kp_cat_id,
            group_by=group_by,
        )

        async def factory() -> dict:
            from backend.app.question_bank.service.group_tree import (
                build_bank_tree,
                build_kp_tree,
                load_banks_and_chapters,
                load_kp_categories,
            )

            category_filter = await FavoriteService._get_category_filter(db=db, cat_id=cat_id, kp_cat_id=kp_cat_id)
            stats = await FavoriteService.get_statistics(db=db, user_id=user_id, cat_id=cat_id, kp_cat_id=kp_cat_id)

            if group_by == 'knowledge_point':
                flat_counts = await question_favorite_dao.get_grouped_by_knowledge_point(db=db, user_id=user_id)
                if category_filter and kp_cat_id is not None:
                    flat_counts = [
                        item
                        for item in flat_counts
                        if str(item['group_name'] or '').strip() in category_filter.knowledge_names
                    ]
                count_map = {item['group_name']: item['count'] for item in flat_counts}
                categories = await load_kp_categories(db)
                groups = build_kp_tree(categories, count_map)
            else:
                flat_counts = await question_favorite_dao.get_bank_chapter_counts(db=db, user_id=user_id)
                if category_filter and cat_id is not None:
                    flat_counts = [
                        row
                        for row in flat_counts
                        if row['bank_id'] is not None and int(row['bank_id']) in category_filter.bank_ids
                    ]
                count_map = {(row['bank_id'], row['chapter_id']): row['count'] for row in flat_counts}
                bank_ids = {row['bank_id'] for row in flat_counts if row['bank_id'] is not None}
                chapter_ids = {row['chapter_id'] for row in flat_counts if row['chapter_id'] is not None}
                banks, chapters = await load_banks_and_chapters(db, bank_ids, chapter_ids)
                groups = build_bank_tree(banks, chapters, count_map)

            return {
                'total_count': stats.total_count,
                'folder_count': stats.folder_count,
                'groups': groups,
            }

        return await favorite_statistics_cache.get_or_set(*cache_key, factory=factory) or {}

    @staticmethod
    async def get_grouped(
        *,
        db: AsyncSession,
        user_id: int,
        group_by: str,
        cat_id: int | None = None,
        kp_cat_id: int | None = None,
    ) -> list[dict]:
        """
        按题库或知识点分组聚合收藏数量

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param group_by: 分组方式
        :return:
        """
        category_filter = await FavoriteService._get_category_filter(db=db, cat_id=cat_id, kp_cat_id=kp_cat_id)
        if group_by == 'knowledge_point':
            rows = await question_favorite_dao.get_grouped_by_knowledge_point(db=db, user_id=user_id)
            if not category_filter or kp_cat_id is None:
                return rows
            return [item for item in rows if str(item['group_name'] or '').strip() in category_filter.knowledge_names]

        rows = await question_favorite_dao.get_grouped_by_bank(db=db, user_id=user_id)
        if not category_filter or cat_id is None:
            return rows
        return [
            item for item in rows if item['group_id'] is not None and int(item['group_id']) in category_filter.bank_ids
        ]


favorite_service = FavoriteService()
