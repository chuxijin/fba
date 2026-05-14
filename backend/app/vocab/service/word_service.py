#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_word import definition_dao, example_dao, word_dao
from backend.app.vocab.schema.word import (
    CreateWordParam,
    GetDefinitionDetail,
    GetExampleDetail,
    GetWordDetail,
    UpdateWordParam,
    WordCoreParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class WordService:
    """单词管理服务类"""

    @staticmethod
    async def create_word(*, db: AsyncSession, user_id: int, obj: CreateWordParam) -> GetWordDetail:
        """
        创建单词（含释义和例句）

        :param db: 数据库会话
        :param user_id: 创建者用户 ID
        :param obj: 创建参数
        :return:
        """
        existing = await word_dao.get_by_word(db, obj.word)
        if existing:
            raise errors.ConflictError(msg=f'单词 "{obj.word}" 已存在')

        # 创建单词
        word_core = WordCoreParam(**obj.model_dump(exclude={'definitions', 'examples'}))
        word = await word_dao.create_model(db, word_core, created_by=user_id, commit=False)
        await db.flush()

        # 创建释义
        definitions = []
        for d in obj.definitions:
            defn = await definition_dao.create_model(db, d, word_id=word.id, commit=False)
            definitions.append(defn)

        # 创建例句
        examples = []
        for e in obj.examples:
            ex = await example_dao.create_model(db, e, word_id=word.id, commit=False)
            examples.append(ex)

        await db.commit()
        await db.refresh(word)

        detail = GetWordDetail.model_validate(word)
        detail.definitions = [GetDefinitionDetail.model_validate(d) for d in definitions]
        detail.examples = [GetExampleDetail.model_validate(e) for e in examples]
        return detail

    @staticmethod
    async def update_word(*, db: AsyncSession, pk: int, obj: UpdateWordParam) -> int:
        """
        更新单词（可全量替换释义/例句）

        :param db: 数据库会话
        :param pk: 单词 ID
        :param obj: 更新参数
        :return:
        """
        word = await word_dao.select_model(db, pk)
        if not word:
            raise errors.NotFoundError(msg='单词不存在')

        update_data = obj.model_dump(exclude_unset=True, exclude={'definitions', 'examples'})

        # 全量替换释义
        if obj.definitions is not None:
            await definition_dao.delete_by_word_id(db, pk)
            for d in obj.definitions:
                await definition_dao.create_model(db, d, word_id=pk, commit=False)

        # 全量替换例句
        if obj.examples is not None:
            await example_dao.delete_by_word_id(db, pk)
            for e in obj.examples:
                await example_dao.create_model(db, e, word_id=pk, commit=False)

        if update_data:
            count = await word_dao.update_model(db, pk, update_data, commit=False)
        else:
            count = 1

        await db.commit()
        return count

    @staticmethod
    async def delete_word(*, db: AsyncSession, pk: int) -> int:
        """
        删除单词（级联删除释义和例句）

        :param db: 数据库会话
        :param pk: 单词 ID
        :return:
        """
        word = await word_dao.select_model(db, pk)
        if not word:
            raise errors.NotFoundError(msg='单词不存在')

        await definition_dao.delete_by_word_id(db, pk)
        await example_dao.delete_by_word_id(db, pk)
        return await word_dao.delete_model(db, pk)

    @staticmethod
    async def get_word_detail(*, db: AsyncSession, pk: int) -> GetWordDetail:
        """
        获取单词详情（含释义和例句）

        :param db: 数据库会话
        :param pk: 单词 ID
        :return:
        """
        word = await word_dao.select_model(db, pk)
        if not word:
            raise errors.NotFoundError(msg='单词不存在')

        definitions = await definition_dao.get_by_word_id(db, pk)
        examples = await example_dao.get_by_word_id(db, pk)

        detail = GetWordDetail.model_validate(word)
        detail.definitions = [GetDefinitionDetail.model_validate(d) for d in definitions]
        detail.examples = [GetExampleDetail.model_validate(e) for e in examples]
        return detail

    @staticmethod
    async def get_word_list(*, db: AsyncSession, keyword: str | None = None) -> dict[str, Any]:
        """
        获取单词列表

        :param db: 数据库会话
        :param keyword: 搜索关键词
        :return:
        """
        stmt = await word_dao.get_select(keyword=keyword)
        return await paging_data(db, stmt)


word_service: WordService = WordService()
