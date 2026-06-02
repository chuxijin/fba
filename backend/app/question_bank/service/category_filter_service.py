#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.model.bank import QuestionBank
from backend.common.log import log
from backend.database.redis import redis_client

QBANK_CATEGORY_APP_CODE = 'youanshang'
QBANK_CATEGORY_FILTER_CACHE_TTL = 3600


@dataclass(frozen=True)
class CategoryQuestionFilter:
    """分类题目过滤上下文"""

    cat_id: int | None
    kp_cat_id: int | None
    bank_ids: set[int]
    knowledge_names: set[str]


class CategoryFilterService:
    """题库分类过滤服务类"""

    @staticmethod
    def build_scope_key(*, cat_id: int | None = None, kp_cat_id: int | None = None) -> str:
        """
        构造分类范围缓存标识

        :param cat_id: 题库目录分类 ID
        :param kp_cat_id: 知识点分类 ID
        :return:
        """
        cat_key = str(cat_id) if cat_id is not None else 'all'
        kp_key = str(kp_cat_id) if kp_cat_id is not None else 'all'
        return f'cat:{cat_key}:kp:{kp_key}'

    @staticmethod
    async def get_product_catalog_category_ids(*, db: AsyncSession, cat_id: int | None) -> set[int]:
        """
        获取题库目录分类子树 ID

        :param db: 数据库会话
        :param cat_id: 题库目录分类 ID
        :return:
        """
        if cat_id is None:
            return set()

        category_ids = await category_dao.get_subtree_ids_by_path(
            db,
            int(cat_id),
            app_code=QBANK_CATEGORY_APP_CODE,
            type_='product_catalog',
            status=True,
        )
        return set(category_ids)

    @staticmethod
    async def get_knowledge_point_names(*, db: AsyncSession, kp_cat_id: int | None) -> set[str]:
        """
        获取知识点分类子树名称

        :param db: 数据库会话
        :param kp_cat_id: 知识点分类 ID
        :return:
        """
        if kp_cat_id is None:
            return set()

        return await category_dao.get_subtree_names_by_path(
            db,
            int(kp_cat_id),
            app_code=QBANK_CATEGORY_APP_CODE,
            type_='knowledge_point',
            status=True,
        )

    @staticmethod
    async def get_knowledge_point_category_ids(*, db: AsyncSession, kp_cat_id: int | None) -> set[int]:
        """
        获取知识点分类子树 ID

        :param db: 数据库会话
        :param kp_cat_id: 知识点分类 ID
        :return:
        """
        if kp_cat_id is None:
            return set()

        category_ids = await category_dao.get_subtree_ids_by_path(
            db,
            int(kp_cat_id),
            app_code=QBANK_CATEGORY_APP_CODE,
            type_='knowledge_point',
            status=True,
        )
        return set(category_ids)

    @staticmethod
    async def get_bank_ids_by_category_ids(*, db: AsyncSession, category_ids: set[int]) -> set[int]:
        """
        按分类 ID 获取题库 ID

        :param db: 数据库会话
        :param category_ids: 分类 ID 集合
        :return:
        """
        if not category_ids:
            return set()

        stmt = (
            select(QuestionBank.id)
            .where(
                QuestionBank.status == 1,
                QuestionBank.cat_id.in_(category_ids),
            )
        )
        rows = (await db.execute(stmt)).scalars().all()
        return {int(bank_id) for bank_id in rows}

    @classmethod
    async def get_question_filter(
        cls,
        *,
        db: AsyncSession,
        cat_id: int | None = None,
        kp_cat_id: int | None = None,
    ) -> CategoryQuestionFilter | None:
        """
        获取分类题目过滤上下文

        :param db: 数据库会话
        :param cat_id: 题库目录分类 ID
        :param kp_cat_id: 知识点分类 ID
        :return:
        """
        if cat_id is None and kp_cat_id is None:
            return None

        cache_key = f'qbank:category_filter:{cls.build_scope_key(cat_id=cat_id, kp_cat_id=kp_cat_id)}'
        try:
            cached = await redis_client.get(cache_key)
        except Exception as exc:
            log.warning('读取题库分类过滤缓存失败: {}', exc)
            cached = None

        if cached:
            data = json.loads(cached)
            return CategoryQuestionFilter(
                cat_id=data.get('cat_id'),
                kp_cat_id=data.get('kp_cat_id'),
                bank_ids=set(data.get('bank_ids') or []),
                knowledge_names=set(data.get('knowledge_names') or []),
            )

        category_ids = await cls.get_product_catalog_category_ids(db=db, cat_id=cat_id)
        bank_ids = await cls.get_bank_ids_by_category_ids(db=db, category_ids=category_ids)
        knowledge_names = await cls.get_knowledge_point_names(db=db, kp_cat_id=kp_cat_id)

        result = CategoryQuestionFilter(
            cat_id=cat_id,
            kp_cat_id=kp_cat_id,
            bank_ids=bank_ids,
            knowledge_names=knowledge_names,
        )
        try:
            await redis_client.setex(
                cache_key,
                QBANK_CATEGORY_FILTER_CACHE_TTL,
                json.dumps({
                    'cat_id': result.cat_id,
                    'kp_cat_id': result.kp_cat_id,
                    'bank_ids': list(result.bank_ids),
                    'knowledge_names': list(result.knowledge_names),
                }, ensure_ascii=False),
            )
        except Exception as exc:
            log.warning('写入题库分类过滤缓存失败: {}', exc)

        return result


category_filter_service: CategoryFilterService = CategoryFilterService()
