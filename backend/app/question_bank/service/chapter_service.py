#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_chapter import chapter_dao
from backend.app.question_bank.model import QuestionChapter
from backend.app.question_bank.model.question import QuestionPlacement
from backend.app.question_bank.schema.chapter import CreateChapterParam, DeleteChapterParam, UpdateChapterParam
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data


class ChapterService:
    """章节服务类"""

    @staticmethod
    async def _validate_parent_chain(
        *,
        db: AsyncSession,
        bank_id: int,
        parent_id: int | None,
        current_chapter_id: int | None = None,
    ) -> None:
        """
        校验父章节关系是否合法

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param parent_id: 父章节 ID
        :param current_chapter_id: 当前章节 ID
        :return:
        """
        if parent_id is None:
            return

        parent_chapter = await chapter_dao.get(db, parent_id)
        if not parent_chapter:
            raise errors.NotFoundError(msg='父级章节不存在')
        if parent_chapter.bank_id != bank_id:
            raise errors.ForbiddenError(msg='父级章节不属于当前内容')
        if current_chapter_id is not None and parent_chapter.id == current_chapter_id:
            raise errors.ForbiddenError(msg='禁止关联自身为父级')

        visited_ids: set[int] = set()
        current_parent = parent_chapter
        while current_parent.parent_id is not None:
            if current_parent.id in visited_ids:
                raise errors.ForbiddenError(msg='章节父子关系存在循环')
            visited_ids.add(current_parent.id)

            next_parent = await chapter_dao.get(db, current_parent.parent_id)
            if not next_parent:
                break
            if current_chapter_id is not None and next_parent.id == current_chapter_id:
                raise errors.ForbiddenError(msg='禁止将章节挂到自己的子孙章节下')
            current_parent = next_parent

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> QuestionChapter:
        """
        获取章节详情

        :param db: 数据库会话
        :param pk: 章节 ID
        :return:
        """
        chapter = await chapter_dao.get(db, pk)
        if not chapter:
            raise errors.NotFoundError(msg='章节不存在')
        return chapter

    @staticmethod
    async def get_tree(*, db: AsyncSession, bank_id: int) -> list[dict[str, Any]]:
        """
        获取章节树形结构

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :return:
        """
        bank = await bank_dao.get(db, bank_id)
        if not bank:
            raise errors.NotFoundError(msg='刷题内容不存在')

        source_bank_id = bank.chapter_source_bank_id or bank.id
        chapter_list = await chapter_dao.get_by_bank(db, source_bank_id)
        tree_data = get_tree_data(chapter_list, sort_key='sort_order')

        if not tree_data:
            return tree_data

        chapter_ids = [chapter.id for chapter in chapter_list]
        stmt = (
            select(QuestionPlacement.chapter_id, func.count(QuestionPlacement.id))
            .where(
                QuestionPlacement.bank_id == bank_id,
                QuestionPlacement.is_active.is_(True),
                QuestionPlacement.chapter_id.in_(chapter_ids),
            )
            .group_by(QuestionPlacement.chapter_id)
        )
        rows = (await db.execute(stmt)).all()
        count_map: dict[int, int] = {row[0]: row[1] for row in rows}

        def patch_count(nodes: list[dict[str, Any]]) -> None:
            """递归回填章节题量"""
            for node in nodes:
                node['q_count_cache'] = count_map.get(node['id'], 0)
                if node.get('children'):
                    patch_count(node['children'])

        patch_count(tree_data)
        return tree_data

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateChapterParam) -> None:
        """
        创建章节

        :param db: 数据库会话
        :param obj: 创建章节参数
        :return:
        """
        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='刷题内容不存在')
        if (bank.chapter_source_bank_id or bank.id) != bank.id:
            raise errors.ForbiddenError(msg='当前内容复用其他内容章节，请在章节源内容中维护章节')

        existing_chapter = await chapter_dao.get_by_name(
            db=db, bank_id=obj.bank_id, name=obj.name, parent_id=obj.parent_id,
        )
        if existing_chapter:
            raise errors.ConflictError(msg='同级章节名称已存在')

        await ChapterService._validate_parent_chain(
            db=db,
            bank_id=obj.bank_id,
            parent_id=obj.parent_id,
        )

        await chapter_dao.create(db, obj)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateChapterParam) -> int:
        """
        更新章节

        :param db: 数据库会话
        :param pk: 章节 ID
        :param obj: 更新章节参数
        :return:
        """
        chapter = await chapter_dao.get(db, pk)
        if not chapter:
            raise errors.NotFoundError(msg='章节不存在')

        bank = await bank_dao.get(db, obj.bank_id)
        if not bank:
            raise errors.NotFoundError(msg='刷题内容不存在')
        if (bank.chapter_source_bank_id or bank.id) != bank.id:
            raise errors.ForbiddenError(msg='当前内容复用其他内容章节，请在章节源内容中维护章节')

        existing_chapter = await chapter_dao.get_by_name(
            db=db, bank_id=obj.bank_id, name=obj.name, parent_id=obj.parent_id,
        )
        if existing_chapter and existing_chapter.id != chapter.id:
            raise errors.ConflictError(msg='同级章节名称已存在')

        await ChapterService._validate_parent_chain(
            db=db,
            bank_id=obj.bank_id,
            parent_id=obj.parent_id,
            current_chapter_id=chapter.id,
        )

        count = await chapter_dao.update(db, pk, obj)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, obj: DeleteChapterParam) -> int:
        """
        删除章节

        :param db: 数据库会话
        :param obj: 删除章节参数
        :return:
        """
        for chapter_id in obj.ids:
            children = await chapter_dao.get_children(db, chapter_id)
            if children:
                raise errors.ConflictError(msg='章节下存在子章节，无法删除')
        count = await chapter_dao.delete(db, obj.ids)
        return count


chapter_service: ChapterService = ChapterService()
