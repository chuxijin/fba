#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.admin.crud.crud_category import category_dao
from backend.app.question_bank.crud.crud_bank import bank_dao
from backend.app.question_bank.crud.crud_user_bank_progress import user_bank_progress_dao
from backend.app.question_bank.crud.crud_question import question_dao
from backend.app.question_bank.model import Question, QuestionAnalysis
from backend.app.question_bank.schema.practice import (
    GetPracticeHomeNode,
    GetPracticeHomeResponse,
    PracticeHomeFilter,
)
from backend.app.question_bank.service.bank_mount_service import bank_mount_service
from backend.app.question_bank.service.question_service import question_service
from backend.app.question_bank.service.study_domain_service import study_domain_service
from backend.common.exception import errors
from backend.utils.build_tree import get_tree_data


class PracticeService:
    """刷题服务类（只读）"""

    @staticmethod
    async def _resolve_home_category_ids(
        *,
        db: AsyncSession,
        study_domain: str,
        cat_id: int | None,
    ) -> list[int]:
        """
        解析刷题首页分类范围

        :param db: 数据库会话
        :param study_domain: 学习领域编码
        :param cat_id: 分类 ID
        :return:
        """
        if cat_id is not None:
            return await category_dao.get_all_children_ids(db, cat_id)

        domain_cat_ids = await study_domain_service.get_product_catalog_category_ids(
            db=db,
            code=study_domain,
        )
        return list(domain_cat_ids)

    @staticmethod
    def _collect_home_node_ids(nodes: list[dict[str, Any]]) -> list[int]:
        """
        收集刷题首页节点 ID

        :param nodes: 内容树节点
        :return:
        """
        node_ids: list[int] = []
        for node in nodes:
            node_id = int(node['id'])
            node_ids.append(node_id)
            node_ids.extend(PracticeService._collect_home_node_ids(node.get('children') or []))

        return node_ids

    @staticmethod
    def _build_home_bank_nodes(
        nodes: list[dict[str, Any]],
        answer_count_map: dict[int, int],
    ) -> list[GetPracticeHomeNode]:
        """
        构造刷题首页题库节点

        :param nodes: 内容树节点
        :param answer_count_map: 作答数量映射
        :return:
        """
        result: list[GetPracticeHomeNode] = []
        for node in nodes:
            children = PracticeService._build_home_bank_nodes(node.get('children') or [], answer_count_map)
            count = sum(child.count for child in children)
            answer_count = sum(child.answerCount for child in children)
            if not children:
                node_id = int(node['id'])
                count = int(node.get('q_count_cache') or 0)
                answer_count = int(answer_count_map.get(node_id, 0))

            if count <= 0:
                continue

            result.append(GetPracticeHomeNode(
                id=int(node['id']),
                name=str(node.get('name') or ''),
                count=count,
                answerCount=answer_count,
                children=children or None,
            ))

        return result

    @staticmethod
    async def get_home(
        *,
        db: AsyncSession,
        study_domain: str,
        cat_id: int | None = None,
        filter_type: PracticeHomeFilter = 'bank',
        user_id: int | None = None,
    ) -> GetPracticeHomeResponse:
        """
        获取刷题首页内容

        :param db: 数据库会话
        :param study_domain: 学习领域编码
        :param cat_id: 分类 ID
        :param filter_type: 首页过滤类型
        :param user_id: 用户 ID
        :return:
        """
        if filter_type != 'bank':
            raise errors.RequestError(msg='暂不支持的首页过滤类型')

        cat_ids = await PracticeService._resolve_home_category_ids(
            db=db,
            study_domain=study_domain,
            cat_id=cat_id,
        )
        if not cat_ids:
            return GetPracticeHomeResponse(
                study_domain=study_domain,
                cat_id=cat_id,
                filter=filter_type,
                items=[],
            )

        bank_rows = await bank_dao.get_home_mappings(db, cat_ids=cat_ids, status=1)
        tree_data = await bank_mount_service.get_mount_tree(
            db=db,
            bank_select=bank_rows,
            status=1,
            parent_id=None,
        )
        if tree_data is None:
            tree_data = get_tree_data(bank_rows, sort_key='sort_order')

        answer_count_map: dict[int, int] = {}
        if user_id is not None:
            node_ids = PracticeService._collect_home_node_ids(tree_data)
            answer_count_map, _ = await user_bank_progress_dao.get_answer_correct_maps(
                db=db,
                user_id=user_id,
                bank_ids=node_ids,
            )

        return GetPracticeHomeResponse(
            study_domain=study_domain,
            cat_id=cat_id,
            filter=filter_type,
            items=PracticeService._build_home_bank_nodes(tree_data, answer_count_map),
        )

    @staticmethod
    async def get_practice_questions(
        *,
        db: AsyncSession,
        bank_id: int | None = None,
        chapter_id: int | None = None,
        type: str | None = None,
        difficulty: str | None = None,
    ) -> Sequence[Question]:
        """
        获取可练习的题目列表（不含答案）

        :param db: 数据库会话
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :param type: 题型
        :param difficulty: 难度
        :return:
        """
        return await question_dao.get_all(
            db=db,
            bank_id=bank_id,
            chapter_id=chapter_id,
            type=type,
            difficulty=difficulty,
            is_active=True,
            review_status=10,
        )

    @staticmethod
    async def get_question_for_practice(*, db: AsyncSession, question_id: int) -> dict[str, Any]:
        """
        获取题目详情用于练习（返回标准化 DTO，不含答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        question = await question_dao.get_with_relations(db, question_id)
        if not question:
            raise errors.NotFoundError(msg='题目不存在')
        if question.content_status != 10:
            raise errors.NotFoundError(msg='题目内容未通过审核')

        data = question_service.serialize_question(
            question=question,
            include_analysis=False,
            include_materials=False,
        )
        await question_service._fill_kp_display_batch(db, [data])
        return data

    @staticmethod
    async def get_practice_analysis(*, db: AsyncSession, question_id: int) -> QuestionAnalysis:
        """
        查看题目解析（刷题后查看答案）

        :param db: 数据库会话
        :param question_id: 题目 ID
        :return:
        """
        return await question_service.get_analysis(db=db, question_id=question_id, increment_view=True)


practice_service: PracticeService = PracticeService()
