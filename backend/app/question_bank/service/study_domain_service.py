#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.model.bank import QuestionBank
from backend.app.question_bank.schema.study_domain import (
    StudyDomainCategoryTree,
    StudyDomainOptionResponse,
    StudyDomainScopeResponse,
)
from backend.app.question_bank.service.study_domain_config import (
    STUDY_DOMAIN_APP_CODE,
    STUDY_DOMAIN_CONFIG,
    get_study_domain_label,
    get_study_domain_root_codes,
    normalize_study_domain_code,
    validate_study_domain_code,
)
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data


@dataclass(frozen=True)
class StudyDomainQuestionFilter:
    """学习领域题目过滤上下文"""

    code: str
    label: str
    bank_ids: set[int]
    knowledge_names: set[str]


class StudyDomainService:
    """学习领域服务类"""

    @staticmethod
    def _validate_code(code: str) -> str:
        """
        校验领域编码

        :param code: 领域编码
        :return:
        """
        try:
            return validate_study_domain_code(code)
        except ValueError as exc:
            raise errors.RequestError(msg=str(exc)) from None

    @staticmethod
    def _filter_root_nodes(
        nodes: list[dict[str, Any]],
        root_codes: list[str],
    ) -> list[StudyDomainCategoryTree]:
        """
        过滤根节点树

        :param nodes: 树节点列表
        :param root_codes: 根编码列表
        :return:
        """
        code_set = {code.strip().lower() for code in root_codes if code}
        if not code_set:
            return []

        matched_nodes = [
            node for node in nodes
            if str(node.get('code') or '').strip().lower() in code_set
        ]
        return [StudyDomainCategoryTree.model_validate(node) for node in matched_nodes]

    @staticmethod
    def _collect_category_ids(nodes: list[StudyDomainCategoryTree]) -> set[int]:
        """
        收集分类 ID

        :param nodes: 分类树节点
        :return:
        """
        category_ids: set[int] = set()

        def walk(tree_nodes: list[StudyDomainCategoryTree]) -> None:
            for node in tree_nodes:
                category_ids.add(int(node.id))
                if node.children:
                    walk(node.children)

        walk(nodes)
        return category_ids

    @staticmethod
    def _collect_category_names(nodes: list[StudyDomainCategoryTree]) -> set[str]:
        """
        收集分类名称

        :param nodes: 分类树节点
        :return:
        """
        category_names: set[str] = set()

        def walk(tree_nodes: list[StudyDomainCategoryTree]) -> None:
            for node in tree_nodes:
                name = str(node.name or '').strip()
                if name:
                    category_names.add(name)
                if node.children:
                    walk(node.children)

        walk(nodes)
        return category_names

    @staticmethod
    async def get_options() -> list[StudyDomainOptionResponse]:
        """获取领域选项列表"""
        return [
            StudyDomainOptionResponse(
                code=normalize_study_domain_code(code),
                label=str(config['label']),
                app_code=STUDY_DOMAIN_APP_CODE,
            )
            for code, config in STUDY_DOMAIN_CONFIG.items()
        ]

    @classmethod
    async def get_scope(
        cls,
        *,
        db: AsyncSession,
        code: str,
    ) -> StudyDomainScopeResponse:
        """
        获取领域分类范围

        :param db: 数据库会话
        :param code: 领域编码
        :return:
        """
        normalized_code = cls._validate_code(code)
        root_codes = get_study_domain_root_codes(normalized_code)

        categories = await category_dao.get_all(
            db,
            app_code=STUDY_DOMAIN_APP_CODE,
            status=True,
        )

        type_groups: dict[str, list[Any]] = defaultdict(list)
        for category in categories:
            type_groups[str(category.type)].append(category)

        tree_map = {
            type_name: get_tree_data(items, sort_key='sort_order')
            for type_name, items in type_groups.items()
        }

        return StudyDomainScopeResponse(
            code=normalized_code,
            label=get_study_domain_label(normalized_code),
            app_code=STUDY_DOMAIN_APP_CODE,
            product_catalog_codes=root_codes['product_catalog'],
            knowledge_point_codes=root_codes['knowledge_point'],
            resource_exam_codes=root_codes['resource_exam'],
            product_catalog_roots=cls._filter_root_nodes(
                tree_map.get('product_catalog', []),
                root_codes['product_catalog'],
            ),
            knowledge_point_roots=cls._filter_root_nodes(
                tree_map.get('knowledge_point', []),
                root_codes['knowledge_point'],
            ),
            resource_exam_roots=cls._filter_root_nodes(
                tree_map.get('resource_exam', []),
                root_codes['resource_exam'],
            ),
        )

    @classmethod
    async def get_question_filter(
        cls,
        *,
        db: AsyncSession,
        code: str,
    ) -> StudyDomainQuestionFilter:
        """
        获取题目领域过滤上下文

        :param db: 数据库会话
        :param code: 领域编码
        :return:
        """
        scope = await cls.get_scope(db=db, code=code)
        category_ids = cls._collect_category_ids(scope.product_catalog_roots)
        knowledge_names = cls._collect_category_names(scope.knowledge_point_roots)

        bank_ids: set[int] = set()
        if category_ids:
            stmt = (
                select(QuestionBank.id)
                .where(
                    QuestionBank.status == 1,
                    QuestionBank.cat_id.in_(category_ids),
                )
            )
            rows = (await db.execute(stmt)).scalars().all()
            bank_ids = {int(bank_id) for bank_id in rows}

        return StudyDomainQuestionFilter(
            code=scope.code,
            label=scope.label,
            bank_ids=bank_ids,
            knowledge_names=knowledge_names,
        )

    @classmethod
    async def get_product_catalog_category_ids(
        cls,
        *,
        db: AsyncSession,
        code: str,
    ) -> set[int]:
        """
        获取领域题库目录分类 ID 集合

        :param db: 数据库会话
        :param code: 领域编码
        :return:
        """
        scope = await cls.get_scope(db=db, code=code)
        return cls._collect_category_ids(scope.product_catalog_roots)


study_domain_service = StudyDomainService()
